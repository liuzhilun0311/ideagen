from unittest.mock import Mock, patch
from django.test import SimpleTestCase

from .diagnostics import capture, sanitize, upstream_post


class DiagnosticTransportTests(SimpleTestCase):
    def test_redaction_keeps_usage(self):
        result = sanitize({
            "api_key": "private", "usage": {"input_tokens": 42},
            "data": [{"b64_json": "large-image", "url": "https://example.com/a?signature=private"}],
            "error": "private sk-example",
        }, ("private",))
        self.assertNotIn("private", str(result))
        self.assertNotIn("large-image", str(result))
        self.assertEqual(result["usage"]["input_tokens"], 42)

    @patch("generation.diagnostics.record")
    def test_each_attempt_records_response_and_context_resets(self, record):
        response = Mock(status_code=429, headers={"x-request-id": "req-1", "set-cookie": "private"})
        response.json.return_value = {"error": {"message": "limit"}, "usage": {"input_tokens": 10}}
        post = Mock(return_value=response)
        with capture("task", 2):
            for _ in range(2):
                self.assertIs(upstream_post(post, "https://example.com", json={"prompt": "test"}), response)
        self.assertEqual(record.call_count, 4)
        event = record.call_args.args[1]
        self.assertEqual(event["page_index"], 2)
        self.assertEqual(event["http_status"], 429)
        self.assertEqual(event["headers"], {"x-request-id": "req-1"})
        self.assertEqual(event["body"]["usage"]["input_tokens"], 10)
        upstream_post(post, "https://example.com")
        self.assertEqual(record.call_count, 4)

    @patch("generation.diagnostics.record")
    def test_connection_error_recorded_without_retry(self, record):
        post = Mock(side_effect=TimeoutError("private"))
        with capture("task", 0), self.assertRaises(TimeoutError):
            upstream_post(post, "https://example.com", diagnostic_secret="private")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(record.call_args.args[1]["error"], "[REDACTED]")
