"""Shared generation context and platform-aware prompt rules."""

from .platform_recommendations import (
    GOAL_NAMES,
    PLATFORM_NAMES,
    normalize_goal,
    normalize_platform,
)
from .outline_modes import CONTENT_FORMS, DENSITIES, normalize_content_form, normalize_information_density

_PHASES = ("outline", "copy", "image")

PLATFORM_RULES = {
    "auto": "根据主题与受众选择图文阅读场景，不自动改写为视频脚本；在无法确定平台时采用最稳妥的通用表达。",
    "xiaohongshu": (
        "首屏明确具体问题与可收藏的价值；短段落、可扫读要点，避免夸张种草及虚构亲测。"
        "重点规避绝对化、极限化、保证性和强功效表达，以及医疗、药品、临床、专利、权威背书暗示。"
        "例如“100%有效”“根治”“最有效”“美白”“减肥”“孕妇可用”等，仅作为高风险语义识别示例，"
        "不得机械替换，也不得用近义包装保留原承诺。"
        "涉及减肥、降脂、降糖、降压、美白、祛斑、抗衰、生发、防脱、杀菌、消炎、排毒、清肠等，"
        "只能基于已提供资料说明具体场景、特点和限制，不把它们写成确定效果。"
        "不对孕妇、儿童、老人等特殊人群作无依据的适用或安全承诺。"
    ),
    "douyin": (
        "按抖音图文而非视频脚本组织：首屏直接点题，一页一个重点，短句快节奏；重点远离边缘操作区。"
        "避免标题党、极端结果承诺、立刻见效、制造焦虑、诱导冲动购买或用强刺激替代事实依据。"
        "保留必要条件、过程和限制；不把互动口号、热梗或情绪化措辞写成效果保证。"
    ),
    "wechat": (
        "按公众号图文组织：交代背景、逻辑衔接与适用边界；图中留核心信息，发布正文补充解释，不虚构引用。"
        "标题、导语和结论避免夸大承诺、权威背书暗示和广告化定论；长文先说明依据、适用范围和限制，再给建议。"
        "引用研究、政策、案例或数据时只能使用用户提供或可核对的内容，不补写来源。"
    ),
    "multi": (
        "生成一份跨平台通用图文，不宣称已产出多个平台版本；避免平台专属口令，保留清楚的标题和可拆分段落。"
        "采用最保守的跨平台表达：事实、条件、限制和适用范围优先，不为迎合某个平台添加刺激性或承诺性措辞。"
    ),
}
COMMON_RISK_RULES = (
    "\n\n【平台风险表达底线】"
    "\n这是一组生成前的表达约束，不是完整、实时或官方的违禁词数据库，也不保证任何平台审核通过。"
    "\n避免无法证明的绝对化、极限化、唯一性、保证性、零风险、强功效和功效承诺；"
    "避免把普通介绍包装成医疗化表达；"
    "不得虚构效果、案例、用户证言、资质、数据、临床结果、专利、排名或权威背书。"
    "\n涉及健康、法律、财务或其他高风险主题时，说明依据、适用条件、个体差异和必要限制；"
    "不能确认时使用“可作为参考”“可能有帮助”“建议结合实际情况判断”等有边界的表达。"
    "\n语义改写只能让表达更客观、有限定条件和符合上下文，不得把承诺换成隐晦同义词继续规避；"
    "不得使用谐音、拆字或特殊字符规避平台规则；也不得使用编码或故意变形规避平台规则。"
    "\n不得修改事实；不得修改用户提供的数字、日期、价格、单位、产品名称、必要风险说明或结论；"
    "本规则只进入生成提示词，生成完成后不机械替换、删词或重写正文。"
)
COPY_RISK_RULES = (
    "\n文案阶段：先识别标题、正文、标签和行动号召中的高风险承诺，再根据语义自然改写为"
    "场景、特点、使用建议、资料范围或有限定条件的表达；不得输出这组制作指令，不得把示例词表原样堆进正文。"
)
OUTLINE_RISK_RULES = (
    "\n大纲阶段：不要让页面标题、结论、卖点或行动建议先形成无法证明的结果承诺；"
    "把依据、条件和限制安排在读者能看到的位置。"
)
IMAGE_RISK_RULES = (
    "\n图片阶段：图片标题、卖点、标签和 CTA 同样遵守风险表达底线；"
    "只使用大纲和页面事实中已有的文字，不用装饰性短语放大效果或制造紧迫感。"
)
GOAL_RULES = {
    "share": "以准确传达知识、观点或体验为目标，自然总结；不强加关注、私信、购买或转化引导。",
    "auto": "选择与内容匹配的一个主要行动，不堆叠关注、购买和私信要求。",
    "follow": "以可持续提供的主题价值引导关注，不承诺未提供的后续福利。",
    "product": "突出有素材支持的产品用途、适用人群与限制，不编造测评或使用体验。",
    "inquiry": "说明适合咨询的问题和已有服务范围；不编造联系方式、赠品或私信暗号。",
    "conversion": "依据已有资料说明适用条件与下一步；没有课程或服务事实时不给购买承诺，不制造限时稀缺。",
    "brand": "通过准确的信息和一致的表达建立认知，不虚构资质、客户案例或行业排名。",
    "engagement": "结尾提出一个具体且易回答、与主题相关的问题，不诱导无意义刷评论。",
}


def effective_preferences(requested, recommendation=None):
    result = dict(requested)
    recommendation = _mapping(recommendation)
    for key, normalize in (("platform", normalize_platform), ("goal", normalize_goal)):
        selected = normalize(result.get(key))
        result[key] = normalize(recommendation.get(key)) if selected == "auto" else selected
    for key, normalize in (("content_form", normalize_content_form),
                           ("information_density", normalize_information_density)):
        if key not in requested:
            continue
        selected = normalize(result.get(key))
        recommended = normalize(recommendation.get(key))
        result[key] = recommended if selected == "auto" else selected
    return result

def _mapping(value):
    return value if isinstance(value, dict) else {}


def growth_prompt_rules(platform, goal, phase):
    """Compile platform and growth-goal choices into phase-specific rules."""
    if phase not in _PHASES:
        raise ValueError(f"不支持的生成阶段：{phase}")

    platform = normalize_platform(platform)
    goal = normalize_goal(goal)
    header = (
        "\n\n【平台与获客目标规则】"
        f"\n发布平台：{PLATFORM_NAMES[platform]}（{platform}）"
        f"\n获客目标：{GOAL_NAMES[goal]}（{goal}）"
    )
    phase_rules = {
        "outline": (
            "\n大纲阶段：根据平台的阅读场景安排开场、页序、信息密度和收束方式；"
            "根据获客目标决定价值证明、信任信息和下一步行动的出现位置。"
            "保持主题事实、数字、步骤和结论不变，不为了转化补写产品承诺。"
        ),
        "copy": (
            "\n文案阶段：根据平台调整开头节奏、段落长度和扫读结构；"
            "根据获客目标安排自然的关注、种草、咨询、转化、品牌或互动行动号召。"
            "行动号召必须与主题和页面事实相符，不制造稀缺、效果或用户证言。"
        ),
        "image": (
            "\n图片阶段：根据平台调整首屏重点、安全区、文字密度和阅读方向；"
            "根据获客目标突出价值、证据或行动区域，但不牺牲页面事实和可读性。"
            "平台名称、获客目标名称、平台 ID、目标 ID、规则标题以及其他内部参数"
            "只能作为生成约束，不得渲染（禁止渲染）为图片中的可见文字。"
        ),
    }
    risk_phase_rules = {
        "outline": OUTLINE_RISK_RULES,
        "copy": COPY_RISK_RULES,
        "image": IMAGE_RISK_RULES,
    }
    return (
        header + COMMON_RISK_RULES + "\n" + PLATFORM_RULES[platform]
        + "\n" + GOAL_RULES[goal] + phase_rules[phase] + risk_phase_rules[phase]
    )


def build_generation_context(
    topic,
    outline,
    generation_preferences,
    copy_preferences,
    image_style,
    page=None,
):
    """Build normalized context shared by outline, copy and image stages."""
    generation_preferences = _mapping(generation_preferences)
    copy_preferences = _mapping(copy_preferences)
    image_style = _mapping(image_style)
    page = _mapping(page)
    platform = normalize_platform(generation_preferences.get("platform"))
    goal = normalize_goal(generation_preferences.get("goal"))

    content = {
        key: generation_preferences.get(key)
        for key in ("organization", "audience", "audience_detail", "tone", "page_count",
                    "content_form", "information_density")
        if generation_preferences.get(key) is not None
    }
    content.update({
        key: copy_preferences.get(key)
        for key in ("style", "structure", "length", "emoji_level")
        if copy_preferences.get(key) is not None
    })
    visual = {
        "image_style": dict(image_style),
        "layout": page.get("layout") or page.get("page_layout") or "自动",
        "page_type": page.get("type") or "",
    }
    growth = {"platform": platform, "goal": goal}
    return {
        "topic": str(topic or "").strip(),
        "outline": outline if isinstance(outline, str) else "",
        "content": content,
        "visual": visual,
        "growth": growth,
        "page": dict(page),
        "prompt_rules": {
            phase: growth_prompt_rules(platform, goal, phase)
                + content_structure_rule(generation_preferences.get("organization"), phase, copy_preferences)
                + outline_mode_rule(generation_preferences, phase)
            for phase in _PHASES
        },
    }


def content_structure_rule(organization, phase, copy_preferences=None):
    if not organization or organization == "自动" or phase == "outline":
        return ""
    from prompts.catalog_runtime import option
    entry = option("outline", "organization", organization)
    rule = f"\n\n【整套内容结构】{entry['name']}：{entry['content']}"
    if phase == "image":
        return rule + "本页遵循既定大纲中的角色与顺序；不得在一张图中重写整套内容，不把结构名称和规则画进图片。"
    structure = (copy_preferences or {}).get("structure", "自动")
    if structure == "自动":
        return rule + "正文结构跟随整套内容结构与既有页序，允许按篇幅压缩，但保留事实、结论和必要边界。"
    return rule + "整套结构作为内容背景；正文的排列以用户明确选择的正文结构为准，不改变核心事实与结论。"


def outline_mode_rule(preferences, phase):
    if phase not in ("outline", "copy", "image"):
        return ""
    form = normalize_content_form(preferences.get("content_form"))
    density = normalize_information_density(preferences.get("information_density"))
    prefix = "\n\n【内容形态与信息密度】"
    if form == "single_infographic":
        prefix += "这是单页知识信息图："
        if phase == "image":
            prefix += "整张图承担完整阅读路径，按标题、模块、流程或关系、结论分层，避免把多页卡片缩成难以阅读的小字。"
        elif phase == "copy":
            prefix += "文案围绕一张图的模块顺序补充解释，不重复堆砌所有图中文字。"
        else:
            prefix += "只输出一个信息图页面，页面内形成从主题引入到核心内容再到总结的完整层级。"
    return prefix + f"\n内容形态：{CONTENT_FORMS[form]['prompt']}\n信息密度：{DENSITIES[density]['prompt']}"


def audit_context(context):
    """Return field-level usage records for prompt coverage checks."""
    context = _mapping(context)
    growth = _mapping(context.get("growth"))
    content = _mapping(context.get("content"))
    visual = _mapping(context.get("visual"))
    entries = []

    for phase in _PHASES:
        for field in ("platform", "goal"):
            value = growth.get(field, "auto")
            entries.append({
                "phase": phase,
                "field": field,
                "value": value,
                "applied": bool(_mapping(context.get("prompt_rules")).get(phase)),
                "verification": "compiled_rule_only",
                "output_verified": False,
            })

    phase_fields = {
        "outline": content,
        "copy": {key: content.get(key) for key in ("style", "structure", "length", "emoji_level")},
        "image": visual,
    }
    for phase, fields in phase_fields.items():
        for field, value in fields.items():
            entries.append({
                "phase": phase,
                "field": field,
                "value": value,
                "applied": value not in (None, ""),
                "verification": "configured_value_only",
                "output_verified": False,
            })
    return entries
