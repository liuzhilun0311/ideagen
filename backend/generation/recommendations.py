import json
import re
from .outline_modes import normalize_content_form, normalize_information_density


def recommendation_instruction(options=None):
    options = options or {}
    from prompts.catalog_runtime import options as catalog_options
    tone_choices = "、".join(
        entry.get("legacy_value") or entry["id"]
        for entry in catalog_options("outline", "tone")
        if entry.get("legacy_value") != "自动匹配"
    )
    automatic = [key for key, default in (
        ("platform", "auto"), ("goal", "auto"), ("audience", "自动判断"),
        ("organization", "自动"), ("tone", "自动匹配"),
        ("content_form", "auto"), ("information_density", "auto")
    ) if options.get(key, default) == default]
    return (
        '\n\n【图片与文案设置推荐】\n'
        '根据主题和完整大纲，推荐图片风格、图片布局、文案风格、正文结构、文案长度和表情丰富度。'
        '只推荐目录中存在的名称；在所有页面之后输出一行 '
        '<generation-recommendation>JSON</generation-recommendation>。'
        'JSON字段为 image_style、image_layout、copy_style、copy_structure、copy_length、emoji_level、reason，'
        '另需提供 audience、audience_detail，记录本次大纲实际面向的读者。'
        'audience 从“零基础入门”“有一定基础”“专业读者”“自定义”中选择；'
        '如果选择自定义，audience_detail 填具体读者，不超过120字；否则填空字符串。'
        '用户已指定读者时遵循用户设置，不得自行改换。'
        f'另需提供 tone 字段，记录实际采用的表达语气，从以下目录选择：{tone_choices}。'
        '自动匹配时结合主题和读者选择具体语气，不得仍返回“自动匹配”；手动指定时遵循用户选择。'
        '另需提供 outline_explanation 对象，仅为以下自动选项返回推荐理由：'
        + ("、".join(automatic) or "无") +
        '。每项理由为不超过120字的中文字符串，结合主题、参考资料和页数，不能只重复选项名。'
        '手动指定的选项不要返回理由，也不要返回“遵循用户设置”等占位文字。'
        'outline_explanation 另含 sequence_meaning 和 sequence_reason，分别说明实际叙述顺序的含义与依据，'
        '各不超过120字；必须对应最终页面顺序，没有对比素材时不得硬套前后对比，不得虚构事实或效果。'
        '其中 emoji_level 只能是“无”“克制”“丰富”，reason 不超过120字。'
        '可额外提供 growth_recommendation 对象，字段为 platform、goal、layout、image_style、'
        'aspect_ratio、content_structure、reason；layout 同时兼容旧字段 image_layout。'
        'image_style 是整套内容共用的一项风格推荐；每一页都必须在页面正文中单独返回“单页布局：名称”，'
        '作为该页的布局推荐；逐页布局应匹配各页内容，不要把所有页面机械设为同一布局。'
        'content_structure 用中文描述实际大纲的叙述顺序，不使用英文内部标识；'
        '该顺序必须与所选组织方式及生成的页序一致。reason 说明主题、受众、页数、平台与目标为何适合该方案，'
        '不得只重复平台名称，也不得虚构评估结果。'
        '另需提供 content_form 字段，记录实际采用的内容形态；只能从单页知识信息图、多页知识卡片、流程图解、对比分析图、方法论海报、产品介绍长图、数据结论图、清单海报中选择。'
        '另需提供 information_density 字段，记录实际采用的信息密度，只能从简洁、标准、高密度中选择。'
        '也可在所有页面之后单独输出 <growth-recommendation>JSON</growth-recommendation>。'
        '该元数据不是页面文字。'
    )


def resolve_adopted_tone(requested, recommendation):
    """Resolve automatic tone only when the model returns a catalog value."""
    result = dict(requested)
    if result.get("tone") != "自动匹配" or not isinstance(recommendation, dict):
        return result
    tone = recommendation.get("tone")
    if not isinstance(tone, str) or not tone.strip():
        return result
    try:
        from prompts.catalog_runtime import option
        entry = option("outline", "tone", tone.strip())
    except (KeyError, ValueError):
        return result
    result["tone"] = entry.get("legacy_value") or entry.get("id") or tone.strip()
    return result


def attach_outline_explanation(result, options):
    raw = (result.get("generation_recommendation") or {}).get("outline_explanation")
    growth = result.get("growth_recommendation")
    if not isinstance(raw, dict) or not isinstance(growth, dict):
        return
    explanation = {}
    automatic = {
        "platform": "auto", "goal": "auto", "audience": "自动判断",
        "organization": "自动", "tone": "自动匹配",
        "content_form": "auto", "information_density": "auto",
    }
    for key in (*automatic, "sequence_meaning", "sequence_reason"):
        if key in automatic and options.get(key, automatic[key]) != automatic[key]:
            continue
        if key in ("platform", "goal", "sequence_meaning", "sequence_reason") and growth.get("source") != "model":
            continue
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            explanation[key] = value.strip()[:120]
    if explanation:
        growth["outline_explanation"] = explanation


def resolve_adopted_outline_modes(requested, recommendation):
    """Resolve automatic content form and density from valid model metadata."""
    result = dict(requested)
    if not isinstance(recommendation, dict):
        recommendation = {}
    if normalize_content_form(result.get("content_form")) == "auto":
        try:
            result["content_form"] = normalize_content_form(recommendation.get("content_form"))
        except ValueError:
            result["content_form"] = "single_infographic" if result.get("page_count") == 1 else "multi_page_cards"
    if normalize_information_density(result.get("information_density")) == "auto":
        try:
            result["information_density"] = normalize_information_density(recommendation.get("information_density"))
        except ValueError:
            result["information_density"] = "standard"
    return result


def resolve_adopted_audience(requested, recommendation):
    """Only resolve automatic readers from valid model metadata."""
    result = dict(requested)
    if result.get("audience") != "自动判断" or not isinstance(recommendation, dict):
        return result
    audience = recommendation.get("audience")
    if audience not in ("零基础入门", "有一定基础", "专业读者", "自定义"):
        return result
    detail = recommendation.get("audience_detail", "")
    if audience == "自定义":
        if not isinstance(detail, str) or not detail.strip() or len(detail.strip()) > 120:
            return result
        result["audience_detail"] = detail.strip()
    else:
        result["audience_detail"] = ""
    result["audience"] = audience
    return result


def extract_generation_recommendation(text):
    match = re.search(r'<generation-recommendation>\s*(.*?)\s*</generation-recommendation>', text, re.S | re.I)
    result = {}
    if match:
        try:
            value = json.loads(match.group(1))
            if isinstance(value, dict):
                result = value
        except (ValueError, TypeError):
            pass
    clean = re.sub(r'<generation-recommendation>.*?(?:</generation-recommendation>|$)', '', text, flags=re.S | re.I).strip()
    return clean, result


def extract_growth_recommendation(text, available_layouts, available_styles):
    from .platform_recommendations import normalize_growth_recommendation

    match = re.search(r'<growth-recommendation>\s*(.*?)\s*</growth-recommendation>', text, re.S | re.I)
    result = None
    if match:
        try:
            result = normalize_growth_recommendation(
                json.loads(match.group(1)), available_layouts, available_styles
            )
        except (ValueError, TypeError):
            pass
    clean = re.sub(r'<growth-recommendation>.*?(?:</growth-recommendation>|$)', '', text,
                   flags=re.S | re.I).strip()
    return clean, result
