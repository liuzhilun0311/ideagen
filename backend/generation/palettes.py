"""Validated palette choices, shared by every image generation path."""
import json
import re
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name("palette_catalog.json").read_text(encoding="utf-8"))
PALETTES = {item["id"]: item for item in CATALOG}


def image_reference_roles(style, value):
    from .reference_roles import validate_reference_roles
    roles = validate_reference_roles(value)
    if (style.get("palette") or {}).get("mode") == "reference" and "color" not in roles:
        roles = [*roles, "color"]
    return roles


def normalize_palette(value):
    if not isinstance(value, dict) or value.get("mode") not in (*PALETTES, "auto", "reference", "custom"):
        raise ValueError("请选择有效配色。")
    result = {"mode": value["mode"]}
    if result["mode"] == "custom":
        for key, default in (("primary", "#194B8C"), ("background", "#F4F8FF"), ("accent", "#19A7A0")):
            color = value.get(key, default)
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("自定义配色必须为六位十六进制颜色。")
            result[key] = color
    if value.get("recommendation") in PALETTES:
        result["recommendation"] = value["recommendation"]
        result["reason"] = str(value.get("reason", ""))[:180]
    return result


def palette_rule(value):
    palette = normalize_palette(value)
    mode = palette["mode"]
    if mode == "reference":
        direction = "从本次实际提供的参考图片提取主色、背景色、强调色；不复制文字和内容。没有参考图时根据主题选择配色，不声称已参考图片。"
    elif mode == "auto" and not palette.get("recommendation"):
        direction = "根据主题、读者和最终画风自动选择协调配色。"
    else:
        colors = palette if mode == "custom" else PALETTES[palette.get("recommendation") if mode == "auto" else mode]
        direction = f"主色：{colors['primary']}；背景色：{colors['background']}；强调色：{colors['accent']}。"
    return ("\n【独立配色约束】" + direction
            + "配色优先于画风模板及旧画面描述的颜色要求，但不改变绘画媒介。"
            "文字自动选择与背景有足够对比的颜色，不仅靠颜色区分信息；颜色编码和规则不得印在图中。")


def recommendation_instruction():
    return ("\n另需在 generation-recommendation 中提供 palette（以下配色ID之一）和 palette_reason（中文推荐理由，不超过120字）。"
            "结合主题、读者及推荐画风选择整套统一配色，不固定选择同一种。\n"
            + "；".join(f"{item['id']}：{item['name']}" for item in CATALOG))
