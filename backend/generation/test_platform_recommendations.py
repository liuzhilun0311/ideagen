from django.test import SimpleTestCase

from .outline_prompt import build_outline_prompt, preferences
from .platform_recommendations import (
    GOALS,
    PLATFORMS,
    normalize_goal,
    normalize_platform,
    normalize_growth_recommendation,
    recommend_growth,
)


class PlatformRecommendationContractTests(SimpleTestCase):
    def test_contract_exposes_supported_platforms_and_goals(self):
        self.assertEqual(
            PLATFORMS,
            ("auto", "xiaohongshu", "douyin", "wechat", "multi"),
        )
        self.assertEqual(
            GOALS,
            ("auto", "follow", "product", "inquiry", "conversion", "brand", "engagement", "share"),
        )

    def test_empty_values_default_to_auto(self):
        self.assertEqual(normalize_platform(None), "auto")
        self.assertEqual(normalize_platform(""), "auto")
        self.assertEqual(normalize_goal(None), "auto")
        self.assertEqual(normalize_goal(""), "auto")

    def test_invalid_values_are_rejected(self):
        for value in ("weibo", " 小红书 ", 1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_platform(value)
        for value in ("sales", "转化", 1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_goal(value)

    def test_outline_preferences_keep_legacy_defaults_and_add_contract_fields(self):
        result = preferences({})
        self.assertEqual(result["platform"], "auto")
        self.assertEqual(result["goal"], "auto")
        self.assertEqual(result["organization"], "自动")

    def test_platform_and_goal_are_injected_into_outline_prompt(self):
        result = preferences({"platform": "xiaohongshu", "goal": "inquiry"})
        prompt = build_outline_prompt("提升生活质量", options=result)
        self.assertIn("发布平台：小红书（xiaohongshu）", prompt)
        self.assertIn("获客目标：私信咨询（inquiry）", prompt)
        self.assertIn("平台与获客目标规则", prompt)

    def test_editor_role_follows_selected_platform_and_topic_heading(self):
        for platform, name in (
            ("xiaohongshu", "小红书"), ("douyin", "抖音"), ("wechat", "公众号"),
            ("multi", "多个发布平台"), ("auto", "根据主题和受众选择的合适平台"),
        ):
            with self.subTest(platform=platform):
                prompt = build_outline_prompt("整理桌面", options={"platform": platform})
                self.assertTrue(prompt.startswith(f"你是面向{name}图文创作的内容编辑。"))
                self.assertIn("用户创作的主题：\n整理桌面", prompt)
                self.assertNotIn("用户要求：", prompt)
                self.assertNotIn("{platform_name}", prompt)
                if platform != "xiaohongshu":
                    self.assertNotIn("面向小红书", prompt)

    def test_platform_placeholder_does_not_rewrite_the_user_topic(self):
        topic = "比较小红书和抖音，保留用户要求：这几个字"
        prompt = build_outline_prompt(topic, options={"platform": "douyin"},
                                      template="面向{platform_name}\n用户创作的主题：\n{topic}")
        self.assertTrue(prompt.startswith("面向抖音"))
        self.assertIn(topic, prompt)

    def test_growth_recommendation_matches_platform_goal_metadata(self):
        layouts = [
            {
                "id": "hook-cover",
                "name": "强钩子封面",
                "metadata": {
                    "platforms": ["xiaohongshu"],
                    "goals": ["follow"],
                    "aspect_ratios": ["3:4"],
                    "summary": "先提出明确问题。",
                },
            },
            {
                "id": "cta",
                "name": "行动号召页",
                "metadata": {
                    "platforms": ["xiaohongshu", "multi"],
                    "goals": ["inquiry"],
                    "aspect_ratios": ["3:4"],
                    "summary": "引导用户采取下一步行动。",
                },
            },
        ]
        styles = [
            {
                "id": "ugc-lifestyle",
                "name": "UGC生活方式",
                "metadata": {
                    "platforms": ["xiaohongshu"],
                    "goals": ["inquiry"],
                    "aspect_ratios": ["3:4"],
                    "summary": "生活化体验表达。",
                },
            },
            {
                "id": "knowledge-card",
                "name": "清爽知识卡片",
                "metadata": {
                    "platforms": ["xiaohongshu", "multi"],
                    "goals": ["follow"],
                    "aspect_ratios": ["3:4"],
                    "summary": "适合收藏型知识。",
                },
            },
        ]
        result = recommend_growth(
            "如何选择适合自己的服务",
            "xiaohongshu",
            "inquiry",
            layouts,
            styles,
        )
        self.assertEqual(
            set(result),
            {"platform", "goal", "layout", "image_style", "aspect_ratio",
             "content_structure", "reason"},
        )
        self.assertEqual(result["platform"], "xiaohongshu")
        self.assertEqual(result["goal"], "inquiry")
        self.assertEqual(result["layout"], "cta")
        self.assertEqual(result["image_style"], "ugc-lifestyle")
        self.assertEqual(result["aspect_ratio"], "3:4")

    def test_growth_normalization_accepts_legacy_image_layout_and_filters_ids(self):
        layouts = [{"id": "pain-solution", "metadata": {"aspect_ratios": ["9:16"]}}]
        styles = [{"id": "talking-cover", "metadata": {"aspect_ratios": ["9:16"]}}]
        result = normalize_growth_recommendation(
            {
                "platform": "douyin",
                "goal": "inquiry",
                "image_layout": "pain-solution",
                "image_style": "talking-cover",
                "aspect_ratio": "9:16",
                "content_structure": "hook_solution_cta",
                "reason": "适合短视频咨询转化",
                "bad_field": "ignored",
            },
            layouts,
            styles,
        )
        self.assertEqual(result["layout"], "pain-solution")
        self.assertNotIn("image_layout", result)
        self.assertEqual(result["image_style"], "talking-cover")
        self.assertEqual(result["aspect_ratio"], "9:16")
        self.assertEqual(result["reason"], "适合短视频咨询转化")

        invalid = normalize_growth_recommendation(
            {"platform": "douyin", "goal": "inquiry", "layout": "missing",
             "image_style": "talking-cover"},
            layouts,
            styles,
        )
        self.assertIsNone(invalid)
