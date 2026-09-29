import io
import json
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase
from PIL import Image

from generation.utils.responses_client import ResponsesTextClient, extract_response_text
from generation.utils.text_client import TextChatClient, get_text_chat_client
from generation.utils.text_protocol import resolve_text_protocol


def completed(text="Generated copy"):
    return {
        "status": "completed",
        "output": [{"type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": text}]}],
    }


class TextProtocolTests(SimpleTestCase):
    def test_legacy_and_inferred_protocols(self):
        self.assertEqual(resolve_text_protocol({}), "chat_completions")
        self.assertEqual(resolve_text_protocol({"endpoint_type": "v1/responses/"}), "responses")
        self.assertEqual(resolve_text_protocol({
            "api_protocol": "responses", "endpoint_type": "/custom/text",
        }), "responses")

    def test_unknown_protocol_rejected(self):
        with self.assertRaises(ValueError):
            resolve_text_protocol({"api_protocol": "unknown"})

    def test_factory_uses_responses_and_keeps_legacy(self):
        base = {"type": "openai_compatible", "api_key": "test-only-not-a-key"}
        self.assertIsInstance(get_text_chat_client(base), TextChatClient)
        self.assertIsInstance(get_text_chat_client({**base, "api_protocol": "responses"}), ResponsesTextClient)
        self.assertIsInstance(get_text_chat_client({**base, "endpoint_type": "/v1/responses"}), ResponsesTextClient)


class ResponsesTextTests(SimpleTestCase):
    def setUp(self):
        self.post = patch("generation.utils.responses_client.requests.post").start()
        self.addCleanup(patch.stopall)
        self.post.return_value = Mock(status_code=200, headers={"Content-Type": "application/json"})
        self.post.return_value.json.return_value = completed()
        self.client = ResponsesTextClient("test-only-not-a-key", "https://relay.example/v1/")

    def test_minimal_gateway_payload_and_exact_model(self):
        result = self.client.generate_text("Write copy", model="gpt-6-astra", temperature=1.0, max_output_tokens=4000)
        self.assertEqual(result, "Generated copy")
        self.assertEqual(self.post.call_args.args[0], "https://relay.example/v1/responses")
        self.assertEqual(self.post.call_args.kwargs["json"], {
            "model": "gpt-6-astra", "input": "Write copy", "stream": False,
        })
        self.assertEqual(self.post.call_args.kwargs["headers"]["Authorization"], "Bearer test-only-not-a-key")
        self.assertFalse(self.post.call_args.kwargs["allow_redirects"])

    def test_system_and_reference_images_use_responses_blocks(self):
        data = io.BytesIO()
        Image.new("RGB", (2, 2)).save(data, format="JPEG")
        self.client.generate_text("Describe", model="custom-model", system_prompt="Editorial style",
                                  images=[data.getvalue(), "https://images.example/photo.png"])
        payload = self.post.call_args.kwargs["json"]
        self.assertEqual(payload["input"][0], {
            "role": "system", "content": [{"type": "input_text", "text": "Editorial style"}],
        })
        content = payload["input"][1]["content"]
        self.assertEqual(content[0], {"type": "input_text", "text": "Describe"})
        self.assertTrue(content[1]["image_url"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(content[2], {"type": "input_image", "image_url": "https://images.example/photo.png"})

    def test_custom_path_and_timeout(self):
        ResponsesTextClient("test-only-not-a-key", "https://relay.example", "/gateway/responses", timeout=30).generate_text("Test", model="relay-alias")
        self.assertEqual(self.post.call_args.args[0], "https://relay.example/gateway/responses")
        self.assertEqual(self.post.call_args.kwargs["timeout"], 30)

    def test_missing_model_fails_before_network(self):
        with self.assertRaises(ValueError):
            self.client.generate_text("Test", model="")
        self.post.assert_not_called()

    def test_missing_key_and_invalid_url_rejected(self):
        for key, base in [("", "https://relay.example"), ("test", "file:///tmp"), ("test", "https://user:pass@relay.example")]:
            with self.subTest(base=base), self.assertRaises(ValueError):
                ResponsesTextClient(key, base)

    def test_http_errors_do_not_echo_secret_or_server_body(self):
        for status in [301, 400, 401, 403, 404, 429, 500]:
            self.post.return_value.status_code = status
            self.post.return_value.text = "test-only-not-a-key private input"
            with self.subTest(status=status), self.assertRaises(ValueError) as caught:
                self.client.generate_text("Test", model="relay-alias")
            self.assertIn(str(status), str(caught.exception))
            self.assertNotIn("test-only-not-a-key", str(caught.exception))
            self.assertNotIn("private input", str(caught.exception))

    def test_transport_and_non_json_errors(self):
        self.post.side_effect = requests.Timeout("test-only-not-a-key")
        with self.assertRaises(ValueError) as caught:
            self.client.generate_text("Test", model="relay-alias")
        self.assertNotIn("test-only-not-a-key", str(caught.exception))
        self.post.side_effect = None
        self.post.return_value.json.side_effect = ValueError("private body")
        with self.assertRaises(ValueError) as caught:
            self.client.generate_text("Test", model="relay-alias")
        self.assertNotIn("private body", str(caught.exception))

    def test_unexpected_stream_is_not_a_success(self):
        self.post.return_value.headers = {"Content-Type": "text/event-stream"}
        self.post.return_value.json.side_effect = ValueError("data: private body")
        with self.assertRaises(ValueError):
            self.client.generate_text("Test", model="relay-alias")

    def test_completed_json_with_mislabeled_stream_header_is_accepted(self):
        self.post.return_value.headers = {"Content-Type": "text/event-stream; charset=utf-8"}
        self.assertEqual(
            self.client.generate_text("Test", model="relay-alias"), "Generated copy"
        )

    def test_mislabeled_incomplete_json_is_not_a_success(self):
        self.post.return_value.headers = {"Content-Type": "text/event-stream"}
        self.post.return_value.json.return_value = {
            "status": "incomplete", "output_text": "Partial",
        }
        with self.assertRaisesRegex(ValueError, "输出未完成"):
            self.client.generate_text("Test", model="relay-alias")

    def test_mislabeled_json_does_not_decode_chinese_as_latin1(self):
        text = "[封面]\n上图文字：整理桌面\n画面描述：桌面"
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "text/event-stream"
        response.encoding = "ISO-8859-1"
        response._content = json.dumps(completed(text), ensure_ascii=False).encode("utf-8")
        self.post.return_value = response
        self.assertEqual(self.client.generate_text("Test", model="relay-alias"), text)


class ResponseExtractionTests(SimpleTestCase):
    def test_multiple_text_blocks_ignore_reasoning(self):
        response = completed("First")
        response["output"].insert(0, {"type": "reasoning", "summary": [{"text": "Private reasoning"}]})
        response["output"][1]["content"].append({"type": "output_text", "text": "Second"})
        self.assertEqual(extract_response_text(response), "First\nSecond")

    def test_top_level_text_compatibility(self):
        self.assertEqual(extract_response_text({"status": "completed", "output_text": "Hello"}), "Hello")

    def test_invalid_and_unfinished_responses_rejected(self):
        examples = [
            [], {}, {"output": []}, {"output_text": " "},
            {"status": "failed", "output_text": "Partial"},
            {"status": "incomplete", "output_text": "Partial"},
            {"status": "in_progress", "output_text": "Partial"},
            {"error": {"message": "Sensitive"}, "output_text": "Partial"},
            {"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "No"}]}]},
            {"output": [{"type": "function_call", "arguments": "Not copy"}]},
            {"output": [{"type": "message", "status": "incomplete",
                         "content": [{"type": "output_text", "text": "Partial"}]}]},
        ]
        for response in examples:
            with self.subTest(response=response), self.assertRaises(ValueError):
                extract_response_text(response)
