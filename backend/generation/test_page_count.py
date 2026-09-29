from unittest.mock import patch

from django.test import SimpleTestCase

from .page_count import normalize_page_count, page_count_instruction, validate_page_count
from .services.outline import OutlineService


def pages(*types):
    return [{"type": page_type} for page_type in types]


class PageCountTests(SimpleTestCase):
    def test_normalize_accepts_auto_and_one_to_fifteen(self):
        self.assertEqual(normalize_page_count(None), "auto")
        self.assertEqual(normalize_page_count("auto"), "auto")
        self.assertEqual(normalize_page_count("5"), 5)
        self.assertEqual(normalize_page_count(15), 15)

    def test_normalize_rejects_invalid_values(self):
        for value in (0, 16, 1.5, True, "nope", "0", "16"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_page_count(value)

    def test_prompt_instruction_describes_fixed_structures(self):
        self.assertIn("只输出1页", page_count_instruction(1))
        self.assertIn("[封面]、[总结]", page_count_instruction(2))
        self.assertIn("只输出5页", page_count_instruction(5))

    def test_fixed_page_structures_are_validated(self):
        validate_page_count(pages("cover"), 1)
        validate_page_count(pages("infographic"), 1, "single_infographic")
        validate_page_count(pages("cover", "summary"), 2)
        validate_page_count(pages("cover", "content", "content", "summary"), 4)

    def test_single_infographic_requires_infographic_page_type(self):
        self.assertIn("[信息图]", page_count_instruction(1, "single_infographic"))
        self.assertIn("只输出1页", page_count_instruction("auto", "single_infographic"))
        validate_page_count(pages("infographic"), "auto", "single_infographic")
        with self.assertRaises(ValueError):
            validate_page_count(pages("cover"), 1, "single_infographic")

    def test_invalid_page_count_or_types_fail(self):
        for actual, requested in (
            (pages("cover", "summary"), 1),
            (pages("cover", "content"), 2),
            (pages("cover", "summary", "summary"), 3),
            (pages("cover", "content", "content", "content"), 5),
        ):
            with self.subTest(actual=actual, requested=requested), self.assertRaises(ValueError):
                validate_page_count(actual, requested)

    @patch("generation.services.outline.get_text_provider_config", return_value={"model": "synthetic"})
    @patch("generation.services.outline.OutlineService._get_client")
    @patch("generation.services.outline.load_text_providers_config", return_value={})
    def test_service_rejects_model_output_with_wrong_fixed_count(self, _providers, client, _config):
        client.return_value.generate_text.return_value = (
            "[封面]\n上图文字：封面\n画面描述：主体\n"
            "<page>\n[总结]\n上图文字：总结\n画面描述：主体"
        )
        result = OutlineService("page-count-test").generate_outline(
            "主题", prepared_prompt="prompt", options={"page_count": 1}
        )
        self.assertFalse(result["success"])
        self.assertIn("指定页数", result["error"])
