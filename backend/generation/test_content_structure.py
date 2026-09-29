import io
import zipfile

from django.test import SimpleTestCase
from .generation_context import build_generation_context
from .copy_prompt import build_copy_prompt
from .outline_prompt import build_outline_prompt
from prompts.catalog_defaults import builtin_entries
from .reference_document import extract_docx


class ContentStructureTests(SimpleTestCase):
    def test_catalog_has_new_structures(self):
        names = {entry["name"] for entry in builtin_entries()
                 if entry["module"] == "outline" and entry["category"] == "organization"}
        self.assertTrue({"误区纠正", "案例拆解", "产品种草", "观点论证"} <= names)

    def test_outline_uses_selected_structure(self):
        prompt = build_outline_prompt("主题", options={"organization": "案例拆解"})
        self.assertIn("案例拆解", prompt)
        self.assertIn("缺少结果时明确未知", prompt)

    def test_image_structure_does_not_rewrite_the_whole_outline(self):
        context = build_generation_context("主题", "大纲", {"organization": "问题解决"}, {}, {})
        self.assertIn("问题解决", context["prompt_rules"]["image"])
        self.assertIn("不得在一张图中重写整套内容", context["prompt_rules"]["image"])

    def test_copy_follows_structure_by_default(self):
        prompt, _, _ = build_copy_prompt({"topic": "主题", "outline": "页面内容",
                                          "generation_preferences": {"organization": "步骤教程"}})
        self.assertIn("步骤教程", prompt)
        self.assertIn("正文结构跟随整套内容结构", prompt)

    def test_explicit_copy_structure_takes_precedence(self):
        prompt, _, _ = build_copy_prompt({"topic": "主题", "outline": "页面内容",
            "generation_preferences": {"organization": "步骤教程"},
            "copy_preferences": {"structure": "要点清单"}})
        self.assertIn("以用户明确选择的正文结构为准", prompt)
        self.assertIn("正文结构：要点清单", prompt)

    def test_extracts_docx_text_without_persisting_the_document(self):
        xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>第一段</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>第二段</w:t></w:r></w:p></w:body></w:document>'
        ).encode()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", xml)
        self.assertEqual(extract_docx(buffer.getvalue()), "第一段\n\n第二段")
