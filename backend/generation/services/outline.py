"""大纲生成服务"""
import logging
import os
import re
from typing import Dict, List, Any, Optional

from providers.config import get_text_provider_config, load_text_providers_config
from prompts.services import safe_format
from ..utils.text_client import get_text_chat_client
from .task_cancel import is_cancelled, reset_cancel

logger = logging.getLogger(__name__)


class OutlineService:
    def __init__(self, user_id: Optional[str] = None):
        logger.debug("初始化 OutlineService...")
        self.user_id = user_id
        self.text_config = load_text_providers_config(user_id)
        self.client = self._get_client()
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
                }
                page_type = type_mapping.get(type_cn, "content")

            pages.append({
                "index": index,
                "type": page_type,
                "content": page_text
            })

        return pages

    def generate_outline(
        self,
        topic: str,
        images: Optional[List[bytes]] = None,
        prompt_text: Optional[str] = None,
        reference_content: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        # 开始新任务：清除该用户的取消标记
        reset_cancel(self.user_id)
        try:
            logger.info(
                f"开始生成大纲: topic={topic[:50]}..., images={len(images) if images else 0}, "
                f"reference_content={len((reference_content or '').strip())}字"
            )
            if prompt_text:
                # 使用用户自定义提示词（缺失占位符原样保留，不报错）
                prompt = safe_format(prompt_text, {
                    "topic": topic,
                    "reference_content": reference_content or '',
                })
            else:
                prompt = self.prompt_template.format(topic=topic)

            # 用户输入了参考内容：把参考内容作为创作素材并入提示词
            if reference_content and str(reference_content).strip():
                prompt += (
                    "\n\n===== 用户提供的参考内容 =====\n"
                    f"{str(reference_content).strip()}\n"
                    "==============================\n"
                    "要求：请把以上参考内容作为核心创作素材，结合主题生成图文大纲。"
                    "大纲内容应紧扣参考内容展开（引用其中的关键信息、风格、卖点或素材），"
                    "不要脱离参考内容自由发挥。"
                )
                logger.debug("添加了参考内容到提示词")

            if images and len(images) > 0:
                prompt += f"\n\n注意：用户提供了 {len(images)} 张参考图片，请在生成大纲时考虑这些图片的内容和风格。这些图片可能是产品图、个人照片或场景图，请根据图片内容来优化大纲，使生成的内容与图片相关联。"
                logger.debug(f"添加了 {len(images)} 张参考图片到提示词")

            # 从配置中获取模型参数（provider_name 为空时使用当前激活服务商）
            provider_config = get_text_provider_config(provider_name, self.user_id)
            # 指定了服务商时按该服务商新建客户端，否则沿用初始化时的客户端
            client = get_text_chat_client(provider_config) if provider_name else self.client

            model = provider_config.get('model', 'gemini-2.0-flash-exp')
            temperature = provider_config.get('temperature', 1.0)
            # 默认 4000：大纲（封面+内容+总结 2~4 页）足够表达，避免模型生成到 8000 上限
            # 才返回导致等待过久（如需更大可在服务商配置 max_output_tokens 覆盖）
            max_output_tokens = provider_config.get('max_output_tokens', 4000)

            logger.info(f"调用文本生成 API: provider={provider_name or 'active'}, model={model}, temperature={temperature}")
            outline_text = client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                images=images
            )

            logger.debug(f"API 返回文本长度: {len(outline_text)} 字符")

            # 生成过程中用户取消：结果作废，不解析、不返回
            if is_cancelled(self.user_id):
                logger.info("大纲生成已被用户取消")
                return {"success": False, "cancelled": True, "error": "已取消"}

            pages = self._parse_outline(outline_text)
            logger.info(f"大纲解析完成，共 {len(pages)} 页")

            return {
                "success": True,
                "outline": outline_text,
                "pages": pages,
                "has_images": images is not None and len(images) > 0
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"大纲生成失败: {error_msg}")

            # 根据错误类型提供更详细的错误信息
            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                detailed_error = (
                    f"API 认证失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. API Key 无效或已过期\n"
                    "2. API Key 没有访问该模型的权限\n"
                    "解决方案：在系统设置页面检查并更新 API Key"
                )
            elif "model" in error_msg.lower() or "404" in error_msg:
                detailed_error = (
                    f"模型访问失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. 模型名称不正确\n"
                    "2. 没有访问该模型的权限\n"
                    "解决方案：在系统设置页面检查模型名称配置"
                )
            elif "timeout" in error_msg.lower() or "连接" in error_msg:
                detailed_error = (
                    f"网络连接失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. 网络连接不稳定\n"
                    "2. API 服务暂时不可用\n"
                    "3. Base URL 配置错误\n"
                    "解决方案：检查网络连接，稍后重试"
                )
            elif "rate" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
                detailed_error = (
                    f"API 配额限制。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. API 调用次数超限\n"
                    "2. 账户配额用尽\n"
                    "解决方案：等待配额重置，或升级 API 套餐"
                )
            else:
                detailed_error = (
                    f"大纲生成失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. Text API 配置错误或密钥无效\n"
                    "2. 网络连接问题\n"
                    "3. 模型无法访问或不存在\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_outline_service(user_id: Optional[str] = None) -> OutlineService:
    """
    获取大纲生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return OutlineService(user_id)
