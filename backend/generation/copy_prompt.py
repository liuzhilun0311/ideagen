from django.http import JsonResponse
from common.api import require_auth, api_error_response, json_body
from prompts.services import safe_format
from .outline_prompt import catalog_base, catalog_option, preferences, expression_instruction
from .catalog import catalog_request
from .generation_context import build_generation_context

STYLES = {
    "自动": "根据主题和目标受众选择自然的表达。",
    "自然分享": "自然口语，像向读者分享建议；不虚构亲测或个人经历。",
    "简洁干货": "直接表达重点，少铺垫，每个要点包含具体信息。",
    "专业科普": "准确解释概念，说明适用边界，避免堆砌术语。",
    "温柔鼓励": "体谅读者处境，温和鼓励，不说教或过度承诺。",
    "轻松幽默": "适量使用轻松比喻，不能改变事实或拿严肃风险开玩笑。",
}
STRUCTURES = {
    "自动": "根据内容选择一种适合的正文结构。",
    "要点清单": "适用场景开场，分点列出短标签和解释，最后给行动建议。",
    "步骤说明": "说明目标，按素材中有依据的顺序列步骤，最后给提醒。",
    "问题解答": "围绕读者的问题分组问答，回答仅基于页面事实。",
    "对比分析": "按素材支持的维度比较，说明各自适用情形；不虚构对比数据。",
    "故事串联": "用问题、理解、行动串联已有内容；不得虚构人物、事件或亲身经历。",
}
LENGTHS = {"简短": "100至200", "适中": "300至500", "详细": "600至900"}
EMOJI_RULES = {
    "无": "不使用任何 emoji 或装饰性符号；需要列举时使用普通数字编号或短横线，保留必要标点、单位和数学符号。",
    "克制": "正文使用0至3个与主题相关的 emoji，少量搭配圈号编号或提示符号，仅在段落引导、重点或行动提醒处使用。",
    "丰富": (
        "主动搭配主题相关的 emoji 与信息符号，不要只在结尾放一个表情。"
        "正文至少使用一种与信息相关的表情或信息符号，不要全部退回普通数字、短横线或纯文字。"
        "步骤或有序清单优先使用键帽数字表情1️⃣ 2️⃣ 3️⃣ 4️⃣作为列表序号，不再使用普通1、2、3、4或圈号①②③④；"
        "平台不适合键帽表情时再使用圈号编号。同级编号保持统一，超过9项不要重新从1编号。"
        "简短正文建议3至5个、适中正文6至10个、详细正文10至16个 emoji（编号和普通符号不计入），"
        "分散在开场、主要段落和行动提醒处；多数主要段落使用1至2个，避免连续堆砌或机械重复。"
        "数量是软目标，短素材、专业语气和平台限制优先，不为凑数增加段落、事实或无关表情。"
    ),
}
EMOJI_REFERENCES = (
    "\n表情参考库（按主题选择，不要把分类或整串示例原样输出）："
    "\n人脸情绪：😀 😄 😅 😂 😊 😉 😍 🥰 🧐 🥺 😴；用来传达自然情绪，不虚构亲身感受。"
    "\n动物：🐶 🐱 🐰 🦊 🐼 🐨 🐸 🐧 🐢 🐳 🦋 🐝；仅用于相关动物、宠物或自然主题。"
    "\n食物：🍎 🍋 🍌 🍉 🍓 🫐 🥝 🥕 🍞 🥐 🍕 🍜 🍰 ☕ 🍵。"
    "\n物品与场景：🏠 🏫 🚗 🚲 ✈️ 🚀 ⚽ 🎮 📱 💻 📷 📖 📝 ✏️ 🎁。"
    "\n手势与爱心：👍 ✌️ 🙌 🙏 👌 🫶 ❤️ 💛 💚 💙 💜 💕 💖。"
    "\n自然天气：☀️ 🌤️ ☁️ 🌧️ ❄️ ⚡ 🌈 🌙 ⭐ ✨ 🔥 🌊 🌸 🌷 🪻 🌻。"
    "\n信息符号：步骤编号可选①②③④或1️⃣2️⃣3️⃣4️⃣；勾选用✓，方向用→，无序要点用•。"
    "同级列表统一使用一种编号或项目符号；可另外搭配相关 emoji 和重点提示符号，"
    "“一种信息标记方式”仅约束同级列表的标记，不禁止其他位置的提示符号。"
    "只替换列表序号，不替换事实中的数字、日期、数量、价格或单位；表情不能替代关键信息。"
)


def copy_preferences(value=None):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("文案选项格式无效")
    result = {}
    for key, choices, default in (
        ("style", STYLES, "自动"), ("structure", STRUCTURES, "自动"),
        ("length", LENGTHS, "适中"),
    ):
        selected = value.get(key, default)
        if not isinstance(selected, str):
            raise ValueError(f"无效的文案选项：{key}")
        entry = catalog_option("content", key, selected)
        result[key] = entry.get("legacy_value") or entry["id"]
    emoji_level = value.get("emoji_level", "克制")
    if emoji_level not in ("无", "克制", "丰富"):
        raise ValueError("无效的文案选项：emoji_level")
    result["emoji_level"] = emoji_level
    return result


def build_copy_prompt(data):
    topic, outline = data.get("topic"), data.get("outline")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("请填写主题")
    if not isinstance(outline, str) or not outline.strip():
        raise ValueError("请先生成页面内容")
    options = copy_preferences(data.get("copy_preferences"))
    audience = preferences(data.get("generation_preferences") or {})
    context = build_generation_context(topic, outline, audience, options, {})
    prompt = safe_format(catalog_base("content"), {"topic": topic, "outline": outline})
    style_entry = catalog_option("content", "style", options["style"])
    structure_entry = catalog_option("content", "structure", options["structure"])
    length_entry = catalog_option("content", "length", options["length"])
    prompt += expression_instruction(audience, style_entry if options["style"] != "自动" else None)
    if options["style"] != "自动":
        audience = {**audience, "tone": style_entry["name"]}
    prompt += (
        f'\n文案风格：{style_entry["name"]}。{style_entry["content"]}'
        f'\n正文结构：{structure_entry["name"]}。'
        + ("跟随整套内容结构与既有页面顺序；没有明确结构时根据内容选择。"
           if options["structure"] == "自动" else structure_entry["content"])
        + (
        f'\n文案长度：{length_entry["name"]}，{length_entry["content"]}（不含标题和标签）。'
        '这是软目标；素材不足时允许更短，不为凑字数编造内容。按长度安排短段落，不固定段数。'
        f'\n表情与符号丰富度：{options["emoji_level"]}。'
        f'{EMOJI_RULES[options["emoji_level"]]}'
        '医疗、法律、财务和严肃风险主题避免搞笑、夸张、庆祝或淡化风险的表情；'
        '未选择“无”时，允许中性编号和提示符号，例如1️⃣、✅、📌、🏠。'
        '严肃主题的“丰富”优先用这些中性标记，不要求凑满情绪表情数量，也不应完全省略信息符号。'
        '选择“无”时仍不使用emoji或装饰性符号。符号不得代替风险说明，也不得暗示安全、功效或收益保证。'
        '\n以上选项控制表达，不改变页面事实、数字和结论；不要输出这些制作指令。'
        )
    )
    if options["emoji_level"] != "无":
        prompt += EMOJI_REFERENCES
    prompt += context["prompt_rules"]["copy"]
    prompt += '\n输出协议：仅输出 JSON 对象，字段 titles 为字符串数组、copywriting 为正文字符串、tags 为字符串数组。'
    return prompt, {k: v for k, v in options.items() if not k.startswith("_")}, audience


@require_auth
@catalog_request
def preview(request):
    if request.method != "POST":
        return api_error_response("请求方法不支持", status=405)
    try:
        prompt, options, audience = build_copy_prompt(json_body(request))
        response = JsonResponse({"success": True, "prompt": prompt,
                                 "preferences": options, "audience": audience})
        response["Cache-Control"] = "no-store"
        return response
    except (ValueError, TypeError, AttributeError) as error:
        return api_error_response(str(error), status=400)
