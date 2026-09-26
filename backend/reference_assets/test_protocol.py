from unittest import TestCase

from .protocol import build_analysis_prompt, parse_analysis_response


class AnalysisProtocolTests(TestCase):
    def test_parse_code_fenced_response_fills_defaults(self):
        result = parse_analysis_response('```json\n{"content": {"summary": "x"}}\n```')

        self.assertEqual(result["content"]["summary"], "x")
        self.assertEqual(result["layout"]["page_type"], "content")
        self.assertEqual(result["visual_style"]["attributes"], [])

    def test_invalid_response_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "格式不正确"):
            parse_analysis_response("not json")

    def test_prompt_keeps_image_parameters_out_of_style_layer(self):
        prompt = build_analysis_prompt({"topic": "咖啡"})
        style_section = prompt.split('"visual_style":', 1)[1]

        for value in ("1K", "3:4", "low", "png"):
            self.assertNotIn(value, style_section)
