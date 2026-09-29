"""Request-scoped art direction, independent of content and provider selection."""
import json
import re
from pathlib import Path
from prompts.catalog_runtime import option, options, resolve_layout_entry, snapshot
from .palettes import normalize_palette, palette_rule


def alias(entry):
    return entry.get("legacy_value") or entry["id"]


def available_styles():
    return {alias(entry): entry for entry in options("image", "style")
            if entry.get("legacy_value") != "auto"}


class FrozenImageTemplate(str):
    """All catalog state is copied before SSE or worker execution."""
    def __new__(cls, text, generation_context=None):
        value = super().__new__(cls, text)
        value.layouts = options("image", "layout")
        value.catalog_snapshot = snapshot()
        value.generation_context = generation_context
        return value

    def layout_entry(self, content):
        match = re.search(r'单页布局\s*[:：]\s*([^\n]+)', content)
        selected = match.group(1).strip() if match else "自动"
        return resolve_layout_entry(self.layouts, selected)

    def audit(self, content):
        return [*self.catalog_snapshot, self.layout_entry(content)]


def validate_image_pages(template, pages):
    from .structure import image_page_content
    for page in pages:
        template.layout_entry(image_page_content(page))

CATALOG = json.loads(Path(__file__).with_name('style_catalog.json').read_text(encoding='utf-8'))
# Keep catalog IDs, recommendations and UI choices backed by one source.
STYLE_DIRECTIONS = {'auto': '', **{item['id']: item['direction'] for item in CATALOG}}


def normalize_recommendation(value):
    available = available_styles()
    keys = {entry["id"]: key for key, entry in available.items()}
    if not isinstance(value, dict) or not isinstance(value.get('preset'), str):
        return None
    preset = keys.get(value["preset"], value["preset"])
    if preset not in available:
        return None
    alternatives = value.get('alternatives', [])
    if not isinstance(alternatives, list):
        alternatives = []
    return {
        'preset': preset,
        'reason': str(value.get('reason', ''))[:180],
        'alternatives': list(dict.fromkeys(keys.get(p, p) for p in alternatives if isinstance(p, str)
                                         and keys.get(p, p) in available and keys.get(p, p) != preset))[:2],
    }


def _legacy_recommendation(topic=''):
    groups = [
        (r'学习|笔记|复习|记忆|备考', 'sketch-note', '以手绘图解组织学习重点。', ['whiteboard', 'infographic']),
        (r'儿童|亲子|幼儿', 'chibi', '以简洁角色帮助理解，减少阅读负担。', ['crayon', 'clay']),
        (r'历史|节气|传统|古诗|民俗', 'modern-chinese', '以现代国风表达文化主题。', ['ink', 'woodcut']),
        (r'植物|花卉|自然|情绪', 'watercolor', '以柔和插画表现自然或情绪主题。', ['pencil', 'minimal']),
        (r'旅行|城市|美食|收纳|物品', 'photography', '以具象主体呈现场景或物品。', ['collage', 'sketch-note']),
    ]
    for pattern, preset, reason, alternatives in groups:
        if re.search(pattern, topic):
            return {'preset': preset, 'reason': reason + '（规则推荐）', 'alternatives': alternatives}
    return {'preset': 'infographic', 'reason': '优先清楚表达要点、步骤与关系。（规则推荐）',
            'alternatives': ['comic', 'sketch-note']}


def fallback_recommendation(topic=''):
    available = available_styles()
    if not available:
        raise ValueError("没有可用的图片风格，请先启用一种风格。")
    rec = _legacy_recommendation(topic)
    rec["preset"] = rec["preset"] if rec["preset"] in available else next(iter(available))
    rec["alternatives"] = [key for key in rec["alternatives"] if key in available and key != rec["preset"]]
    return rec


def recommendation_instruction():
    current = options("image", "style")
    choices = '\n'.join(
        f"{alias(s)}：{s['name']}；适用平台：{','.join(s.get('metadata', {}).get('platforms', [])) or '通用'}；"
        f"获客目标：{','.join(s.get('metadata', {}).get('goals', [])) or '通用'}；"
        f"场景：{s.get('metadata', {}).get('scenes', s.get('description', ''))}"
        for s in current if s.get("legacy_value") != "auto"
    )
    return (
        '\n\n【独立风格推荐元数据】\n根据读者、主题和信息结构，从下列目录选一个最适合整套的风格，'
        '不要总是选同一风格。风格只是建议，不在页面画面描述中固定媒介或配色；由用户最终选择决定。'
        '在所有页面之后另起一行输出 <style-recommendation>JSON</style-recommendation>。'
        'JSON 字段为 preset（目录ID）、reason（80字以内理由）、alternatives（两个不同备选ID）。'
        '该元数据不是页面，不得写进上图文字。\n' + choices
    )


def extract_recommendation(text, topic):
    match = re.search(r'<style-recommendation>\s*(.*?)\s*</style-recommendation>', text, re.S | re.I)
    result = None
    if match:
        try:
            result = normalize_recommendation(json.loads(match.group(1)))
        except (ValueError, TypeError):
            pass
    # A truncated metadata block must not leak into the last page.
    clean = re.sub(r'<style-recommendation>.*?(?:</style-recommendation>|$)', '', text, flags=re.S | re.I).strip()
    return clean, result or fallback_recommendation(topic)


def resolve_style(value, recommendation=None):
    style = normalize_style(value)
    if style['preset'] == 'auto':
        rec = normalize_recommendation(recommendation) or style.get('recommendation') or fallback_recommendation()
        style['preset'] = rec['preset']
    return {'preset': style['preset'], 'notes': style['notes'],
            **({'palette': style['palette']} if 'palette' in style else {})}


def neutral_visual_context(text):
    """Strip explicit old art-direction fields, never the printable text."""
    parts = re.split(r'(<page>)', text, flags=re.I)
    for index, part in enumerate(parts):
        match = re.search(r'(?:画面描述|配图建议|视觉说明)\s*[:：]', part)
        if not match:
            continue
        visual = part[match.end():]
        visual = re.sub(
            r'(?m)^[ \t]*(?:[-*]\s*)?(?:推荐风格|图片风格|画风|绘画风格|风格|配色方案|主色调|渲染方式)\s*[:：][^\n]*',
            '', visual,
        )
        parts[index] = part[:match.end()] + visual
    return ''.join(parts)


def format_image_prompt(template, values):
    from prompts.services import safe_format
    layouts = getattr(template, "layouts", None)
    context = values.get("generation_context") or getattr(template, "generation_context", None)
    layout_rule = ""
    if layouts is not None:
        entry = template.layout_entry(values.get("page_content", ""))
        layout_rule = f'\n单页布局规则：{entry["name"]}。{entry["content"]}'
    # Full-set text is not needed to render one page, including saved legacy templates.
    template = re.sub(r'(?m)^[ \t]*(?:整套内容|完整大纲|整套)\s*[:：][^\n]*\{full_outline\}[^\n]*\n?', '', template)
    growth_rules = ""
    if isinstance(context, dict):
        growth_rules = context.get("prompt_rules", {}).get("image", "")
    values = {**values, 'full_outline': '', 'growth_rules': growth_rules}
    if '【本次图片的视觉风格：最高优先级视觉约束】' in template:
        values = {**values, **{key: neutral_visual_context(values.get(key, ''))
                              for key in ('page_content', 'full_outline')}}
    result = safe_format(template, values) + layout_rule
    if growth_rules and growth_rules not in result:
        result += growth_rules
    if re.search(r'单页布局\s*[:：]', values.get('page_content', '')):
        result += '\n单页布局只控制排版，优先于旧画面描述中的位置安排；保留文字和事实，布局字段不得印在图中。'
    if "接口参数为准" not in result:
        result += '\n图片分辨率、宽高比、质量和输出格式以接口参数为准；本说明不得印在图中。'
    return result


def normalize_style(value):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError('图片风格配置必须是对象。')
    preset = value.get('preset', 'auto')
    notes = value.get('notes', '')
    if not isinstance(preset, str):
        raise ValueError('请选择有效的图片风格。')
    entry = option("image", "style", preset)
    preset = alias(entry)
    if not isinstance(notes, str) or len(notes) > 600:
        raise ValueError('风格补充要求不能超过600字。')
    result = {'preset': preset, 'notes': notes.strip()}
    if value.get('palette') is not None:
        result['palette'] = normalize_palette(value['palette'])
    recommendation = normalize_recommendation(value.get('recommendation'))
    if recommendation:
        result['recommendation'] = recommendation
    applied = value.get('applied')
    if applied is not None:
        if not isinstance(applied, dict) or 'applied' in applied:
            raise ValueError('已生成图片的风格配置无效。')
        result['applied'] = normalize_style(applied)
    return result


def style_prompt(prompt, value, generation_context=None):
    style = resolve_style(value)
    entry = option("image", "style", style["preset"])
    direction = entry["content"]
    metadata = entry.get("metadata") or {}
    preset = {"id": alias(entry), "name": entry["name"], "color": metadata.get("color", "#5b6472")}
    rules = (
        '\n\n【本次图片的视觉风格：最高优先级视觉约束】\n'
        '最终风格：' + preset['name'] + '（' + preset['id'] + '）\n'
        + direction + '\n补充要求：' + style['notes']
        + '\n强调色：' + preset['color'] + '；文字保持高对比、清晰易读。'
        + '\n风格只改变视觉表现，不能改变上图文字、事实、数字、地点、步骤或结论。'
        + '用户参考图仅按用户明确选择的维度使用；与参考图外观冲突时，按最终风格重新绘制。'
    )
    if style.get('palette'):
        rules += palette_rule(style['palette'])
    return FrozenImageTemplate(rules + '\n\n' + prompt, generation_context=generation_context)


def request_style(data, record_id=None, task_id=None):
    from history.models import HistoryRecord
    from history.permissions import task_records

    record = HistoryRecord.objects.filter(pk=record_id).first() if record_id else None
    if record is None and task_id:
        record = next(iter(task_records(task_id)), None)
    return resolve_style(data.get('image_style', record.image_style if record else None),
                         (record.image_style or {}).get('recommendation') if record else None)
