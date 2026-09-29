from types import SimpleNamespace
from django.test import SimpleTestCase

from .parameters import normalize_image_parameters, apply_image_parameters
from .structure import extract_organization, page_metadata, image_page_content
from .styles import format_image_prompt
from .services.outline import OutlineService
from unittest.mock import Mock, patch


class LayerTests(SimpleTestCase):
    def test_defaults(self):
        self.assertEqual(normalize_image_parameters(None), {
            "resolution": "1K", "aspect_ratio": "3:4",
            "quality": "low", "output_format": "png",
        })

    def test_explicit_parameters_and_auto(self):
        self.assertEqual(normalize_image_parameters({
            "resolution": "AUTO", "quality": "high",
            "aspect_ratio": "1:1", "output_format": "webp",
        }), {"resolution": "1K", "quality": "high",
             "aspect_ratio": "1:1", "output_format": "webp"})

    def test_invalid_values_do_not_silently_fallback(self):
        for value in ({"quality": "typo"}, {"resolution": "8K"},
                      {"aspect_ratio": "0:0"}, {"output_format": "gif"}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_image_parameters(value)

    def test_service_and_generator_receive_same_values(self):
        service = SimpleNamespace(provider_config={"quality": "high"},
                                  generator=SimpleNamespace(config={}))
        original = service
        service = apply_image_parameters(service, {"quality": "low"})
        self.assertEqual(original.provider_config["quality"], "high")
        self.assertEqual(service.provider_config["quality"], "low")
        self.assertEqual(service.generator.config["quality"], "low")
        self.assertEqual(service.generator.config["image_size"], "1K")

    def test_organization_is_not_a_page(self):
        text, organization = extract_organization(
            "[封面]\n上图文字：标题\n<organization>分类递进</organization>")
        self.assertEqual(organization, "分类递进")
        self.assertNotIn("<organization>", text)

    def test_legacy_and_explicit_page_metadata(self):
        self.assertEqual(page_metadata("旧页面")["layout"], "自动")
        self.assertEqual(page_metadata(
            "[内容]\n单页布局：对比\n上图文字：标题\n画面描述：\n左右并列"
        ), {"layout": "对比", "visual_focus": "左右并列"})

    def test_page_layout_overrides_old_composition_without_removing_facts(self):
        content = image_page_content({"content": "上图文字：3:4、1K 是本页介绍的术语",
                                      "layout": "对比"})
        result = format_image_prompt("本页：{page_content}\n整套：{full_outline}", {
            "page_content": content, "full_outline": "other page",
        })
        self.assertIn("单页布局：对比", result)
        self.assertIn("3:4、1K", result)
        self.assertIn("优先于旧画面描述", result)
        self.assertNotIn("other page", result)

    def test_changed_layout_in_text_wins_over_old_parsed_metadata(self):
        content = "单页布局：步骤\n上图文字：先整理后归类"
        self.assertEqual(image_page_content({"content": content, "layout": "对比"}), content)

    def test_legacy_inline_template_keeps_current_page(self):
        prompt = format_image_prompt("{page_content} context: {full_outline}",
                                     {"page_content": "KEEP", "full_outline": "DROP"})
        self.assertIn("KEEP", prompt)
        self.assertNotIn("DROP", prompt)
        self.assertIn("接口参数为准", prompt)

    @patch("generation.services.outline.get_text_provider_config", return_value={})
    def test_outline_generation_preserves_metadata_and_legacy_pages(self, _config):
        service = OutlineService.__new__(OutlineService)
        service.user_id = "layer-test"
        service.client = Mock()
        service.prompt_template = "主题：{topic}"
        service.client.generate_text.return_value = (
            "[封面]\n单页布局：封面\n上图文字：标题\n画面描述：居中\n"
            "<page>\n[内容]\n单页布局：步骤\n上图文字：先整理后归类\n"
            "画面描述：顺序路径\n<organization>步骤教程</organization>"
        )
        result = service.generate_outline("收纳", organization="步骤教程")
        self.assertTrue(result["success"])
        self.assertEqual(result["organization"], "步骤教程")
        self.assertEqual(len(result["pages"]), 2)
        self.assertEqual(result["pages"][1]["layout"], "步骤")
        self.assertNotIn("<organization>", result["outline"])
        self.assertIn("采用用户选择的组织方式：步骤教程", service.client.generate_text.call_args.kwargs["prompt"])
