import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from accounts.models import User, Token
from .models import ContentRun


class ContentDiagnosticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(id="copy-owner", username="copy-owner")
        Token.objects.create(user=self.user, key="copy-token",
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer copy-token"

    @patch("generation.views.get_content_service")
    def test_success_records_separate_copy_request_and_response(self, service):
        service.return_value.generate_content.return_value = {
            "success": True, "titles": ["Title"], "copywriting": "Body", "tags": [],
        }
        result = self.client.post("/api/content", json.dumps({
            "topic": "Topic", "outline": "Outline",
            "generation_preferences": {"platform": "douyin"},
        }), content_type="application/json")
        self.assertEqual(result.status_code, 200)
        run = ContentRun.objects.get()
        self.assertEqual(result.json()["generation_record"]["id"], str(run.pk))
        events = self.client.get(f"/api/content/records/{run.pk}/diagnostics").json()["events"]
        self.assertEqual([event["event"] for event in events], ["request", "response"])
        self.assertIn("douyin", events[0]["prompt"])
        self.assertEqual(events[1]["result"]["copywriting"], "Body")

    @patch("generation.views.get_content_service", side_effect=ValueError("unavailable"))
    def test_initialization_failure_has_owner_only_diagnostics(self, _service):
        result = self.client.post("/api/content", json.dumps({"topic": "Topic", "outline": "Outline"}),
                                  content_type="application/json")
        self.assertGreaterEqual(result.status_code, 400)
        run = ContentRun.objects.get()
        self.assertEqual(run.status, "failed")
        self.assertEqual(result.json()["generation_record"]["id"], str(run.pk))
        other = User.objects.create(id="copy-other", username="copy-other")
        Token.objects.create(user=other, key="copy-other-token",
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer copy-other-token"
        self.assertEqual(self.client.get(f"/api/content/records/{run.pk}/diagnostics").status_code, 404)

    @patch("generation.views.get_content_service")
    def test_rich_plain_copy_returns_warning_without_retry_or_discarding_text(self, service):
        body = "- 出行：使用安全带。\n- 居家：检查报警器。"
        service.return_value.generate_content.return_value = {
            "success": True, "titles": ["防护清单"], "copywriting": body, "tags": ["安全"],
        }
        result = self.client.post("/api/content", json.dumps({
            "topic": "日常防护", "outline": body, "copy_preferences": {"emoji_level": "丰富"},
        }), content_type="application/json")
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["copywriting"], body)
        self.assertTrue(any("正文未包含表情或信息符号" in item for item in data["validation"]["warnings"]))
        service.return_value.generate_content.assert_called_once()
