import json
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from accounts.models import Token, User
from history.models import HistoryRecord

from .consistency import check_content_image_consistency


class ContentImageConsistencyTests(SimpleTestCase):
    def test_matching_subject_numbers_and_cta_are_consistent(self):
        result = check_content_image_consistency(
            pages=[{
                "index": 0,
                "content": "产品A帮助小商家节省150元，想了解可以私信咨询。",
            }],
            images=[{
                "index": 0,
                "prompt": "展示产品A和150元账单，画面文字引导用户私信咨询。",
            }],
            growth_preferences={"goal": "inquiry"},
        )

        self.assertEqual(result["status"], "consistent")
        self.assertEqual(result["pages"][0]["risks"], [])

    def test_flags_unmentioned_subject_number_conclusion_and_cta(self):
        result = check_content_image_consistency(
            pages=[{
                "index": 1,
                "content": "产品A帮助小商家节省150元，想了解可以私信咨询。",
            }],
            images=[{
                "index": 1,
                "prompt": (
                    "展示产品A和产品B，标注节省999元，保证收益，"
                    "点击购买按钮。"
                ),
            }],
            growth_preferences={"goal": "inquiry"},
        )

        self.assertEqual(result["status"], "warning")
        risk_types = {risk["type"] for risk in result["pages"][0]["risks"]}
        self.assertTrue({"subject", "number", "conclusion", "cta"} <= risk_types)
        self.assertIn("产品B", result["pages"][0]["risks"][0]["detail"])

    def test_missing_prompt_is_reported_without_blocking(self):
        result = check_content_image_consistency(
            pages=[{"index": 0, "content": "只提供正文"}],
            images=[],
            growth_preferences={},
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertIn("图片提示词", result["summary"])
        self.assertEqual(result["pages"][0]["status"], "unavailable")


class ConsistencyEndpointTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create(id="consistency-owner", username="consistency-owner")
        self.other = User.objects.create(id="consistency-other", username="consistency-other")
        Token.objects.create(
            user=self.owner,
            key="consistency-token",
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.record = HistoryRecord.objects.create(
            id="consistency-record",
            user=self.owner,
            title="Consistency",
            outline={
                "pages": [{"index": 0, "type": "content", "content": "产品A，私信咨询"}],
                "generation_preferences": {"platform": "xiaohongshu", "goal": "inquiry"},
            },
            content={"copywriting": "产品A，私信咨询"},
            images={"task_id": "consistency-task", "generated": ["0.png"]},
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer consistency-token"

    def test_task_consistency_requires_read_access(self):
        response = self.client.get("/api/generation/consistency/consistency-task")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["result"]["status"], "unavailable")

        self.record.user = self.other
        self.record.save(update_fields=["user"])
        response = self.client.get("/api/generation/consistency/consistency-task")
        self.assertEqual(response.status_code, 403)

    def test_task_consistency_requires_authentication(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION")
        response = self.client.get("/api/generation/consistency/consistency-task")
        self.assertEqual(response.status_code, 401)
