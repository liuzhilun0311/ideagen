import json
import re
from copy import deepcopy


EMPTY_ANALYSIS = {
    "content": {
        "summary": "",
        "subjects": [],
        "text_structure": [],
        "visual_focus": "",
        "rewrite": "",
    },
    "layout": {
        "page_type": "content",
        "description": "",
        "regions": [],
        "hierarchy": "",
        "spacing": "",
        "prompt_text": "",
    },
    "visual_style": {
        "description": "",
        "attributes": [],
        "palette": [],
        "medium": "",
        "lighting": "",
        "composition": "",
        "prompt_text": "",
    },
    "rewritten_content": "",
}


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _string_list(value):
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if isinstance(item, str) and item.strip()]


def normalize_analysis_payload(value):
    if not isinstance(value, dict):
        raise ValueError("图片分析结果格式无效")

    result = deepcopy(EMPTY_ANALYSIS)
    content = value.get("content") if isinstance(value.get("content"), dict) else {}
    result["content"].update({
        "summary": _text(content.get("summary")),
        "subjects": _string_list(content.get("subjects")),
        "text_structure": content.get("text_structure") if isinstance(content.get("text_structure"), list) else [],
        "visual_focus": _text(content.get("visual_focus")),
        "rewrite": _text(content.get("rewrite")),
    })

    layout = value.get("layout") if isinstance(value.get("layout"), dict) else {}
    result["layout"].update({
        "page_type": _text(layout.get("page_type")) or "content",
        "description": _text(layout.get("description")),
        "regions": layout.get("regions") if isinstance(layout.get("regions"), list) else [],
        "hierarchy": _text(layout.get("hierarchy")),
        "spacing": _text(layout.get("spacing")),
        "prompt_text": _text(layout.get("prompt_text")),
    })

    style = value.get("visual_style") if isinstance(value.get("visual_style"), dict) else {}
    result["visual_style"].update({
        "description": _text(style.get("description")),
        "attributes": _string_list(style.get("attributes")),
        "palette": _string_list(style.get("palette")),
        "medium": _text(style.get("medium")),
        "lighting": _text(style.get("lighting")),
        "composition": _text(style.get("composition")),
        "prompt_text": _text(style.get("prompt_text")),
    })
    result["rewritten_content"] = _text(value.get("rewritten_content"))
    if not result["rewritten_content"]:
        result["rewritten_content"] = result["content"]["rewrite"]
    return result


def parse_analysis_response(text):
    raw = (text or "").strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    candidates = [match.group(1).strip()] if match else []
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start:end + 1])
    candidates.append(raw)

    for candidate in candidates:
        try:
            return normalize_analysis_payload(json.loads(candidate))
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    raise ValueError("AI 返回的图片分析结果格式不正确")


def build_analysis_prompt(context=None):
    context = context if isinstance(context, dict) else {}
    topic = _text(context.get("topic"))
    page_content = _text(context.get("page_content"))
    context_text = []
    if topic:
        context_text.append(f"当前主题：{topic}")
    if page_content:
        context_text.append(f"当前页面内容：{page_content}")
    context_block = "\n".join(context_text) or "没有额外创作上下文。"
    return f"""你是 IdeaGen 的图片参考分析助手。
请分析用户上传的图片，并严格只返回一个 JSON 对象，不要返回 Markdown 或解释文字。
分析必须拆分为 content、layout、visual_style 和 rewritten_content 四个字段。
content 描述图片表达的内容、主体、文字结构、视觉重点，并给出可编辑的 rewrite。
layout 只描述单页布局、信息区域、层级、留白和构图关系。
visual_style 只描述媒介、色彩、材质、光线、氛围和构图风格。
layout.prompt_text 和 visual_style.prompt_text 必须是可复用提示词。
不要在图片风格提示词中写入具体分辨率、宽高比、质量或输出格式。
OCR 结果可能不准确，请把不确定内容标记为需要确认，不要编造不可见文字。

{context_block}

JSON 结构：
{{
  "content": {{
    "summary": "",
    "subjects": [],
    "text_structure": [],
    "visual_focus": "",
    "rewrite": ""
  }},
  "layout": {{
    "page_type": "cover|content|summary",
    "description": "",
    "regions": [],
    "hierarchy": "",
    "spacing": "",
    "prompt_text": ""
  }},
  "visual_style": {{
    "description": "",
    "attributes": [],
    "palette": [],
    "medium": "",
    "lighting": "",
    "composition": "",
    "prompt_text": ""
  }},
  "rewritten_content": ""
}}"""
