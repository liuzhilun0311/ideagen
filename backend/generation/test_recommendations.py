import json

from django.test import SimpleTestCase

from .recommendations import (
    attach_outline_explanation,
    extract_generation_recommendation,
    extract_growth_recommendation,
    recommendation_instruction,
    resolve_adopted_tone,
)


class RecommendationProtocolTests(SimpleTestCase):
    def test_only_automatic_choices_request_reasons(self):
        prompt = recommendation_instruction({"platform": "douyin", "goal": "auto",
                                             "audience": "专业读者", "organization": "自动",
                                             "tone": "自动匹配"})
        self.assertIn("返回推荐理由：goal、organization、tone、content_form、information_density。", prompt)
        self.assertIn("手动指定的选项不要返回理由", prompt)

    def test_automatic_tone_is_resolved_from_catalog_and_manual_tone_is_preserved(self):
        automatic = {"tone": "自动匹配"}
        self.assertEqual(
            resolve_adopted_tone(automatic, {"tone": "亲切易懂"})["tone"], "亲切易懂")
        manual = {"tone": "专业简洁"}
        self.assertEqual(
            resolve_adopted_tone(manual, {"tone": "亲切易懂"})["tone"], "专业简洁")
        for invalid in (None, "", {}, "不存在的语气"):
            self.assertEqual(resolve_adopted_tone(automatic, {"tone": invalid}), automatic)
        self.assertIn("另需提供 tone 字段", recommendation_instruction())

    def test_tone_reasons_follow_requested_mode(self):
        result = {"generation_recommendation": {"outline_explanation": {"tone": "生活主题适合自然表达"}},
                  "growth_recommendation": {"source": "model"}}
        attach_outline_explanation(result, {"tone": "专业简洁"})
        self.assertNotIn("outline_explanation", result["growth_recommendation"])
        attach_outline_explanation(result, {"tone": "自动匹配"})
        self.assertEqual(result["growth_recommendation"]["outline_explanation"]["tone"], "生活主题适合自然表达")

    def test_manual_reasons_discarded_and_automatic_reasons_preserved(self):
        result = {"generation_recommendation": {"outline_explanation": {
            "platform": "不应采用", "goal": "主题适合知识分享", "audience": 123,
            "sequence_reason": "按时间展开",
        }}, "growth_recommendation": {"source": "model"}}
        attach_outline_explanation(result, {"platform": "douyin"})
        actual = result["growth_recommendation"]["outline_explanation"]
        self.assertNotIn("platform", actual)
        self.assertNotIn("audience", actual)
        self.assertEqual(actual["goal"], "主题适合知识分享")
        self.assertEqual(actual["sequence_reason"], "按时间展开")

    def test_instruction_preserves_legacy_fields_and_adds_growth_protocol(self):
        prompt = recommendation_instruction()
        for field in ("image_style", "image_layout", "copy_style", "copy_structure",
                      "copy_length", "emoji_level", "growth_recommendation"):
            self.assertIn(field, prompt)
        self.assertIn("image_layout", prompt)

    def test_generation_extraction_preserves_old_fields_and_growth(self):
        value = {
            "image_style": "knowledge-card",
            "image_layout": "hook-cover",
            "copy_style": "专业简洁",
            "growth_recommendation": {
                "platform": "xiaohongshu",
                "goal": "follow",
                "image_layout": "hook-cover",
                "image_style": "knowledge-card",
                "aspect_ratio": "3:4",
                "content_structure": "hook_value_cta",
                "reason": "适合收藏和关注",
            },
        }
        clean, result = extract_generation_recommendation(
            "正文\n<generation-recommendation>"
            + json.dumps(value, ensure_ascii=False)
            + "</generation-recommendation>"
        )
        self.assertEqual(clean, "正文")
        self.assertEqual(result["image_style"], "knowledge-card")
        self.assertEqual(result["image_layout"], "hook-cover")
        self.assertEqual(result["growth_recommendation"]["image_layout"], "hook-cover")

    def test_growth_extraction_normalizes_legacy_layout_and_rejects_bad_ids(self):
        layouts = [{"id": "hook-cover", "metadata": {"aspect_ratios": ["3:4"]}}]
        styles = [{"id": "knowledge-card", "metadata": {"aspect_ratios": ["3:4"]}}]
        payload = {
            "platform": "xiaohongshu",
            "goal": "follow",
            "image_layout": "hook-cover",
            "image_style": "knowledge-card",
            "aspect_ratio": "3:4",
            "content_structure": "hook_value_cta",
            "reason": "清楚",
        }
        clean, result = extract_growth_recommendation(
            "正文\n<growth-recommendation>"
            + json.dumps(payload, ensure_ascii=False)
            + "</growth-recommendation>",
            layouts,
            styles,
        )
        self.assertEqual(clean, "正文")
        self.assertEqual(result["layout"], "hook-cover")
        self.assertEqual(result["image_style"], "knowledge-card")

        clean, result = extract_growth_recommendation(
            "正文\n<growth-recommendation>{\"layout\":\"bad\",\"image_style\":\"bad\"}"
            "</growth-recommendation>",
            layouts,
            styles,
        )
        self.assertEqual(clean, "正文")
        self.assertIsNone(result)
