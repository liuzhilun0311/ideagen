"""Platform-aware growth recommendation contracts and deterministic fallback."""

import re

PLATFORMS = ("auto", "xiaohongshu", "douyin", "wechat", "multi")
GOALS = ("auto", "follow", "product", "inquiry", "conversion", "brand", "engagement", "share")

PLATFORM_NAMES = {
    "auto": "自动推荐",
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "wechat": "公众号",
    "multi": "通用多平台",
}

GOAL_NAMES = {
    "auto": "自动推荐",
    "follow": "涨粉关注",
    "product": "产品种草",
    "inquiry": "私信咨询",
    "conversion": "课程/服务转化",
    "brand": "品牌认知",
    "engagement": "评论互动",
    "share": "知识分享／内容表达",
}


def _normalize(value, allowed, label):
    if value is None:
        return "auto"
    if not isinstance(value, str):
        raise ValueError(f"{label}必须是有效选项。")
    value = value.strip()
    if not value:
        return "auto"
    if value not in allowed:
        raise ValueError(f"{label}必须是有效选项。")
    return value


def normalize_platform(value):
    return _normalize(value, PLATFORMS, "发布平台")


def normalize_goal(value):
    return _normalize(value, GOALS, "获客目标")


def platform_goal_instruction(platform, goal):
    platform = normalize_platform(platform)
    goal = normalize_goal(goal)
    platform_name = PLATFORM_NAMES[platform]
    goal_name = GOAL_NAMES[goal]
    return (
        "\n平台与获客目标规则："
        f"\n发布平台：{platform_name}（{platform}）；"
        f"\n获客目标：{goal_name}（{goal}）。"
        "\n自动推荐时，根据主题、受众和参考资料判断最适合的平台与目标；"
        "指定平台或目标时，页面结构、视觉风格、文字密度和行动号召必须优先适配所选项。"
        "\n平台和目标只影响内容组织与视觉推荐，不得改变用户事实、主题边界或凭空增加产品承诺。"
    )


def _catalog_id(entry):
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return ""
    return entry.get("id") or entry.get("legacy_value") or ""


def _metadata(entry):
    return entry.get("metadata") or {} if isinstance(entry, dict) else {}


def _catalog_lookup(entries):
    lookup = {}
    for entry in entries or []:
        key = _catalog_id(entry)
        if not key:
            continue
        lookup[key] = entry
        if isinstance(entry, dict) and entry.get("legacy_value"):
            lookup[entry["legacy_value"]] = entry
    return lookup


def _infer_platform(topic):
    text = str(topic or "")
    if re.search(r"抖音|短视频|口播|直播|视频号", text, re.I):
        return "douyin"
    if re.search(r"公众号|长文|深度|专栏|文章", text, re.I):
        return "wechat"
    if re.search(r"小红书|种草|收藏|笔记", text, re.I):
        return "xiaohongshu"
    return "multi"


def _infer_goal(topic):
    text = str(topic or "")
    if re.search(r"咨询|私信|预约|联系", text, re.I):
        return "inquiry"
    if re.search(r"购买|下单|报名|转化|成交", text, re.I):
        return "conversion"
    if re.search(r"产品|体验|测评|推荐|种草", text, re.I):
        return "product"
    if re.search(r"评论|讨论|互动|提问", text, re.I):
        return "engagement"
    if re.search(r"品牌|专业|认知", text, re.I):
        return "brand"
    return "follow"


def _matches(values, selected):
    values = values if isinstance(values, list) else []
    return selected in values or "multi" in values


def _score(entry, platform, goal, topic):
    metadata = _metadata(entry)
    score = 0
    platforms = metadata.get("platforms", [])
    goals = metadata.get("goals", [])
    if platform != "auto":
        score += 8 if platform in platforms else (2 if _matches(platforms, platform) else -5)
    if goal != "auto":
        score += 8 if goal in goals else -5
    text = " ".join(str(metadata.get(key, "")) for key in ("summary", "scenes", "detail"))
    for keyword in re.findall(r"[\u4e00-\u9fff]{2,}", str(topic or "")):
        if keyword in text:
            score += 1
    return score


def _preferred_ratios(platform):
    return {
        "xiaohongshu": ("3:4", "1:1", "4:3"),
        "douyin": ("9:16", "3:4", "1:1"),
        "wechat": ("3:4", "4:3", "1:1", "16:9"),
        "multi": ("3:4", "1:1", "9:16", "16:9"),
        "auto": ("3:4", "9:16", "1:1", "4:3", "16:9"),
    }.get(platform, ("3:4", "1:1"))


def _content_structure(platform, goal, layout):
    key = (platform, goal)
    presets = {
        ("xiaohongshu", "follow"): "hook_value_list_save",
        ("xiaohongshu", "product"): "hook_scene_benefit_proof",
        ("xiaohongshu", "inquiry"): "pain_solution_proof_cta",
        ("douyin", "follow"): "hook_problem_value_follow",
        ("douyin", "inquiry"): "hook_problem_solution_dm",
        ("douyin", "conversion"): "hook_demo_benefit_cta",
        ("wechat", "brand"): "观点背景案例总结",
        ("wechat", "conversion"): "问题分析方案案例行动",
    }
    return presets.get(key, f"主题引入—{layout}—要点总结—行动建议")


def normalize_growth_recommendation(value, available_layouts, available_styles):
    """Normalize model output against the authorized layout/style catalogs."""
    if not isinstance(value, dict):
        return None
    layout_lookup = _catalog_lookup(available_layouts)
    style_lookup = _catalog_lookup(available_styles)
    layout_value = value.get("layout", value.get("image_layout"))
    style_value = value.get("image_style")
    layout_entry = layout_lookup.get(layout_value) if isinstance(layout_value, str) else None
    style_entry = style_lookup.get(style_value) if isinstance(style_value, str) else None
    if layout_entry is None or style_entry is None:
        return None
    platform = normalize_platform(value.get("platform"))
    goal = normalize_goal(value.get("goal"))
    layout = _catalog_id(layout_entry)
    image_style = _catalog_id(style_entry)
    layout_ratios = _metadata(layout_entry).get("aspect_ratios", [])
    style_ratios = _metadata(style_entry).get("aspect_ratios", [])
    requested_ratio = value.get("aspect_ratio")
    ratio = requested_ratio if isinstance(requested_ratio, str) else ""
    if ratio and layout_ratios and ratio not in layout_ratios:
        ratio = ""
    if ratio and style_ratios and ratio not in style_ratios:
        ratio = ""
    if not ratio:
        ratio = next((item for item in _preferred_ratios(platform)
                      if not layout_ratios or item in layout_ratios
                      if not style_ratios or item in style_ratios), None)
    if not ratio:
        ratio = (layout_ratios or style_ratios or ["3:4"])[0]
    return {
        "platform": platform,
        "goal": goal,
        "layout": layout,
        "image_style": image_style,
        "aspect_ratio": ratio,
        "content_structure": str(value.get("content_structure") or "")[:200],
        "reason": str(value.get("reason") or "")[:120],
    }


def recommend_growth(topic, platform, goal, available_layouts, available_styles):
    """Return a catalog-safe, deterministic platform/growth recommendation."""
    platform = normalize_platform(platform)
    goal = normalize_goal(goal)
    resolved_platform = platform if platform != "auto" else _infer_platform(topic)
    resolved_goal = goal if goal != "auto" else _infer_goal(topic)
    layouts = [entry for entry in available_layouts or [] if _catalog_id(entry)]
    styles = [entry for entry in available_styles or [] if _catalog_id(entry)]
    if not layouts or not styles:
        raise ValueError("没有可用的图片布局或图片风格，无法生成推荐。")
    layout = max(enumerate(layouts), key=lambda item: (_score(item[1], resolved_platform, resolved_goal, topic), -item[0]))[1]
    style = max(enumerate(styles), key=lambda item: (_score(item[1], resolved_platform, resolved_goal, topic), -item[0]))[1]
    raw = {
        "platform": resolved_platform,
        "goal": resolved_goal,
        "layout": _catalog_id(layout),
        "image_style": _catalog_id(style),
        "content_structure": _content_structure(resolved_platform, resolved_goal, layout.get("name", _catalog_id(layout))),
        "reason": f"根据{PLATFORM_NAMES[resolved_platform]}与{GOAL_NAMES[resolved_goal]}，优先选择{layout.get('name', _catalog_id(layout))}和{style.get('name', _catalog_id(style))}。",
    }
    normalized = normalize_growth_recommendation(raw, layouts, styles)
    if normalized is None:
        raise ValueError("目录中没有可用的增长推荐组合。")
    return normalized
