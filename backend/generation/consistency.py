"""Deterministic content/image prompt consistency checks.

The checker is intentionally conservative: it reports prompt claims that are
not present in the page copy, but does not block viewing or regeneration.
"""
from __future__ import annotations

import re
from typing import Any


_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:万|亿|元|岁|人|个|件|天|%|％)?")
_SUBJECT_RE = re.compile(
    r"(?:产品|课程|服务|品牌|软件|工具|方案)\s*(?:[A-Za-z0-9_-]{1,16}|[\u4e00-\u9fff]{1,6})"
)
_CONCLUSION_RE = re.compile(
    r"(?:保证收益|稳赚不赔|零风险|一定有效|绝对有效|立刻见效|完全解决|"
    r"100%有效|最好的选择|第一名|行业第一)"
)
_CTA_RE = re.compile(
    r"(?:私信|咨询|留言|评论|收藏|关注|转发|点击购买|立即购买|下单|扫码|"
    r"预约|报名|加微信|联系客服|了解更多)"
)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_text(item) for item in value)
    return ""


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _page_index(page: dict[str, Any], fallback: int) -> int:
    value = page.get("index", fallback)
    return value if type(value) is int and value >= 0 else fallback


def _find_image(images: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    for image in images:
        if type(image) is dict and image.get("index") == index:
            return image
    return None


def _risk(kind: str, detail: str, values: list[str]) -> dict[str, Any]:
    return {"type": kind, "detail": detail, "values": values}


def check_content_image_consistency(topic="", pages=None, images=None, growth_preferences=None):
    """Compare page copy with the corresponding image-generation prompt.

    ``pages`` and ``images`` are deliberately loose JSON-compatible objects.
    Image entries should contain ``index`` and ``prompt``. Missing prompts are
    reported as ``unavailable`` instead of raising or preventing the workflow.
    """
    page_list = pages if isinstance(pages, list) else []
    image_list = images if isinstance(images, list) else []
    preferences = growth_preferences if isinstance(growth_preferences, dict) else {}
    results: list[dict[str, Any]] = []
    checked = 0

    for fallback_index, page in enumerate(page_list):
        if not isinstance(page, dict):
            continue
        index = _page_index(page, fallback_index)
        copy_text = _text(page.get("content") or page.get("text") or page)
        image = _find_image(image_list, index)
        prompt = _text(image.get("prompt")) if image else ""
        risks: list[dict[str, Any]] = []
        if not prompt.strip():
            results.append({
                "index": index,
                "status": "unavailable",
                "summary": "缺少本页图片提示词，暂时无法判断。",
                "risks": [],
            })
            continue

        checked += 1
        subjects = _unique(_SUBJECT_RE.findall(prompt))
        missing_subjects = [value for value in subjects if value not in copy_text]
        if missing_subjects:
            risks.append(_risk(
                "subject",
                f"图片提示词包含正文未提及的主体：{'、'.join(missing_subjects)}。",
                missing_subjects,
            ))

        prompt_numbers = _unique(_NUMBER_RE.findall(prompt))
        missing_numbers = [value for value in prompt_numbers if value not in copy_text]
        if missing_numbers:
            risks.append(_risk(
                "number",
                f"图片提示词包含正文未提及的数字：{'、'.join(missing_numbers)}。",
                missing_numbers,
            ))

        conclusions = _unique(_CONCLUSION_RE.findall(prompt))
        missing_conclusions = [value for value in conclusions if value not in copy_text]
        if missing_conclusions:
            risks.append(_risk(
                "conclusion",
                f"图片提示词包含正文未提及的结论：{'、'.join(missing_conclusions)}。",
                missing_conclusions,
            ))

        prompt_cta = _unique(_CTA_RE.findall(prompt))
        copy_cta = _unique(_CTA_RE.findall(copy_text))
        missing_cta = [value for value in prompt_cta if value not in copy_text]
        if missing_cta:
            risks.append(_risk(
                "cta",
                f"图片提示词的行动引导与正文不一致：{'、'.join(missing_cta)}。",
                missing_cta,
            ))
        goal = preferences.get("goal")
        if goal == "inquiry" and copy_cta and not any(
            value in prompt for value in ("私信", "咨询", "留言", "联系客服", "加微信")
        ):
            risks.append(_risk(
                "cta",
                "当前目标是私信咨询，但图片提示词没有对应的咨询引导。",
                copy_cta,
            ))

        results.append({
            "index": index,
            "status": "warning" if risks else "consistent",
            "summary": "发现需要核对的内容。" if risks else "正文与图片提示词基本一致。",
            "risks": risks,
        })

    if not results:
        return {
            "status": "unavailable",
            "summary": "没有可检查的页面。",
            "pages": [],
        }
    if checked == 0:
        return {
            "status": "unavailable",
            "summary": "缺少图片提示词，暂时无法判断图片与文案的一致性。",
            "pages": results,
        }
    warning_count = sum(1 for page in results if page["status"] == "warning")
    if warning_count:
        return {
            "status": "warning",
            "summary": f"发现 {warning_count} 页需要核对，结果不会阻塞查看或重试。",
            "pages": results,
        }
    return {
        "status": "consistent",
        "summary": "已检查页面，正文与图片提示词基本一致。",
        "pages": results,
    }
