import json
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.test import Client

from accounts.models import Token, User
from prompts.models import PromptEntry
from .models import HistoryRecord


class CustomStyleSaveTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create(id="style-owner", username="style-owner")
        self.other = User.objects.create(id="style-other", username="style-other")
        Token.objects.create(key="style-token", user=self.owner, expires_at=datetime(2099, 1, 1))
        self.style = PromptEntry.objects.create(
            id="custom-style", owner=self.owner, module="image", category="style",
            name="Reference style", content="Fine pencil lines", enabled=True,
            visibility="private",
        )
        self.record = HistoryRecord.objects.create(id="style-record", user=self.owner)

    def save_style(self, create=False):
        payload = {
            "topic": "Example", "outline": {"pages": []},
            "task_id": "style-task",
            "image_style": {"preset": self.style.pk, "notes": ""},
        }
        return getattr(self.client, "post" if create else "put")(
            "/api/history" if create else f"/api/history/{self.record.pk}",
            data=json.dumps(payload), content_type="application/json",
            HTTP_AUTHORIZATION="Bearer style-token",
        )

    @patch("history.views.valid_task_binding", return_value=True)
    @patch("history.views.get_history_service")
    def test_owner_can_create_and_update_with_custom_style(self, service, valid_task):
        service.return_value.create_record.return_value = "new-record"
        service.return_value.update_record.return_value = True
        for create in (True, False):
            response = self.save_style(create)
            self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(service.return_value.update_record.call_args.kwargs["image_style"]["preset"], self.style.pk)

    @patch("history.views.valid_task_binding", return_value=True)
    @patch("history.views.get_history_service")
    def test_disabled_and_private_other_user_styles_are_rejected(self, service, valid_task):
        for changes in ({"enabled": False}, {"enabled": True, "owner": self.other}):
            for key, value in changes.items():
                setattr(self.style, key, value)
            self.style.save()
            for create in (True, False):
                response = self.save_style(create)
                self.assertEqual(response.status_code, 400, response.content)
        service.assert_not_called()
