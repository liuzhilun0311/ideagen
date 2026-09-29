import base64
import io
import json
from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from accounts.models import User, Token
from .reference_images import MAX_REFERENCE_IMAGE_BYTES, validate_reference_count, validate_reference_image


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, "PNG")
    return buffer.getvalue()


class ReferenceImageLimitTests(TestCase):
    def setUp(self):
        user = User.objects.create(id="image-limits", username="image-limits")
        Token.objects.create(user=user, key="image-limits-token",
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer image-limits-token"

    def test_valid_image_and_exact_size_boundary(self):
        data = png()
        self.assertEqual(validate_reference_image(data, "image/png"), "image/png")
        self.assertEqual(validate_reference_image(data + b"\0" * (MAX_REFERENCE_IMAGE_BYTES - len(data))), "image/png")
        with self.assertRaisesRegex(ValueError, "5 MiB"):
            validate_reference_image(data + b"\0" * MAX_REFERENCE_IMAGE_BYTES)

    def test_empty_invalid_and_mismatched_types_are_rejected(self):
        for data, kind in [(b"", "image/png"), (b"text", "image/png"), (png(), "image/jpeg")]:
            with self.assertRaises(ValueError):
                validate_reference_image(data, kind)

    @patch("generation.views.get_outline_service")
    def test_multipart_limits_reject_before_model_call(self, service):
        for files in [
            [SimpleUploadedFile("big.png", b"x" * (MAX_REFERENCE_IMAGE_BYTES + 1), "image/png")],
            [SimpleUploadedFile("wrong.jpg", png(), "image/jpeg")],
        ]:
            result = self.client.post("/api/outline", {"topic": "Test", "images": files})
            self.assertGreaterEqual(result.status_code, 400)
        service.assert_not_called()

    @patch("generation.views.get_outline_service")
    def test_json_limits_reject_before_model_call(self, service):
        for images in [
            ["!" * 20],
            ["A" * (7 * 1024 * 1024 + 1)],
            "not-a-list",
        ]:
            result = self.client.post("/api/outline", json.dumps({"topic": "Test", "images": images}),
                                      content_type="application/json")
            self.assertGreaterEqual(result.status_code, 400)
        service.assert_not_called()

    def test_counts_have_no_upper_limit_but_must_be_nonnegative_integers(self):
        for count in (0, 6, 20, 1000):
            validate_reference_count(count)
        for count in (-1, 1.5, True, "6", None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                validate_reference_count(count)

    @patch("generation.views.get_outline_service")
    def test_more_than_five_images_reach_generation_in_both_formats(self, service):
        service.return_value.generate_outline.return_value = {"success": True, "pages": []}
        for multipart in (True, False):
            with self.subTest(multipart=multipart):
                if multipart:
                    response = self.client.post("/api/outline", {
                        "topic": "Test",
                        "images": [SimpleUploadedFile(f"{i}.png", png(), "image/png") for i in range(101)],
                    })
                else:
                    response = self.client.post("/api/outline", json.dumps({
                        "topic": "Test", "images": ["data:image/png;base64," + base64.b64encode(png()).decode()] * 12,
                    }), content_type="application/json")
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(len(service.return_value.generate_outline.call_args.args[1]), 101 if multipart else 12)

    def test_preview_accepts_large_counts(self):
        for endpoint, data in (
            ("/api/outline/preview", {"topic": "Test", "image_count": 25}),
            ("/api/image-prompt/preview", {"page": {"type": "content", "content": "Test"}, "reference_count": 25}),
        ):
            response = self.client.post(endpoint, json.dumps(data), content_type="application/json")
            self.assertEqual(response.status_code, 200, response.content)
