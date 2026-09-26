from unittest.mock import Mock, patch

from django.test import TestCase

from .services import analyze_image


class AnalysisServiceTests(TestCase):
    @patch("reference_assets.services.get_text_chat_client")
    @patch("reference_assets.services.get_text_provider_config")
    def test_analyze_image_uses_multimodal_text_client(self, get_config, get_client):
        get_config.return_value = {
            "model": "vision-model",
            "api_key": "secret",
            "type": "openai_compatible",
        }
        client = Mock()
        client.generate_text.return_value = '{"visual_style": {"prompt_text": "soft pencil"}}'
        get_client.return_value = client

        result = analyze_image(b"image-bytes", "u_test", {"topic": "coffee"})

        self.assertEqual(result["visual_style"]["prompt_text"], "soft pencil")
        client.generate_text.assert_called_once()
        self.assertEqual(client.generate_text.call_args.kwargs["images"], [b"image-bytes"])
