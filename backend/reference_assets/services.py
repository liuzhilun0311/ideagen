import hashlib
import logging

from providers.config import get_text_provider_config
from generation.utils.text_client import get_text_chat_client

from .protocol import build_analysis_prompt, parse_analysis_response

logger = logging.getLogger(__name__)


def analyze_image(image, user_id, context=None, provider_name=None):
    if not isinstance(image, bytes) or not image:
        raise ValueError("请上传有效图片")
    provider_config = get_text_provider_config(provider_name or None, user_id)
    client = get_text_chat_client(provider_config)
    response = client.generate_text(
        prompt=build_analysis_prompt(context),
        model=provider_config.get("model", "gemini-2.0-flash-exp"),
        temperature=provider_config.get("temperature", 0.4),
        max_output_tokens=provider_config.get("max_output_tokens", 4000),
        images=[image],
    )
    result = parse_analysis_response(response)
    logger.info("图片分析完成 user=%s digest=%s", user_id, hashlib.sha256(image).hexdigest()[:12])
    return result
