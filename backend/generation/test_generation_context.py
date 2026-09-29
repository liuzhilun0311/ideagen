from django.test import SimpleTestCase

from .generation_context import (
    audit_context,
    build_generation_context,
    growth_prompt_rules,
)
from .copy_validation import validate_copy_result


class GenerationContextTests(SimpleTestCase):
    def test_context_keeps_platform_and_goal_for_all_generation_phases(self):
        context = build_generation_context(
            topic="AI 工具获客",
            outline="单页布局：强钩子封面\n上图文字：提高效率",
            generation_preferences={"platform": "douyin", "goal": "follow"},
            copy_preferences={"style": "简洁干货"},
            image_style={"preset": "infographic", "notes": ""},
        )
        self.assertEqual(context["growth"], {"platform": "douyin", "goal": "follow"})
        for phase in ("outline", "copy", "image"):
            self.assertIn("douyin", context["prompt_rules"][phase])
            self.assertIn("follow", context["prompt_rules"][phase])

    def test_image_rules_block_internal_fields_from_visible_text(self):
        rules = growth_prompt_rules("douyin", "inquiry", "image")
        self.assertIn("禁止渲染", rules)
        self.assertIn("douyin", rules)
        self.assertIn("inquiry", rules)

    def test_audit_context_reports_each_growth_field_for_each_phase(self):
        context = build_generation_context(
            "主题",
            "",
            {"platform": "xiaohongshu", "goal": "inquiry"},
            {},
            {},
        )
        growth_entries = [
            item for item in audit_context(context)
            if item["field"] in ("platform", "goal")
        ]
        self.assertEqual(len(growth_entries), 6)
        self.assertTrue(all(item["applied"] for item in growth_entries))
        self.assertEqual(
            {item["value"] for item in growth_entries},
            {"xiaohongshu", "inquiry"},
        )

    def test_old_context_without_new_fields_remains_normalized(self):
        context = build_generation_context("主题", "", {}, {}, {})
        self.assertEqual(context["growth"], {"platform": "auto", "goal": "auto"})
        self.assertTrue(all(
            context["prompt_rules"][phase]
            for phase in ("outline", "copy", "image")
        ))

    def test_xiaohongshu_rules_cover_reference_risk_categories(self):
        rules = growth_prompt_rules("xiaohongshu", "product", "copy")
        for phrase in ("绝对化", "功效承诺", "医疗化", "特殊人群", "100%有效",
                       "根治", "美白", "减肥", "孕妇", "自然改写", "不得修改事实"):
            self.assertIn(phrase, rules)

    def test_platform_rules_are_distinct_and_present_in_every_phase(self):
        for platform in ("auto", "xiaohongshu", "douyin", "wechat", "multi"):
            rules = [
                growth_prompt_rules(platform, "share", phase)
                for phase in ("outline", "copy", "image")
            ]
            self.assertTrue(all("平台风险表达底线" in value for value in rules))
            self.assertTrue(all("不得使用谐音、拆字或特殊字符规避" in value for value in rules))
        self.assertIn("避免标题党", growth_prompt_rules("douyin", "share", "copy"))
        self.assertIn("依据、适用范围和限制", growth_prompt_rules("wechat", "share", "copy"))
        self.assertIn("最保守的跨平台表达", growth_prompt_rules("multi", "share", "copy"))
        self.assertNotEqual(
            growth_prompt_rules("douyin", "share", "copy"),
            growth_prompt_rules("wechat", "share", "copy"),
        )

    def test_copy_validation_does_not_rewrite_generated_body(self):
        result = {"copywriting": "100%有效，事实数字 2026 不应被自动改写。"}
        original = result["copywriting"]
        validate_copy_result(result, {"emoji_level": "无", "length": "简短"})
        self.assertEqual(result["copywriting"], original)
