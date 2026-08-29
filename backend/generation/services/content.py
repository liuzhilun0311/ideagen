"""
内容生成服务

生成小红书风格的标题、文案和标签
"""

import json
import logging
import os
import re
from typing import Dict, List, Any, Optional

from providers.config import get_text_provider_config, load_text_providers_config
from prompts.services import safe_format
from ..utils.text_client import get_text_chat_client
from .task_cancel import is_cancelled, reset_cancel


logger = logging.getLogger(__name__)


class ContentService:
    """内容生成服务：生成标题、文案、标签"""

    def __init__(self, user_id: Optional[str] = None):
        logger.debug("初始化 ContentService...")
        self.user_id = user_id
        self.text_config = load_text_providers_config(user_id)
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"ContentService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _get_client(self):
        """根据配置获取客户端（含 API Key 校验）"""
        provider_config = get_text_provider_config(None, self.user_id)
        logger.info(f"使用文本服务商: {provider_config.get('type')}")
        return get_text_chat_client(provider_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            "content_prompt.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        解析 AI 返回的 JSON 响应
        修复：兼容各种markdown代码块格式，有无换行都能解析
        """
        raw = response_text.strip()
        logger.debug(f"[AI原始返回片段] {raw[:300]}")

        # 策略1：提取 ```json / ``` markdown代码块，\s*兼容空格、换行、无换行
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if json_match:
            candidate = json_match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                logger.debug("策略1：代码块内部JSON解析失败，继续尝试其他策略")

        # 策略2：全局截取最外层 { ... }，忽略前后多余垃圾文字
        start_idx = raw.find('{')
        end_idx = raw.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = raw[start_idx:end_idx + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                logger.debug("策略2：截取{}范围JSON解析失败")

        # 策略3：兜底直接解析原始字符串
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        logger.error(f"无法解析 JSON 响应: {response_text[:200]}...")
        raise ValueError("AI 返回的内容格式不正确，无法解析")

    def generate_content(
        self,
        topic: str,
        outline: str,
        prompt_text: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成标题、文案和标签

        参数：
            topic: 用户输入的主题
            outline: 大纲内容
            prompt_text: 用户自定义提示词（可选）

        返回：
            包含 titles, copywriting, tags 的字典
        """
        # 开始新任务：清除该用户的取消标记
        reset_cancel(self.user_id)
        try:
            logger.info(f"开始生成内容: topic={topic[:50]}...")

            # 构建提示词
            if prompt_text:
                # 使用用户自定义提示词（缺失占位符原样保留，不报错）
                prompt = safe_format(prompt_text, {"topic": topic, "outline": outline})
            else:
                prompt = self.prompt_template.format(
                    topic=topic,
                    outline=outline
                )

            # 从配置中获取模型参数（provider_name 为空时使用当前激活服务商）
            provider_config = get_text_provider_config(provider_name, self.user_id)
            # 指定了服务商时按该服务商新建客户端，否则沿用初始化时的客户端
            client = get_text_chat_client(provider_config) if provider_name else self.client

            model = provider_config.get('model', 'gemini-2.0-flash-exp')
            temperature = provider_config.get('temperature', 1.0)
            max_output_tokens = provider_config.get('max_output_tokens', 4000)

            logger.info(f"调用文本生成 API: provider={provider_name or 'active'}, model={model}, temperature={temperature}")
            response_text = client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )

            logger.debug(f"API 返回文本长度: {len(response_text)} 字符")

            # 生成过程中用户取消：结果作废，不解析、不返回
            if is_cancelled(self.user_id):
                logger.info("内容生成已被用户取消")
                return {"success": False, "cancelled": True, "error": "已取消"}

            # 解析 JSON 响应
            content_data = self._parse_json_response(response_text)

            # 验证必要字段
            titles = content_data.get('titles', [])
            copywriting = content_data.get('copywriting', '')
            tags = content_data.get('tags', [])

            # 确保 titles 是列表
            if isinstance(titles, str):
                titles = [titles]

            # 确保 tags 是列表
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',')]

            logger.info(f"内容生成完成: {len(titles)} 个标题, {len(tags)} 个标签")

            return {
                "success": True,
                "titles": titles,
                "copywriting": copywriting,
                "tags": tags
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"内容生成失败: {error_msg}")

            # 根据错误类型提供更详细的错误信息
            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                detailed_error = (
                    f"API 认证失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：API Key 无效或已过期\n"
                    "解决方案：在系统设置页面检查并更新 API Key"
                )
            elif "model" in error_msg.lower() or "404" in error_msg:
                detailed_error = (
                    f"模型访问失败。\n"
                    f"错误详情: {error_msg}\n"
                    "解决方案：在系统设置页面检查模型名称配置"
                )
            elif "timeout" in error_msg.lower() or "连接" in error_msg:
                detailed_error = (
                    f"网络连接失败。\n"
                    f"错误详情: {error_msg}\n"
                    "解决方案：检查网络连接，稍后重试"
                )
            elif "rate" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
                detailed_error = (
                    f"API 配额限制。\n"
                    f"错误详情: {error_msg}\n"
                    "解决方案：等待配额重置，或升级 API 套餐"
                )
            else:
                detailed_error = (
                    f"内容生成失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_content_service(user_id: Optional[str] = None) -> ContentService:
    """
    获取内容生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return ContentService(user_id)
