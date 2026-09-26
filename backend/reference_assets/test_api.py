import io
import json
from datetime import datetime
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from PIL import Image

from accounts.auth import _hash_password
from accounts.models import Token, User
from .models import ImageAnalysis, ReferenceAsset


def png_upload(name="reference.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 255, 255)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class ReferenceAssetApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            id="u_api_owner",
            username="api-owner",
            password_hash=_hash_password("secret123"),
        )
        self.other = User.objects.create(
            id="u_api_other",
            username="api-other",
            password_hash=_hash_password("secret123"),
        )
        expires_at = datetime(2099, 1, 1)
        self.token = Token.objects.create(key="token-owner", user=self.user, expires_at=expires_at)
        self.other_token = Token.objects.create(key="token-other", user=self.other, expires_at=expires_at)

    def auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.token.key}"}

    @patch("reference_assets.views.analyze_image")
    def test_analyze_creates_owner_scoped_record(self, analyze_image):
        analyze_image.return_value = {
            "content": {"summary": "咖啡"},
            "layout": {"prompt_text": "居中布局"},
            "visual_style": {"prompt_text": "柔和手绘"},
            "rewritten_content": "改写内容",
        }

        response = self.client.post(
            "/api/image-analysis",
            {"image": png_upload(), "topic": "咖啡"},
            **self.auth(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        analysis = ImageAnalysis.objects.get()
        self.assertEqual(analysis.owner_id, self.user.id)
        self.assertEqual(response.json()["analysis"]["content"]["summary"], "咖啡")

    def test_other_user_cannot_read_analysis(self):
        analysis = ImageAnalysis.objects.create(owner=self.user, content={"summary": "private"})

        response = self.client.get(
            f"/api/image-analysis/{analysis.pk}",
            **self.auth(self.other_token.key),
        )

        self.assertEqual(response.status_code, 404)

    def test_apply_returns_only_requested_parts(self):
        analysis = ImageAnalysis.objects.create(
            owner=self.user,
            content={"summary": "content"},
            layout={"prompt_text": "layout"},
            visual_style={"prompt_text": "style"},
        )

        response = self.client.post(
            f"/api/image-analysis/{analysis.pk}/apply",
            data=json.dumps({"parts": ["layout"], "mode": "merge"}),
            content_type="application/json",
            **self.auth(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["applied"]["layout"]["prompt_text"], "layout")
        self.assertNotIn("content", response.json()["applied"])

    def test_create_reference_asset_and_delete_isolated_source(self):
        analysis = ImageAnalysis.objects.create(owner=self.user, content={"summary": "saved"})

        response = self.client.post(
            "/api/reference-assets",
            data=json.dumps({
                "analysis_id": str(analysis.pk),
                "title": "我的参考",
                "rewritten_content": "可用内容",
            }),
            content_type="application/json",
            **self.auth(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        asset = ReferenceAsset.objects.get()
        self.assertEqual(asset.owner_id, self.user.id)
        delete = self.client.delete(f"/api/reference-assets/{asset.pk}", **self.auth())
        self.assertEqual(delete.status_code, 200, delete.content)
        self.assertFalse(ReferenceAsset.objects.exists())

    def test_prompt_creation_rejects_content_part(self):
        analysis = ImageAnalysis.objects.create(owner=self.user, layout={"prompt_text": "layout"})

        response = self.client.post(
            "/api/prompt-center/from-analysis",
            data=json.dumps({"analysis_id": str(analysis.pk), "parts": ["content"]}),
            content_type="application/json",
            **self.auth(),
        )

        self.assertEqual(response.status_code, 400)
