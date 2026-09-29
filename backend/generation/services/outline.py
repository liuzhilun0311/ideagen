"""大纲生成服务"""
import logging
import os
import re
from typing import Dict, List, Any, Optional

from providers.config import get_text_provider_config, load_text_providers_config
from prompts.services import safe_format
from prompts.catalog_runtime import options as catalog_options
from ..utils.text_client import get_text_chat_client
from .task_cancel import is_cancelled, reset_cancel
from ..styles import recommendation_instruction, extract_recommendation
from ..recommendations import (
    recommendation_instruction as generation_recommendation_instruction,
    extract_generation_recommendation,
    extract_growth_recommendation,
)
from ..structure import organization_instruction, extract_organization, page_metadata
from ..outline_prompt import build_outline_prompt
from ..page_count import validate_page_count
from ..diagnostics import sanitize, record_current
from ..platform_recommendations import (
    normalize_goal,
    normalize_growth_recommendation,
    normalize_platform,
    recommend_growth,
)
from prompts.catalog_runtime import options as catalog_options

logger = logging.getLogger(__name__)


class OutlineService:
    def __init__(self, user_id: Optional[str] = None):
        logger.debug("初始化 OutlineService...")
        self.user_id = user_id
        self.text_config = load_text_providers_config(user_id)
        self.client = None
        self.prompt_template = self._load_prompt_template()
        logger.info(f"OutlineService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _get_client(self):
        """根据配置获取客户端（含 API Key 校验）"""
        provider_config = get_text_provider_config(None, self.user_id)
        logger.info(f"使用文本服务商: {provider_config.get('type')}")
        return get_text_chat_client(provider_config)

    def _load_prompt_template(self) -> str:
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            "outline_prompt.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_outline(self, outline_text: str) -> List[Dict[str, Any]]:
        # 按 <page> 分割页面（兼容旧的 --- 分隔符）
        if '<page>' in outline_text:
            pages_raw = re.split(r'<page>', outline_text, flags=re.IGNORECASE)
        else:
            # 向后兼容：如果没有 <page> 则使用 ---
            pages_raw = outline_text.split("---")

        pages = []

        for index, page_text in enumerate(pages_raw):
            page_text = page_text.strip()
            if not page_text:
                continue

            page_type = "content"
            type_match = re.match(r"\[(\S+)\]", page_text)
            if type_match:
                type_cn = type_match.group(1)
                type_mapping = {
                    "封面": "cover",
                    "内容": "content",
                    "总结": "summary",
                    "信息图": "infographic",
                }
                page_type = type_mapping.get(type_cn, "content")

            pages.append({
                "index": index,
                "type": page_type,
                "content": page_text,
                **page_metadata(page_text),
            })

        return pages

    def generate_outline(
        self,
        topic: str,
        images: Optional[List[bytes]] = None,
        prompt_text: Optional[str] = None,
        reference_content: Optional[str] = None,
        provider_name: Optional[str] = None,
        organization: str = "自动",
        options=None,
        prepared_prompt=None,
        on_send=None,
    ) -> Dict[str, Any]:
        # 开始新任务：清除该用户的取消标记
        reset_cancel(self.user_id)
        provider_config = {}
        prompt = prepared_prompt or prompt_text
        try:
            logger.info(
                f"开始生成大纲: topic={topic[:50]}..., images={len(images) if images else 0}, "
                f"reference_content={len((reference_content or '').strip())}字"
            )
            prompt = prepared_prompt if prepared_prompt is not None else build_outline_prompt(
                topic, reference_content, len(images or []),
                options or {"organization": organization},
                template=prompt_text or self.prompt_template,
            )
            # 从配置中获取模型参数（provider_name 为空时使用当前激活服务商）
            provider_config = get_text_provider_config(provider_name, self.user_id)
            # 指定了服务商时按该服务商新建客户端，否则沿用初始化时的客户端
            client = get_text_chat_client(provider_config) if provider_name else self.client or self._get_client()

            model = provider_config.get('model', 'gemini-2.0-flash-exp')
            temperature = provider_config.get('temperature', 1.0)
            # 默认 4000：大纲（封面+内容+总结 2~4 页）足够表达，避免模型生成到 8000 上限
            # 才返回导致等待过久（如需更大可在服务商配置 max_output_tokens 覆盖）
            max_output_tokens = provider_config.get('max_output_tokens', 4000)

            logger.info(f"调用文本生成 API: provider={provider_name or 'active'}, model={model}, temperature={temperature}")
            if on_send:
                on_send(prompt, model)
            outline_text = client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                images=images
            )
            record_current({"event": "response", "phase": "outline", "status": "received",
                            "model": model, "body": {"output_text": outline_text}},
                           (provider_config.get("api_key"),))

            logger.debug(f"API 返回文本长度: {len(outline_text)} 字符")

            # 生成过程中用户取消：结果作废，不解析、不返回
            if is_cancelled(self.user_id):
                logger.info("大纲生成已被用户取消")
                return {"success": False, "cancelled": True, "error": "已取消"}

            outline_text, generation_recommendation = extract_generation_recommendation(outline_text)
            available_layouts = catalog_options("image", "layout")
            available_styles = catalog_options("image", "style")
            outline_text, tagged_growth = extract_growth_recommendation(
                outline_text, available_layouts, available_styles
            )
            request_options = options or {}
            platform = normalize_platform(request_options.get("platform"))
            goal = normalize_goal(request_options.get("goal"))
            nested_growth = normalize_growth_recommendation(
                generation_recommendation.get("growth_recommendation"),
                available_layouts,
                available_styles,
            ) if isinstance(generation_recommendation, dict) else None
            growth_recommendation = (
                tagged_growth
                or nested_growth
                or recommend_growth(
                    topic,
                    platform,
                    goal,
                    available_layouts,
                    available_styles,
                )
            )
            fallback = recommend_growth(topic, platform, goal, available_layouts, available_styles)
            growth_recommendation["source"] = "model" if tagged_growth or nested_growth else "rules"
            for key, selected in (("platform", platform), ("goal", goal)):
                recommended = growth_recommendation.get(key)
                growth_recommendation[key] = selected if selected != "auto" else (
                    recommended if recommended not in (None, "auto") else fallback[key])
            outline_text, recommendation = extract_recommendation(outline_text, topic)
            outline_text, recommended_organization = extract_organization(outline_text)
            pages = self._parse_outline(outline_text)
            validate_page_count(
                pages,
                (options or {}).get("page_count", "auto"),
                (options or {}).get("content_form")
                if (options or {}).get("_content_form_explicit", True) else None,
            )
            logger.info(f"大纲解析完成，共 {len(pages)} 页")

            return {
                "success": True,
                "outline": outline_text,
                "pages": pages,
                "style_recommendation": recommendation,
                "generation_recommendation": generation_recommendation,
                "growth_recommendation": growth_recommendation,
                "organization": organization if organization != "自动" else recommended_organization,
                "has_images": images is not None and len(images) > 0
            }

        except Exception as e:
            # Classify only the actual failure; generic advice changes keyword matching.
            error_msg = sanitize(str(e), (provider_config.get("api_key"), prompt))
            logger.error(f"大纲生成失败: {error_msg}")

            return {
                "success": False,
                "error": error_msg
            }


def get_outline_service(user_id: Optional[str] = None) -> OutlineService:
    """
    获取大纲生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return OutlineService(user_id)
