"""Optional structure metadata for the existing text outline contract."""
import re

ORGANIZATIONS = ("自动", "分类递进", "步骤教程", "问题解决", "对比决策",
                 "概念到例子", "故事时间线", "清单合集",
                 "误区纠正", "案例拆解", "产品种草", "观点论证")

GROWTH_LAYOUTS = (
    "hook-cover", "pain-solution", "myth-fact", "before-after", "case-study",
    "product-benefits", "proof", "faq", "data-conclusion", "quote",
    "chapter-divider", "cta", "talking-subtitle", "product-demo", "comment-proof",
)

LAYOUT_NAMES = (
    "封面", "清单", "步骤", "对比", "分类", "关系", "例子", "总结",
    "强钩子封面", "痛点—方案", "误区—真相", "前后对比", "案例拆解",
    "产品卖点", "用户评价/证据", "FAQ问答", "数据结论", "金句观点",
    "章节分隔", "行动号召页", "口播字幕页", "产品演示页", "评论/聊天截图页",
)


def organization_instruction(value="自动", catalog_content=None):
    from prompts.catalog_runtime import option
    entry = option("outline", "organization", value)
    from prompts.catalog_runtime import options
    layout_entries = options("image", "layout")
    layout_names = "、".join(
        item["name"] for item in layout_entries
        if item.get("legacy_value") != "自动"
    )
    selection = "按主题选择合适的组织方式" if entry.get("legacy_value") == "自动" else f"采用用户选择的组织方式：{entry['name']}"
    rule = entry["content"]
    from prompts.catalog_runtime import options as catalog_options
    organization_names = "、".join(item["name"] for item in catalog_options("outline", "organization")
                                 if item.get("legacy_value") != "自动")
    return (
        f"\n整套内容组织：{selection}。{rule}只决定各页内容顺序，不固定画风或输出规格。"
        "\n每页类型行之后输出“单页布局：布局名称”，再输出上图文字和画面描述。"
        f"布局按内容从当前目录中选择：{layout_names}。"
        "\n自动选择时综合主题、受众、参考事实、页数、平台和目标，不仅按平台套固定模板。"
        f"\n内容组织目录：{organization_names}。"
        "\n所有页面之后输出 <organization>实际组织方式</organization>，值必须来自内容组织目录；"
        "它是独立元数据，不是页面内容。"
    )


def extract_organization(text):
    match = re.search(r"<organization>\s*([^<\n]{1,40})\s*</organization>", text, re.I)
    organization = match.group(1).strip() if match else "自动"
    clean = re.sub(r"<organization>.*?(?:</organization>|$)", "", text, flags=re.S | re.I).strip()
    return clean, organization


def page_metadata(text):
    layout = re.search(r"(?m)^\s*单页布局\s*[:：]\s*([^\n]+)", text)
    visual = re.search(r"(?:画面描述|视觉主体)\s*[:：]\s*(.*)", text, re.S)
    return {"layout": layout.group(1).strip() if layout else "自动",
            "visual_focus": visual.group(1).strip() if visual else ""}


def image_page_content(page):
    content = page["content"]
    metadata = page_metadata(content)
    if metadata["layout"] == "自动" and page.get("layout") and "单页布局" not in content:
        content = f'单页布局：{page["layout"]}\n' + content
    if page.get("reference_notes"):
        content = f'{content}\n参考分析：{page["reference_notes"]}'
    return content
