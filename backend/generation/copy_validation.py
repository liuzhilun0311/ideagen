"""Deterministic checks, not a claim of semantic or factual verification."""
import re

_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u20E3]")
_INFORMATION_SYMBOL = re.compile("[\u2460-\u2473\u2776-\u277F\u24EA\u2190-\u21FF\u2022\u25CF]")
_RANGES = {"简短": (100, 200), "适中": (300, 500), "详细": (600, 900)}


def validate_copy_result(result, options):
    warnings = []
    text = result.get("copywriting", "")
    if not isinstance(text, str):
        raise ValueError("文案正文格式无效。")
    if options.get("emoji_level") == "无" and _EMOJI.search(text):
        raise ValueError("模型未遵守不使用表情符号的要求，请重试；已有文案保持不变。")
    if options.get("emoji_level") == "丰富" and not (_EMOJI.search(text) or _INFORMATION_SYMBOL.search(text)):
        warnings.append("已选择“丰富”，但正文未包含表情或信息符号。内容已保留，可重新生成或手动补充中性编号、勾选和提示符号。")
    bounds = _RANGES.get(options.get("length"))
    count = len(re.sub(r"\s", "", text))
    if bounds and not bounds[0] <= count <= bounds[1]:
        warnings.append(f"正文约{count}字，未落在建议的{bounds[0]}至{bounds[1]}字范围；长度为软目标，请核对素材完整性。")
    return {"body_characters": count, "warnings": warnings,
            "semantic_verified": False, "facts_verified": False}
