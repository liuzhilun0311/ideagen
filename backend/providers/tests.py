from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from providers.views import _load_provider_config, _test_openai_compatible


class ResponsesConnectionTests(SimpleTestCase):
    def test_smoke_uses_production_contract(self):
        response = Mock(status_code=200, headers={})
        response.json.return_value = {
            "status": "completed",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": "IdeaGen connection successful"},
            ]}],
        }
        for protocol in ({"api_protocol": "responses"}, {"endpoint_type": "/v1/responses"}):
            with self.subTest(protocol=protocol), patch(
                "generation.utils.responses_client.requests.post", return_value=response
            ) as post:
                result = _test_openai_compatible({
                    "api_key": "test-only-not-a-key",
                    "base_url": "https://relay.example/v1",
                    "model": "custom-model",
                    **protocol,
                }, "test")
                self.assertTrue(result["success"])
                self.assertEqual(post.call_args.args[0], "https://relay.example/v1/responses")
                self.assertEqual(post.call_args.kwargs["json"], {
                    "model": "custom-model", "input": "test", "stream": False,
                })
                self.assertEqual(post.call_args.kwargs["timeout"], 30)

    def test_empty_response_is_not_success(self):
        response = Mock(status_code=200, headers={})
        response.json.return_value = {"status": "completed", "output": [{"type": "reasoning"}]}
        with patch("generation.utils.responses_client.requests.post", return_value=response):
            with self.assertRaises(ValueError):
                _test_openai_compatible({
                    "api_key": "test-only-not-a-key", "api_protocol": "responses", "model": "custom",
                }, "test")

    def test_legacy_chat_unchanged(self):
        from providers.views import LlmSmokeResult
        with patch("providers.views._test_openai_chat_completion",
                   return_value=LlmSmokeResult("IdeaGen", "content", "stop")) as chat:
            self.assertTrue(_test_openai_compatible({}, "test")["success"])
            chat.assert_called_once_with({}, "test")


class SavedProtocolTests(SimpleTestCase):
    def merge(self, edited, saved):
        with patch("providers.views.load_text_providers_config", return_value={
            "providers": {"relay": {"api_key": "test-only-not-a-key", **saved}},
        }):
            return _load_provider_config("openai_compatible", "relay", {
                "base_url": None, "model": None, **edited,
            }, "synthetic-user")

    def test_saved_protocol_and_custom_endpoint_restored(self):
        config = self.merge({}, {"api_protocol": "responses", "endpoint_type": "/custom/responses"})
        self.assertEqual(config["api_protocol"], "responses")
        self.assertEqual(config["endpoint_type"], "/custom/responses")
        self.assertEqual(config["api_key"], "test-only-not-a-key")

    def test_edited_protocol_does_not_inherit_old_endpoint(self):
        config = self.merge({"api_protocol": "responses"}, {
            "api_protocol": "chat_completions", "endpoint_type": "/v1/chat/completions",
        })
        self.assertEqual(config["api_protocol"], "responses")
        self.assertFalse(config.get("endpoint_type"))

    def test_edited_endpoint_infers_protocol_without_saved_override(self):
        config = self.merge({"endpoint_type": "/v1/responses"}, {"api_protocol": "chat_completions"})
        self.assertFalse(config.get("api_protocol"))
        self.assertEqual(config["endpoint_type"], "/v1/responses")


class ImageConnectionTests(SimpleTestCase):
    def test_models_check_is_only_a_warning(self):
        from providers.views import _test_image_api
        with patch("requests.get", return_value=Mock(status_code=200)):
            result = _test_image_api({
                "api_key": "synthetic-key", "base_url": "https://relay.example",
                "model": "gpt-image-2", "endpoint_type": "/v1/images/generations",
            })
        self.assertTrue(result["success"])
        self.assertTrue(result["warning"])
        self.assertIn("尚未验证", result["message"])

    def test_responses_endpoint_does_not_pass_connectivity_test(self):
        from providers.views import _test_image_api
        from common.errors import classify_error
        with patch("requests.get") as get:
            with self.assertRaises(ValueError) as raised:
                _test_image_api({
                    "api_key": "synthetic-key", "base_url": "https://relay.example",
                    "model": "gpt-6-astra", "endpoint_type": "/v1/responses",
                })
            get.assert_not_called()
        self.assertEqual(classify_error(raised.exception).code, "MODEL_ENDPOINT_MISMATCH")
