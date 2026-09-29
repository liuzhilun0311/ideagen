import json
import io
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import requests
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from accounts.models import User, Token
from .models import OutlineRun
from .utils.responses_client import ResponsesTextClient


class OutlineDiagnosticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(id="diagnostics-owner", username="diagnostics-owner")
        Token.objects.create(user=self.user, key="diagnostics-token",
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer diagnostics-token"
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.patch("generation.diagnostics._path",
                   side_effect=lambda task: str(self.directory / f"{task}.jsonl"))
        self.config = {"api_key": "private-provider-key", "model": "synthetic",
                       "base_url": "https://relay.example", "api_protocol": "responses"}
        self.patch("generation.services.outline.load_text_providers_config", return_value={})
        self.patch("generation.services.outline.get_text_provider_config", return_value=self.config)
        self.patch("generation.services.outline.OutlineService._get_client",
                   return_value=ResponsesTextClient(self.config["api_key"], self.config["base_url"]))
        self.post = self.patch("generation.utils.responses_client.requests.post")

    def patch(self, *args, **kwargs):
        patcher = patch(*args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def response(self, status=200, body=None):
        result = requests.Response()
        result.status_code = status
        result.headers["Content-Type"] = "text/event-stream"
        result.headers["Set-Cookie"] = "private-provider-key"
        result.encoding = "ISO-8859-1"
        result._content = json.dumps(body or {
            "status": "completed", "output_text": "[封面]\n上图文字：桌面\n画面描述：桌面",
        }, ensure_ascii=False).encode("utf-8")
        return result

    def generate(self):
        return self.client.post("/api/outline", json.dumps({"topic": "桌面", "page_count": 1}),
                                content_type="application/json")

    def diagnostics(self, record_id):
        return self.client.get(f"/api/outline/records/{record_id}/diagnostics")

    def test_success_records_real_request_response_and_decodes_chinese(self):
        self.post.return_value = self.response()
        result = self.generate()
        self.assertEqual(result.status_code, 200)
        record_id = result.json()["generation_record"]["id"]
        response = self.diagnostics(record_id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        data = response.json()
        self.assertTrue(data["response_available"])
        upstream = [event for event in data["events"] if event["source"] == "upstream"]
        self.assertEqual(len(upstream), 2)
        self.assertEqual(upstream[0]["body"]["model"], "synthetic")
        self.assertEqual(upstream[1]["http_status"], 200)
        self.assertIn("[封面]", upstream[1]["body"]["output_text"])
        self.assertNotIn("private-provider-key", response.content.decode())
        self.assertNotIn("Set-Cookie", response.content.decode())

    def test_http_failure_keeps_record_and_redacts_error_body(self):
        self.post.return_value = self.response(403, {
            "error": {"message": "private-provider-key sk-example"},
            "image": "data:image/png;base64,PRIVATE",
        })
        result = self.generate()
        self.assertEqual(result.status_code, 403)
        response = self.diagnostics(result.json()["generation_record"]["id"])
        data = response.json()
        self.assertEqual(data["status"], "failed")
        self.assertTrue(any(event.get("http_status") == 403 for event in data["events"]))
        for secret in ("private-provider-key", "sk-example", "PRIVATE"):
            self.assertNotIn(secret, response.content.decode())

    def test_timeout_records_failure_without_retry(self):
        self.post.side_effect = requests.ReadTimeout("private-provider-key")
        result = self.generate()
        self.assertEqual(result.status_code, 504)
        events = self.diagnostics(result.json()["generation_record"]["id"]).json()["events"]
        self.assertTrue(any(event.get("status") == "network_error" for event in events))
        self.assertNotIn("private-provider-key", str(events))
        self.post.assert_called_once()

    def test_initialization_failure_returns_record_id(self):
        self.patch("generation.views.get_outline_service", side_effect=ValueError("unconfigured provider"))
        response = self.generate()
        self.assertEqual(response.status_code, 500)
        data = self.diagnostics(response.json()["generation_record"]["id"]).json()
        self.assertEqual(data["status"], "failed")
        self.assertIn("unconfigured provider", str(data["events"]))

    def test_raw_output_is_available_when_page_validation_fails(self):
        self.post.return_value = self.response(body={
            "status": "completed", "output_text": "[内容]\n上图文字：桌面\n画面描述：桌面",
        })
        result = self.generate()
        self.assertEqual(result.status_code, 500)
        events = self.diagnostics(result.json()["generation_record"]["id"]).json()["events"]
        self.assertTrue(any("[内容]" in str(event.get("body", {})) for event in events))
        self.assertEqual(events[-1]["status"], "failed")

    def test_reference_image_bytes_are_not_recorded_in_transport(self):
        image = io.BytesIO()
        Image.new("RGB", (2, 2)).save(image, format="PNG")
        self.post.return_value = self.response()
        result = self.client.post("/api/outline", {
            "topic": "桌面", "page_count": "1",
            "images": SimpleUploadedFile("ref.png", image.getvalue(), content_type="image/png"),
        })
        self.assertEqual(result.status_code, 200)
        events = self.diagnostics(result.json()["generation_record"]["id"]).json()["events"]
        self.assertNotIn("base64,", str(events))
        self.assertIn("image_base64", str(events))

    def test_legacy_snapshot_has_no_fabricated_response_or_image_payload(self):
        run = OutlineRun.objects.create(user=self.user, prompt="Saved prompt", status="failed",
                                        references=[{"bytes": 10, "thumbnail": "PRIVATE"}])
        data = self.diagnostics(run.pk).json()
        self.assertFalse(data["response_available"])
        self.assertEqual(data["events"][0]["source"], "snapshot")
        self.assertEqual(data["events"][0]["prompt"], "Saved prompt")
        self.assertNotIn("PRIVATE", str(data))

    def test_owner_only_and_invalid_identifiers(self):
        other = User.objects.create(id="diagnostics-other", username="diagnostics-other")
        run = OutlineRun.objects.create(user=other, prompt="PRIVATE")
        self.assertEqual(self.diagnostics(run.pk).status_code, 404)
        self.assertEqual(self.diagnostics("not-a-uuid").status_code, 400)
        self.client.defaults.clear()
        self.assertEqual(self.diagnostics(run.pk).status_code, 401)
