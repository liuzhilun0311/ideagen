import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from accounts.models import User, Token
from .models import OutlineRun
from .outline_prompt import build_outline_prompt
from .services.outline import OutlineService


class OutlineInspectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(id="outline-inspector", username="outline-inspector")
        Token.objects.create(user=self.user, key="inspection-token",
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer inspection-token"
        self.input = {"topic": "整理桌面", "organization": "步骤教程",
                      "audience": "零基础入门", "tone": "亲切易懂",
                      "reference_content": "每天十分钟"}

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    @patch("generation.services.outline.get_text_provider_config", return_value={"model": "synthetic"})
    @patch("generation.services.outline.OutlineService._get_client")
    @patch("generation.services.outline.load_text_providers_config", return_value={})
    def test_preview_equals_actual_snapshot_and_is_immutable(self, _providers, client, _config):
        client.return_value.generate_text.return_value = "[封面]\n上图文字：桌面\n画面描述：物品"
        preview = self.post("/api/outline/preview", self.input)
        self.assertEqual(preview.status_code, 200)
        response = self.post("/api/outline", {**self.input, "prompt_name": "obsolete"})
        self.assertEqual(response.status_code, 200)
        run = OutlineRun.objects.get()
        self.assertEqual(run.prompt, preview.json()["prompt"])
        self.assertEqual(run.prompt, client.return_value.generate_text.call_args.kwargs["prompt"])
        self.assertTrue(run.sent)
        self.assertEqual(run.status, "succeeded")
        self.post("/api/outline/preview", {**self.input, "tone": "专业简洁"})
        run.refresh_from_db()
        self.assertEqual(run.prompt, preview.json()["prompt"])

    @patch("generation.views.get_outline_service")
    def test_initialization_failure_still_leaves_inspectable_snapshot(self, service):
        service.side_effect = ValueError("model unavailable")
        self.assertGreaterEqual(self.post("/api/outline", self.input).status_code, 400)
        run = OutlineRun.objects.get()
        self.assertFalse(run.sent)
        self.assertEqual(run.status, "failed")
        self.assertEqual(self.client.get("/api/outline/records").json()["records"][0]["prompt"], run.prompt)

    def test_records_are_owner_only(self):
        other = User.objects.create(id="other-inspector", username="other-inspector")
        OutlineRun.objects.create(user=other, prompt="PRIVATE")
        self.assertEqual(self.client.get("/api/outline/records").json()["records"], [])
        self.client.defaults.clear()
        self.assertEqual(self.client.get("/api/outline/records").status_code, 401)

    @patch("generation.services.outline.get_text_provider_config", return_value={"model": "synthetic"})
    @patch("generation.services.outline.OutlineService._get_client")
    @patch("generation.services.outline.load_text_providers_config", return_value={})
    def test_douyin_preview_and_actual_request_use_the_same_platform_role(self, _providers, client, _config):
        client.return_value.generate_text.return_value = "[封面]\n上图文字：桌面\n画面描述：物品"
        data = {**self.input, "platform": "douyin"}
        preview = self.post("/api/outline/preview", data).json()["prompt"]
        self.assertTrue(preview.startswith("你是面向抖音图文创作的内容编辑。"))
        self.assertIn("用户创作的主题：\n整理桌面", preview)
        response = self.post("/api/outline", data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.return_value.generate_text.call_args.kwargs["prompt"], preview)
        self.assertEqual(OutlineRun.objects.get().prompt, preview)

    def test_invalid_custom_audience_is_rejected_without_a_model_call(self):
        response = self.post("/api/outline/preview", {**self.input, "audience": "自定义"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(OutlineRun.objects.exists())

    def test_automatic_preferences_are_in_composed_prompt(self):
        text = build_outline_prompt("主题")
        self.assertIn("自动判断", text)
        self.assertIn("自动匹配", text)
        self.assertIn("style-recommendation", text)
        self.assertIn("平台风险表达底线", text)

    def test_platform_risk_rules_follow_selected_platform(self):
        text = build_outline_prompt("主题", options={"platform": "wechat", "goal": "share"})
        self.assertIn("依据、适用范围和限制", text)
        self.assertNotIn("避免标题党", text)

    @patch("generation.services.outline.get_text_provider_config", return_value={"model": "synthetic"})
    @patch("generation.services.outline.OutlineService._get_client")
    @patch("generation.services.outline.load_text_providers_config", return_value={})
    def test_upstream_failure_keeps_actual_sent_prompt(self, _providers, client, _config):
        client.return_value.generate_text.side_effect = RuntimeError("upstream unavailable")
        response = self.post("/api/outline", self.input)
        self.assertGreaterEqual(response.status_code, 400)
        run = OutlineRun.objects.get()
        self.assertTrue(run.sent)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.prompt, client.return_value.generate_text.call_args.kwargs["prompt"])
        self.assertEqual(response.json()["generation_record"]["id"], str(run.pk))
