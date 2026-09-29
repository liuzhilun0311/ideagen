"""Normalize and validate the requested outline page count."""


def normalize_page_count(value):
    if value is None or value == "" or value == "auto":
        return "auto"
    if isinstance(value, bool):
        raise ValueError("页数必须选择自动或1-15页。")
    if isinstance(value, int):
        count = value
    elif isinstance(value, str) and value.strip().isdigit():
        count = int(value.strip())
    else:
        raise ValueError("页数必须选择自动或1-15页。")
    if not 1 <= count <= 15:
        raise ValueError("页数必须选择自动或1-15页。")
    return count


def page_count_instruction(page_count, content_form="auto"):
    if page_count == "auto" and content_form == "single_infographic":
        return (
            "\n严格内容形态规则：只输出1页，且该页必须是[信息图]；该页同时承担标题、核心内容、模块关系和结论收束，不拆成封面和总结。"
            "页面之间必须使用<page>分隔；不得增加、删除、合并或拆分页面。"
            "信息过多时围绕主题摘要，保留关键限定条件；不得缩小字体堆字或编造事实。"
        )
    if page_count == "auto":
        return "\n页数规则：根据主题和信息量自动决定合理页数，保持现有自动策略。"
    if page_count == 1 and content_form in ("auto", "single_infographic"):
        layout = "只输出1页，且该页必须是[信息图]；该页同时承担标题、核心内容、模块关系和结论收束，不拆成封面和总结。"
    elif page_count == 1:
        layout = "只输出1页，且该页必须是[封面]。"
    elif page_count == 2:
        layout = "只输出2页，依次为[封面]、[总结]，不得输出[内容]页。"
    else:
        layout = (
            f"只输出{page_count}页，依次为[封面]、{page_count - 2}页[内容]、[总结]。"
        )
    return (
        f"\n严格页数规则：{layout}"
        "页面之间必须使用<page>分隔；不得增加、删除、合并或拆分页面。"
        "指定页数优先于基础模板中的拆页建议。信息过多时围绕主题摘要，保留关键限定条件；不得缩小字体堆字或编造事实。"
    )


def validate_page_count(pages, page_count, content_form=None):
    page_count = normalize_page_count(page_count)
    if page_count == "auto":
        if content_form != "single_infographic":
            return
        page_count = 1
    if len(pages) != page_count:
        raise ValueError("模型未按指定页数生成，请重试。")
    types = [page.get("type") for page in pages]
    if page_count == 1 and content_form in ("auto", "single_infographic") and types != ["infographic"]:
        raise ValueError("模型未按单页知识信息图结构生成，请重试。")
    if page_count == 1 and content_form not in ("auto", "single_infographic") and types != ["cover"]:
        raise ValueError("模型未按指定页面结构生成，请重试。")
    if page_count == 2 and types != ["cover", "summary"]:
        raise ValueError("模型未按指定页面结构生成，请重试。")
    if page_count >= 3 and (
        not types or types[0] != "cover" or types[-1] != "summary"
        or any(page_type != "content" for page_type in types[1:-1])
    ):
        raise ValueError("模型未按指定页面结构生成，请重试。")
