"""Builtin seed data, kept independent of generation modules to avoid import cycles."""
import json
from pathlib import Path
from .scene_descriptions import SCENES

ROOT = Path(__file__).resolve().parent.parent / "generation"
LAYOUT_PREVIEW_ROOT = ROOT.parent.parent / "frontend" / "public" / "assets" / "layouts"
CATEGORIES = [
    {"module": module, "category": key, "label": label}
    for module, categories in (
        ("outline", (("base", "基础规则"), ("organization", "组织方式"), ("audience", "目标受众"), ("tone", "表达语气"))),
        ("image", (("base", "基础规则"), ("layout", "单页布局"), ("style", "图片风格"))),
        ("content", (("base", "基础规则"), ("style", "文案风格"), ("structure", "正文结构"), ("length", "文案长度"))),
    ) for key, label in categories
]
BUILTIN_GROUPS = {
    ("outline", "organization"): [
        ("自动", "根据主题选择适合整套内容的组织方式。"),
        ("分类递进", "先展示分类全貌，再分组展开，由基础信息递进到应用。"),
        ("步骤教程", "按可执行的先后顺序讲解，每页聚焦一个阶段及必要提醒。"),
        ("问题解决", "从具体问题出发，解释原因，给出有依据的解决办法与行动。"),
        ("对比决策", "围绕统一维度比较选项，最后说明各自适用情境，不编造对比数据。"),
        ("概念到例子", "先解释概念，再用素材支持的例子帮助理解，最后总结应用。"),
        ("故事时间线", "按素材中真实存在的时间与事件推进，不虚构人物和经历。"),
        ("清单合集", "先说明清单适用范围，再按同一标准组织各条要点，避免重复。"),
        ("误区纠正", "提出常见误区，依据资料解释真相，给出正确做法与适用边界。不编造流行观点。"),
        ("案例拆解", "按背景、问题、做法、结果与可借鉴之处拆解已有案例；缺少结果时明确未知，不虚构成功。"),
        ("产品种草", "从真实使用场景出发，讲清特点、收益、证据与限制，再给适用人群建议，不虚构亲测。"),
        ("观点论证", "提出观点，展开有依据的理由和例子，说明反例或边界，最后总结，不编造数据或引用。"),
    ],
    ("outline", "audience"): [
        ("自动判断", "根据主题判断目标读者和解释深度。"),
        ("零基础入门", "面向零基础读者，解释必要术语，从基础概念开始。"),
        ("有一定基础", "面向已有基础的读者，减少常识铺垫，突出方法与应用细节。"),
        ("专业读者", "面向专业读者，保持术语准确，强调适用边界，不凭空增加技术事实。"),
        ("自定义", "面向用户明确填写的读者，调整解释深度与例子，不改变事实。"),
    ],
    ("outline", "tone"): [
        ("自动匹配", "根据主题和读者选择合适口吻。"),
        ("亲切易懂", "使用自然亲切、容易理解的表达，避免居高临下。"),
        ("专业简洁", "准确直接、信息清楚，减少不必要的修饰。"),
        ("轻松幽默", "允许轻松表达和适量比喻，不拿严肃风险开玩笑。"),
        ("温柔鼓励", "体谅读者，温和鼓励，不说教或过度承诺。"),
    ],
    ("image", "layout"): [
        ("自动", "按本页文字与信息关系选择清楚、适合阅读的布局。"),
        ("封面", "突出主标题与一个视觉主体，副标题次之，保留安全边距。"),
        ("清单", "以等距排列的条目组织信息，编号和短标签对齐。"),
        ("步骤", "沿清晰的阅读路径展示顺序，箭头只表达有依据的先后关系。"),
        ("对比", "将比较对象并列，维度对齐，保持视觉权重相当。"),
        ("分类", "按同级类别分组，组间清楚，组内层级一致。"),
        ("关系", "以主体、连线和标签表达素材支持的关系，不添加不存在的因果。"),
        ("例子", "让示例主体与对应解释明确关联，不编造事实。"),
        ("总结", "收束核心结论，减少次要装饰，突出可执行提醒。"),
    ],
    ("content", "style"): [
        ("自动", "根据主题和目标受众选择自然的表达。"),
        ("自然分享", "自然口语，像向读者分享建议；不虚构亲测或个人经历。"),
        ("简洁干货", "直接表达重点，少铺垫，每个要点包含具体信息。"),
        ("专业科普", "准确解释概念，说明适用边界，避免堆砌术语。"),
        ("温柔鼓励", "体谅读者处境，温和鼓励，不说教或过度承诺。"),
        ("轻松幽默", "适量使用轻松比喻，不能改变事实或拿严肃风险开玩笑。"),
    ],
    ("content", "structure"): [
        ("自动", "根据内容选择一种适合的正文结构。"),
        ("要点清单", "适用场景开场，分点列出短标签和解释，最后给行动建议。"),
        ("步骤说明", "说明目标，按素材中有依据的顺序列步骤，最后给提醒。"),
        ("问题解答", "围绕读者的问题分组问答，回答仅基于页面事实。"),
        ("对比分析", "按素材支持的维度比较，说明各自适用情形；不虚构对比数据。"),
        ("故事串联", "用问题、理解、行动串联已有内容；不得虚构人物、事件或亲身经历。"),
    ],
    ("content", "length"): [
        ("简短", "正文约100至200字，不含标题和标签。"),
        ("适中", "正文约300至500字，不含标题和标签。"),
        ("详细", "正文约600至900字，不含标题和标签。"),
    ],
}

LEGACY_LAYOUT_METADATA = {
    "自动": {
        "layout_group": "role",
        "preview": "summary",
        "preview_alt": "根据内容自动选择页面排版结构，示例展示标题、正文和视觉主体的清晰分区。",
        "summary": "根据本页信息关系自动选择清晰、适合阅读的页面结构。",
    },
    "封面": {
        "layout_group": "role",
        "preview": "cover",
        "preview_alt": "主标题与视觉主体集中在页面中央，副标题次级呈现并保留安全边距。",
        "summary": "突出主标题与一个视觉主体，适合内容开场和主题建立。",
    },
    "清单": {
        "layout_group": "information",
        "preview": "list",
        "preview_alt": "多个编号条目纵向排列，短标签和说明形成清晰的层级关系。",
        "summary": "以等距排列的条目组织信息，适合要点、资源和检查项。",
    },
    "步骤": {
        "layout_group": "information",
        "preview": "steps",
        "preview_alt": "步骤节点沿明确阅读路径排列，并用方向关系表达先后顺序。",
        "summary": "沿清晰的阅读路径展示顺序，适合教程和流程说明。",
    },
    "对比": {
        "layout_group": "information",
        "preview": "compare",
        "preview_alt": "两个或多个对象分栏并列，比较维度横向对齐且视觉权重相当。",
        "summary": "将比较对象并列，适合差异、选择和方案分析。",
    },
    "分类": {
        "layout_group": "information",
        "preview": "category",
        "preview_alt": "内容按多个同级类别分区呈现，组间分隔清楚且组内层级一致。",
        "summary": "按同级类别分组，适合整理主题、类型和场景。",
    },
    "关系": {
        "layout_group": "information",
        "preview": "relation",
        "preview_alt": "中心主体与周边关联元素通过连线和标签建立关系，避免无依据的因果表达。",
        "summary": "以主体、连线和标签表达信息关系，适合结构和关联说明。",
    },
    "例子": {
        "layout_group": "information",
        "preview": "example",
        "preview_alt": "示例主体与对应解释文本成组排列，突出具体应用场景和理解入口。",
        "summary": "让示例主体与对应解释明确关联，适合概念到应用。",
    },
    "总结": {
        "layout_group": "role",
        "preview": "summary",
        "preview_alt": "核心结论置于视觉中心，下方保留关键提醒或下一步行动区域。",
        "summary": "收束核心结论，适合总结、复盘和行动提醒。",
    },
}

GROWTH_LAYOUT_PREVIEW_ALT = {
    "hook-cover": "大标题占据首屏主要区域，痛点或结果形成视觉焦点，下方保留主体和安全边距。",
    "pain-solution": "页面分成痛点区和方案区，两个信息块沿明确阅读路径前后衔接。",
    "myth-fact": "误区与真相采用对照分区，标签和结论形成清楚的视觉反差。",
    "before-after": "变化前后或两种状态左右并列，比较维度保持对齐。",
    "case-study": "案例背景、问题、做法和结果按阶段分区，形成从事实到结论的阅读路径。",
    "product-benefits": "产品主体位于视觉中心，周围围绕用户收益和使用场景组织信息。",
    "proof": "评价、数据或证据作为主体突出展示，补充说明放在周边并保留来源位置。",
    "faq": "多个问题以问答卡片或分区排列，每个问题对应一段简短直接的回答。",
    "data-conclusion": "关键数字或趋势图表位于主体区域，结论和必要说明形成上下层级。",
    "quote": "核心观点以大字号置于视觉中心，来源和补充解释作为次级信息排列。",
    "chapter-divider": "章节标题和简短导语集中在页面主区域，用留白提示内容转折和阅读节奏。",
    "cta": "核心行动指令位于视觉中心，辅助说明和行动入口集中在底部安全区域。",
    "talking-subtitle": "人物或主体保留在画面一侧，分层字幕位于安全区，避免遮挡关键信息。",
    "product-demo": "产品主体、操作步骤和结果按顺序排列，形成从操作到收益的演示路径。",
    "comment-proof": "评论、私信或聊天内容作为主体展示，保留上下文、隐私处理和回应关系。",
}

LAYOUT_GROUP_BY_NAME = {
    "自动": "role",
    "封面": "role",
    "清单": "information",
    "步骤": "information",
    "对比": "information",
    "分类": "information",
    "关系": "information",
    "例子": "information",
    "总结": "role",
    "强钩子封面": "growth",
    "痛点—方案": "growth",
    "误区—真相": "growth",
    "前后对比": "growth",
    "案例拆解": "growth",
    "产品卖点": "growth",
    "用户评价/证据": "growth",
    "FAQ问答": "growth",
    "数据结论": "growth",
    "金句观点": "growth",
    "章节分隔": "role",
    "行动号召页": "growth",
    "口播字幕页": "media",
    "产品演示页": "media",
    "评论/聊天截图页": "media",
}
LAYOUT_GROUP_BY_NAME.update({
    "hook-cover": "growth",
    "pain-solution": "growth",
    "myth-fact": "growth",
    "before-after": "growth",
    "case-study": "growth",
    "product-benefits": "growth",
    "proof": "growth",
    "faq": "growth",
    "data-conclusion": "growth",
    "quote": "growth",
    "chapter-divider": "role",
    "cta": "growth",
    "talking-subtitle": "media",
    "product-demo": "media",
    "comment-proof": "media",
})
VALID_LAYOUT_GROUPS = frozenset(("role", "information", "growth", "media"))


def validate_builtin_layout_previews(entries):
    """Validate the shared metadata and local assets used by built-in layouts."""
    layouts = [
        entry for entry in entries
        if entry.get("module") == "image" and entry.get("category") == "layout"
    ]
    errors = []
    seen = set()
    for entry in layouts:
        if entry.get("legacy_value") == "自动":
            continue
        metadata = entry.get("metadata") or {}
        if metadata.get("layout_group") not in VALID_LAYOUT_GROUPS:
            errors.append(f'{entry.get("id")}: 单页布局分类无效')
        missing = [
            field for field in ("preview", "preview_alt", "summary")
            if not isinstance(metadata.get(field), str) or not metadata[field].strip()
        ]
        if missing:
            errors.append(f'{entry.get("id")}: 缺少 {", ".join(missing)}')
            continue
        preview = metadata["preview"]
        if preview in seen:
            errors.append(f"{entry.get('id')}: 样图标识重复 {preview}")
        seen.add(preview)
        asset = LAYOUT_PREVIEW_ROOT / f"{preview}.png"
        if not asset.is_file():
            errors.append(f"{entry.get('id')}: 样图文件不存在 {asset}")
    if errors:
        raise ValueError("内置单页布局样图契约无效：" + "；".join(errors))


def builtin_entries(current_base=True):
    result = []
    def add(module, category, key, name, content, legacy="", metadata=None, description=""):
        description = SCENES.get((module, category), {}).get(name, description)
        metadata = dict(metadata or {})
        if module == "image" and category == "layout":
            metadata.setdefault("layout_group", LAYOUT_GROUP_BY_NAME.get(name, "role"))
        result.append({
            "id": f"{module}.{category}.{key}", "module": module, "category": category,
            "name": name, "content": content, "description": description,
            "legacy_value": legacy, "metadata": metadata,
            "builtin": True, "enabled": True, "visibility": "public", "allowed_users": [],
        })
    for module in ("outline", "image", "content"):
        if current_base:
            from .services import get_base_prompt
            text = get_base_prompt(module)
        else:
            text = (ROOT / "prompts" / f"{module}_prompt.txt").read_text(encoding="utf-8")
        add(module, "base", "default", "基础规则", text)
    for (module, category), items in BUILTIN_GROUPS.items():
        for index, (name, instruction) in enumerate(items):
            metadata = {}
            if module == "image" and category == "layout":
                metadata = dict(LEGACY_LAYOUT_METADATA[name])
            add(module, category, str(index), name, instruction, legacy=name, metadata=metadata)
    growth_layouts = [
        ("hook-cover", "强钩子封面", "用一个明确痛点、结果或反常识观点建立首屏注意力，标题短而醒目。",
         ["xiaohongshu", "douyin", "multi"], ["follow", "product", "inquiry"], ["3:4", "9:16"], "high",
         "适合首屏吸引停留，突出问题、结果或反常识观点。"),
        ("pain-solution", "痛点—方案", "先呈现用户痛点，再给出对应方法或解决方案，形成清晰阅读路径。",
         ["xiaohongshu", "douyin", "wechat", "multi"], ["product", "inquiry", "conversion"], ["3:4", "9:16", "1:1"], "medium",
         "适合把用户问题自然连接到方法、产品或服务。"),
        ("myth-fact", "误区—真相", "并列展示常见误区与基于正文的真实判断，避免制造未经支持的结论。",
         ["xiaohongshu", "douyin", "wechat", "multi"], ["follow", "brand", "engagement"], ["3:4", "9:16"], "medium",
         "适合知识澄清、反常识内容和评论讨论。"),
        ("before-after", "前后对比", "将变化前后或两种状态并列呈现，对齐比较维度，不凭空增加效果数据。",
         ["xiaohongshu", "douyin", "multi"], ["product", "conversion", "engagement"], ["3:4", "9:16"], "medium",
         "适合展示体验变化、方法效果或方案差异。"),
        ("case-study", "案例拆解", "按背景、问题、做法和结果组织案例，只使用正文中已有的案例事实。",
         ["xiaohongshu", "douyin", "wechat", "multi"], ["inquiry", "conversion", "brand"], ["3:4", "9:16", "1:1"], "high",
         "适合建立专业信任，推动用户进一步咨询。"),
        ("product-benefits", "产品卖点", "围绕用户收益组织产品特点、使用场景和适用边界，避免堆砌规格。",
         ["xiaohongshu", "douyin", "multi"], ["product", "conversion"], ["3:4", "9:16", "1:1"], "medium",
         "适合把产品特点翻译成用户能理解的实际收益。"),
        ("proof", "用户评价/证据", "突出评价、数据或可核验证据，并标明证据来源或适用范围。",
         ["xiaohongshu", "douyin", "wechat", "multi"], ["inquiry", "conversion", "brand"], ["3:4", "9:16", "1:1"], "high",
         "适合降低决策风险，但不能虚构用户反馈或数据。"),
        ("faq", "FAQ问答", "以用户问题为标题，给出简短直接的回答，适合连续解决疑虑。",
         ["xiaohongshu", "douyin", "wechat", "multi"], ["follow", "inquiry", "engagement"], ["3:4", "9:16", "1:1"], "medium",
         "适合处理购买前、咨询前和评论区常见问题。"),
        ("data-conclusion", "数据结论", "突出已有数据和结论，图表只表达正文提供的信息，不补造统计关系。",
         ["douyin", "wechat", "multi"], ["brand", "conversion", "follow"], ["3:4", "9:16", "1:1"], "high",
         "适合用事实、趋势或关键数字支撑观点。"),
        ("quote", "金句观点", "以一句核心观点为视觉中心，辅以必要解释和来源，不让装饰抢过文字。",
         ["xiaohongshu", "douyin", "wechat", "multi"], ["follow", "brand", "engagement"], ["3:4", "9:16", "1:1"], "low",
         "适合观点传播、收藏和转发。"),
        ("chapter-divider", "章节分隔", "用章节标题和简短导语提示内容转折，保持整套内容的阅读节奏。",
         ["wechat", "multi"], ["brand", "follow"], ["3:4", "1:1", "16:9"], "low",
         "适合公众号长文和系列内容分段。"),
        ("cta", "行动号召页", "明确告诉用户下一步可以做什么，行动与正文和获客目标保持一致。",
         ["xiaohongshu", "douyin", "wechat", "multi"], ["follow", "inquiry", "conversion", "engagement"], ["3:4", "9:16", "1:1"], "low",
         "适合关注、收藏、评论、私信或咨询引导。"),
        ("talking-subtitle", "口播字幕页", "为竖屏口播保留人物或主体空间，字幕分层清楚，避免文字压住关键信息。",
         ["douyin", "multi"], ["follow", "inquiry", "conversion"], ["9:16"], "high",
         "适合抖音口播、知识讲解和字幕卡点。"),
        ("product-demo", "产品演示页", "按操作顺序突出产品主体、步骤和结果，避免添加正文没有的功能。",
         ["douyin", "xiaohongshu", "multi"], ["product", "conversion", "inquiry"], ["9:16", "3:4", "1:1"], "high",
         "适合展示产品怎么用、怎么选和怎么产生结果。"),
        ("comment-proof", "评论/聊天截图页", "以评论、私信或聊天证据为视觉主体，保留上下文和隐私安全边界。",
         ["xiaohongshu", "douyin", "multi"], ["engagement", "inquiry", "conversion"], ["3:4", "9:16"], "high",
         "适合展示真实互动和问题反馈，不伪造聊天记录。"),
    ]
    for key, name, instruction, platforms, goals, ratios, density, summary in growth_layouts:
        add("image", "layout", key, name, instruction, legacy=key, metadata={
            "layout_group": LAYOUT_GROUP_BY_NAME[key],
            "platforms": platforms, "goals": goals, "aspect_ratios": ratios,
            "text_density": density, "summary": summary, "preview": key,
            "preview_alt": GROWTH_LAYOUT_PREVIEW_ALT[key],
        }, description=f"适合：{summary} 视觉重点：{instruction}")
    add("image", "style", "auto", "自动推荐", "根据内容从当前用户可用风格中推荐。",
        legacy="auto", metadata={"color": "#5b6472", "group": "推荐", "preview": "auto"},
        description="适合首次探索视觉方向或尚未确定系列画风的主题。按内容从可用风格中推荐；已有品牌规范或需要整套视觉统一时，建议手动指定一种风格。")
    for item in json.loads((ROOT / "style_catalog.json").read_text(encoding="utf-8")):
        add("image", "style", item["id"], item["name"], item["direction"], legacy=item["id"],
            metadata={key: value for key, value in item.items() if key not in ("id", "name", "direction")},
            description=f'适合：{item["scenes"]}。视觉特点：{item["detail"]}。选择时注意：{item["caution"]}。')
    return result
