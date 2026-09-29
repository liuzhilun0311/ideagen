from django.test import TestCase

from accounts.models import User
from history.models import HistoryRecord
from history.services import HistoryService


class GenerationAuditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(id="audit-user", username="audit-user")
        self.record = HistoryRecord.objects.create(
            id="audit-record",
            user=self.user,
            title="审计记录",
            outline={"raw": "主题", "pages": []},
        )
        self.service = HistoryService()

    def test_history_record_accepts_generation_audit(self):
        self.record.generation_audit = {"effective": {"platform": "douyin"}}
        self.record.save(update_fields=["generation_audit"])
        self.record.refresh_from_db()
        self.assertEqual(self.record.generation_audit["effective"]["platform"], "douyin")

    def test_service_serializes_and_merges_audit_without_dropping_phases(self):
        self.service.update_record(
            self.record.id,
            generation_audit={
                "context": {"growth": {"platform": "douyin"}},
                "effective": {"platform": "douyin", "layout": "hook-cover"},
                "prompts": [{"phase": "outline", "prompt_name": "outline-v1"}],
            },
        )
        self.service.update_record(
            self.record.id,
            generation_audit={
                "effective": {"goal": "follow", "image_style": "infographic"},
                "prompts": [{"phase": "image", "prompt_name": "image-v1"}],
            },
        )

        detail = self.service.get_record(self.record.id)
        self.assertEqual(detail["generation_audit"]["effective"]["platform"], "douyin")
        self.assertEqual(detail["generation_audit"]["effective"]["goal"], "follow")
        self.assertEqual(detail["generation_audit"]["effective"]["layout"], "hook-cover")
        self.assertEqual(
            [item["phase"] for item in detail["generation_audit"]["prompts"]],
            ["outline", "image"],
        )

    def test_service_replaces_same_phase_and_prompt_snapshot(self):
        self.service.update_record(
            self.record.id,
            generation_audit={"prompts": [{"phase": "copy", "prompt_name": "copy-v1", "rules": ["old"]}]},
        )
        self.service.update_record(
            self.record.id,
            generation_audit={"prompts": [{"phase": "copy", "prompt_name": "copy-v1", "rules": ["new"]}]},
        )
        detail = self.service.get_record(self.record.id)
        self.assertEqual(detail["generation_audit"]["prompts"], [
            {"phase": "copy", "prompt_name": "copy-v1", "rules": ["new"]},
        ])
