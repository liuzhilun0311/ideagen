from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from common.api import normalize_error_result
from common.errors import classify_error
from generation.services.outline import OutlineService
from generation.utils.responses_client import ResponsesTextClient


class OutlineErrorTests(SimpleTestCase):
    def setUp(self):
        self.service = OutlineService.__new__(OutlineService)
        self.service.user_id = "outline-error-test"
        self.service.client = Mock()
        self.config = {"model": "synthetic", "api_key": "private-provider-key"}

    def generate_failure(self, message):
        self.service.client.generate_text.side_effect = ValueError(message)
        with patch("generation.services.outline.get_text_provider_config", return_value=self.config):
            return self.service.generate_outline("topic", prepared_prompt="private-prompt")

    def test_output_failures_are_not_network_errors(self):
        for message in (
            "Responses 未返回最终文本，推理过程或工具调用不能作为文案",
            "Responses 输出未完成，请减少输入长度或调整服务商输出限额",
            "中转站返回了流式数据，请确认支持 stream:false 的 Responses 请求",
            "Responses 返回的不是合法 JSON，请检查中转站协议配置",
            "生成大纲与指定页数不一致",
        ):
            with self.subTest(message=message):
                result = normalize_error_result(self.generate_failure(message))
                self.assertEqual(result["error"]["code"], "UNKNOWN_ERROR")
                self.assertEqual(result["error"]["detail"], message)

    def test_http_classification_is_preserved(self):
        for status, code in ((401, "AUTH_OR_PERMISSION"), (402, "INSUFFICIENT_BALANCE"),
                             (404, "MODEL_NOT_FOUND"), (429, "RATE_LIMITED"),
                             (502, "UPSTREAM_UNAVAILABLE")):
            with self.subTest(status=status):
                result = normalize_error_result(
                    self.generate_failure(f"Responses 请求失败（HTTP {status}）：上游拒绝请求")
                )
                self.assertEqual(result["error"]["code"], code)

    def test_logs_and_result_redact_credentials_and_prompt(self):
        with self.assertLogs("generation.services.outline", level="ERROR") as logs:
            result = self.generate_failure("invalid private-provider-key private-prompt")
        for value in (str(normalize_error_result(result)), str(logs.output)):
            self.assertNotIn("private-provider-key", value)
            self.assertNotIn("private-prompt", value)
            self.assertIn("[REDACTED]", value)

    def test_failure_before_provider_lookup_preserves_reason(self):
        with patch("generation.services.outline.build_outline_prompt",
                   side_effect=ValueError("invalid outline options")):
            self.service.prompt_template = "template"
            result = self.service.generate_outline("topic")
        self.assertEqual(result["error"], "invalid outline options")


class ResponsesTransportErrorTests(SimpleTestCase):
    def test_transport_categories_keep_safe_detail(self):
        cases = (
            (requests.ConnectTimeout, "NETWORK_TIMEOUT", "连接超时"),
            (requests.ReadTimeout, "NETWORK_TIMEOUT", "读取超时"),
            (requests.Timeout, "NETWORK_TIMEOUT", "请求超时"),
            (requests.exceptions.ProxyError, "PROXY_UNAVAILABLE", "代理"),
            (requests.exceptions.SSLError, "NETWORK_ERROR", "TLS"),
            (requests.ConnectionError, "NETWORK_ERROR", "连接失败"),
            (requests.RequestException, "UNKNOWN_ERROR", "请求发送失败"),
        )
        client = ResponsesTextClient("private-key", "https://relay.example")
        for exception, code, detail in cases:
            with self.subTest(exception=exception.__name__):
                with patch("generation.utils.responses_client.requests.post",
                           side_effect=exception("private-key private-prompt")):
                    with self.assertRaises(ValueError) as caught:
                        client.generate_text("private-prompt", model="synthetic")
                error = classify_error(caught.exception)
                self.assertEqual(error.code, code)
                self.assertIn(detail, error.detail)
                self.assertNotIn("private-key", str(error.to_dict()))
                self.assertNotIn("private-prompt", str(error.to_dict()))
