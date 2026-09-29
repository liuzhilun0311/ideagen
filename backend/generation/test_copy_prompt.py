import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from accounts.models import User, Token
from .copy_prompt import build_copy_prompt


class CopyPromptTests(TestCase):
    def setUp(self):
        user = User.objects.create(id="copy-preview", username="copy-preview")
        Token.objects.create(user=user, key="copy-preview-token",
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer copy-preview-token"
        self.data = {"topic": "Desk", "outline": "Clear your desk. Literal {topic}",
                     "prompt_name": "legacy-template"}

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    @patch("generation.views.get_content_service")
    def test_preview_matches_generation_without_model_call(self, service):
        preview = self.post("/api/content/preview", self.data)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview["Cache-Control"], "no-store")
        service.assert_not_called()
        service.return_value.generate_content.return_value = {
            "success": True, "titles": ["Desk"], "copywriting": "Clear", "tags": [],
        }
        result = self.post("/api/content", self.data)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(preview.json()["prompt"],
                         service.return_value.generate_content.call_args.kwargs["prepared_prompt"])
        self.assertIn("Literal {topic}", preview.json()["prompt"])
        self.assertEqual(preview.json()["preferences"],
                         {"style": "自动", "structure": "自动", "length": "适中", "emoji_level": "克制"})

    @patch("generation.views.get_content_service")
    def test_invalid_options_rejected_before_service(self, service):
        for options in ([], {"style": "bad"}, {"structure": 3}, {"length": "bad"}):
            for endpoint in ("/api/content", "/api/content/preview"):
                self.assertEqual(self.post(endpoint, {**self.data, "copy_preferences": options}).status_code, 400)
        service.assert_not_called()

    def test_manual_style_overrides_inherited_tone(self):
        data = {**self.data, "generation_preferences": {
            "audience": "自动判断", "tone": "温和鼓励",
        }}
        # Use a valid stored tone from the existing outline catalog.
        from .outline_prompt import TONES
        data["generation_preferences"]["tone"] = next(iter(TONES))
        _, _, automatic = build_copy_prompt(data)
        self.assertEqual(automatic["tone"], data["generation_preferences"]["tone"])
        prompt, _, manual = build_copy_prompt({**data, "copy_preferences": {
            "style": "简洁干货", "structure": "要点清单", "length": "简短",
        }})
        self.assertEqual(manual["tone"], "简洁干货")
        self.assertIn("100至200", prompt)
        self.assertIn("不新增价格", prompt)
        self.assertNotIn("legacy-template", prompt)

    def test_preview_requires_authentication(self):
        self.client.defaults.clear()
        self.assertEqual(self.post("/api/content/preview", self.data).status_code, 401)

    def test_rich_emoji_includes_topic_library_and_clear_density_targets(self):
        prompt, options, _ = build_copy_prompt({
            **self.data, "copy_preferences": {"emoji_level": "丰富"},
        })
        self.assertEqual(options["emoji_level"], "丰富")
        for text in ("表情与符号丰富度：丰富", "3至5个", "6至10个", "10至16个",
                     "人脸情绪", "动物", "食物", "物品与场景", "手势与爱心", "自然天气",
                     "🥰", "🫐", "🫶", "🪻", "①②③④", "1️⃣2️⃣3️⃣4️⃣", "✓", "→", "•",
                     "不替换事实中的数字", "数量是软目标", "同级列表",
                     "优先使用键帽数字表情1️⃣ 2️⃣ 3️⃣ 4️⃣",
                     "允许中性编号和提示符号", "不要求凑满情绪表情数量"):
            self.assertIn(text, prompt)
        self.assertNotIn("每段最多2个", prompt)
        self.assertNotIn("严肃风险主题不使用emoji", prompt)

    def test_health_and_safety_rich_copy_allows_neutral_symbols(self):
        prompt, _, _ = build_copy_prompt({
            "topic": "出行、居家和健康防护清单",
            "outline": "出行使用安全带，居家检查报警器，记录血压并咨询医生。",
            "copy_preferences": {"emoji_level": "丰富", "length": "简短"},
        })
        self.assertIn("1️⃣、✅、📌、🏠", prompt)
        self.assertIn("避免搞笑、夸张、庆祝或淡化风险", prompt)
        self.assertIn("正文至少使用一种", prompt)
        self.assertNotIn("严肃风险主题不使用emoji", prompt)

    def test_no_emoji_uses_plain_markers_without_suggesting_emoji_library(self):
        prompt, _, _ = build_copy_prompt({
            **self.data, "copy_preferences": {"emoji_level": "无"},
        })
        self.assertIn("不使用任何 emoji 或装饰性符号", prompt)
        self.assertIn("普通数字编号或短横线", prompt)
        self.assertNotIn("表情参考库", prompt)
        self.assertNotIn("6至10个", prompt)

    def test_restrained_emoji_retains_low_density_with_symbol_guidance(self):
        prompt, _, _ = build_copy_prompt({
            **self.data, "copy_preferences": {"emoji_level": "克制"},
        })
        self.assertIn("0至3个", prompt)
        self.assertIn("少量搭配圈号编号或提示符号", prompt)
        self.assertIn("只替换列表序号", prompt)
        self.assertNotIn("6至10个", prompt)

    def test_platform_risk_rules_are_injected_without_post_generation_rewrite(self):
        prompt, _, _ = build_copy_prompt({
            **self.data,
            "generation_preferences": {"platform": "xiaohongshu", "goal": "product"},
        })
        self.assertIn("平台风险表达底线", prompt)
        self.assertIn("100%有效", prompt)
        self.assertIn("不得修改事实", prompt)
        self.assertIn("生成完成后不机械替换", prompt)
