"""Canonical outline content-form and information-density options."""

CONTENT_FORMS = {
    "auto": {
        "name": "自动推荐",
        "prompt": "根据主题、平台、读者、页数和参考资料选择最合适的图文形态。",
    },
    "single_infographic": {
        "name": "单页知识信息图",
        "prompt": "把一个主题压缩为一张纵向知识信息图，使用清晰的标题、模块、流程或结论层级，不拆成封面和总结两页。",
    },
    "multi_page_cards": {
        "name": "多页知识卡片",
        "prompt": "将主题拆成多页卡片，每页只承担一个核心重点，形成可连续滑动阅读的内容。",
    },
    "flowchart": {
        "name": "流程图解",
        "prompt": "突出步骤、判断条件、输入输出和先后关系，只有素材确实存在流程时才使用箭头。",
    },
    "comparison": {
        "name": "对比分析图",
        "prompt": "按统一维度并列比较不同方案、状态或选择，明确适用场景和限制。",
    },
    "methodology_poster": {
        "name": "方法论海报",
        "prompt": "突出一套可复用的方法、框架或系统，安排核心原则、流程、工具和验收标准。",
    },
    "product_long_graphic": {
        "name": "产品介绍长图",
        "prompt": "围绕产品用途、适用人群、核心能力、边界和下一步行动组织内容，不虚构卖点。",
    },
    "data_conclusion": {
        "name": "数据结论图",
        "prompt": "突出有来源或用户提供的数据、变化、结论和解释，不补写未经提供的数字。",
    },
    "checklist_poster": {
        "name": "清单海报",
        "prompt": "把可执行事项整理为分组清单、检查项和完成标准，保持短句和可扫读性。",
    },
}

DENSITIES = {
    "auto": {"name": "自动推荐", "prompt": "根据主题复杂度和目标平台选择可读的信息量。"},
    "concise": {"name": "简洁", "prompt": "只保留最重要的结论和少量支撑信息，留出明显留白。"},
    "standard": {"name": "标准", "prompt": "在完整表达和手机可读之间平衡，每个模块保留必要解释。"},
    "high": {"name": "高密度", "prompt": "允许更多模块和短句，但必须分层、留安全边距，不能靠缩小文字堆叠。"},
}


def normalize_content_form(value):
    if value in (None, "", "自动", "自动推荐"):
        return "auto"
    if not isinstance(value, str) or value not in CONTENT_FORMS:
        raise ValueError("内容形态必须选择有效选项。")
    return value


def normalize_information_density(value):
    if value in (None, "", "自动", "自动推荐"):
        return "auto"
    if not isinstance(value, str) or value not in DENSITIES:
        raise ValueError("信息密度必须选择有效选项。")
    return value


def content_form_name(value):
    return CONTENT_FORMS[normalize_content_form(value)]["name"]


def information_density_name(value):
    return DENSITIES[normalize_information_density(value)]["name"]
