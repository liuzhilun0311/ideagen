import base64
import io
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase
from PIL import Image

from generation.generators.image_api import ImageApiGenerator
from generation.generators.gpt_images import GptImagesClient
from generation.styles import style_prompt
from generation.parameters import apply_image_parameters
from types import SimpleNamespace


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, "PNG")
    return buffer.getvalue()


class GptImagesTests(SimpleTestCase):
    def config(self, **changes):
        return {"api_key": "synthetic-key", "base_url": "https://relay.example/v1",
                "model": "gpt-image-2", "endpoint_type": "/v1/images/generations", **changes}

    def response(self):
        return Mock(status_code=200, headers={}, json=lambda: {
            "data": [{"b64_json": base64.b64encode(png()).decode()}],
        })

    def test_generation_contract_through_existing_generator(self):
        with patch("generation.generators.gpt_images.requests.post", return_value=self.response()) as post:
            result = ImageApiGenerator(self.config()).generate_image("desk", aspect_ratio="3:4")
        self.assertTrue(result.startswith(b"\x89PNG"))
        self.assertEqual(post.call_args.args[0], "https://relay.example/v1/images/generations")
        self.assertEqual(post.call_args.kwargs["json"], {
            "model": "gpt-image-2", "prompt": "desk", "n": 1, "size": "768x1024", "output_format": "png",
            "quality": "low",
        })
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_request_selection_overrides_provider_and_reaches_upstream(self):
        config = self.config(quality="high", image_size="4K", output_format="png")
        original = SimpleNamespace(provider_config=config, generator=ImageApiGenerator(config))
        service = apply_image_parameters(original, {
            "resolution": "AUTO", "aspect_ratio": "1:1",
            "quality": "low", "output_format": "webp",
        })
        with patch("generation.generators.gpt_images.requests.post", return_value=self.response()) as post:
            service.generator.generate_image("Current page", aspect_ratio=service.provider_config["default_aspect_ratio"])
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["quality"], "low")
        self.assertEqual(payload["size"], "1024x1024")
        self.assertEqual(payload["output_format"], "webp")
        self.assertEqual(payload["n"], 1)
        self.assertEqual(original.provider_config["quality"], "high")

    def test_references_use_multipart_edit_and_real_mime(self):
        with patch("generation.generators.gpt_images.requests.post", return_value=self.response()) as post:
            ImageApiGenerator(self.config()).generate_image("desk", reference_images=[png(), png()])
        self.assertEqual(post.call_args.args[0], "https://relay.example/v1/images/edits")
        kwargs = post.call_args.kwargs
        self.assertNotIn("json", kwargs)
        self.assertNotIn("Content-Type", kwargs["headers"])
        self.assertEqual(kwargs["files"][0][0], "image[]")
        self.assertEqual(kwargs["files"][0][1][2], "image/png")
        self.assertEqual(kwargs["data"]["model"], "gpt-image-2")

    def test_selected_style_reaches_actual_image_http_payload(self):
        prompt = style_prompt('Photo of desk', {'preset': 'sketch-note', 'notes': 'blue'})
        with patch("generation.generators.gpt_images.requests.post", return_value=self.response()) as post:
            ImageApiGenerator(self.config()).generate_image(prompt)
        self.assertEqual(post.call_args.kwargs['json']['prompt'], prompt)
        self.assertIn('禁止摄影主体', post.call_args.kwargs['json']['prompt'])

    def test_generic_reference_adapter_does_not_override_selected_style(self):
        prompt = style_prompt('Desk', {'preset': 'comic'})
        generator = ImageApiGenerator(self.config(model='image-model'))
        with patch.object(generator.client, 'generate_via_images', return_value=png()) as send:
            generator._generate_via_images_api(prompt, '3:4', 'image-model', reference_images=[png()])
        actual = send.call_args.args[0]['prompt']
        self.assertIn(prompt, actual)
        self.assertEqual(actual, prompt)
        self.assertNotIn('使用相似的光影处理', actual)

    def test_responses_endpoint_fails_before_network_even_for_text_model(self):
        with patch("requests.post") as post, self.assertRaisesRegex(ValueError, "图片.*接口"):
            ImageApiGenerator(self.config(model="gpt-6-astra", endpoint_type="/v1/responses")).generate_image("test")
        post.assert_not_called()

    def test_no_retry_or_secret_in_http_and_transport_errors(self):
        for status in (400, 401, 402, 403, 404, 429, 500):
            with self.subTest(status=status), patch("generation.generators.gpt_images.requests.post",
                return_value=Mock(status_code=status, text="synthetic-key")) as post:
                with self.assertRaises(ValueError) as raised:
                    GptImagesClient(self.config()).generate_image("test")
                self.assertIn(str(status), str(raised.exception))
                self.assertNotIn("synthetic-key", str(raised.exception))
                self.assertEqual(post.call_count, 1)
        with patch("generation.generators.gpt_images.requests.post",
                   side_effect=requests.Timeout("synthetic-key")) as post:
            with self.assertRaisesRegex(ValueError, "超时"):
                GptImagesClient(self.config()).generate_image("test")
            self.assertEqual(post.call_count, 1)

    def test_non_image_success_is_rejected(self):
        for body in ({}, {"data": []}, {"data": [{"b64_json": "aGVsbG8="}]}):
            with self.subTest(body=body), patch("generation.generators.gpt_images.requests.post",
                return_value=Mock(status_code=200, headers={}, json=lambda: body)):
                with self.assertRaises(ValueError):
                    GptImagesClient(self.config()).generate_image("test")

    def test_invalid_reference_is_rejected_before_request(self):
        with patch("generation.generators.gpt_images.requests.post") as post:
            with self.assertRaises(ValueError):
                GptImagesClient(self.config()).generate_image("test", reference_images=[b"not-image"])
            post.assert_not_called()

    def test_custom_prefix_is_preserved_for_edits(self):
        with patch("generation.generators.gpt_images.requests.post", return_value=self.response()) as post:
            GptImagesClient(self.config(base_url="https://relay.example/proxy")).generate_image(
                "test", reference_images=[png()])
            self.assertEqual(post.call_args.args[0], "https://relay.example/proxy/v1/images/edits")

    def test_private_download_urls_are_rejected(self):
        client = GptImagesClient(self.config())
        with patch("generation.generators.gpt_images.urllib3.HTTPSConnectionPool") as get:
            for url in ("file:///etc/passwd", "http://127.0.0.1/test", "https://user:secret@host/a"):
                with self.assertRaises(ValueError):
                    client.download_image(url)
            get.assert_not_called()

    def test_public_image_url_is_downloaded_without_credentials(self):
        response = Mock(status_code=200, headers={}, json=lambda: {
            "data": [{"url": "https://cdn.example/image.png"}],
        })
        download = Mock(status=200)
        download.stream.return_value = [png()]
        pool = Mock()
        pool.request.return_value = download
        manager = Mock()
        manager.__enter__ = Mock(return_value=pool)
        manager.__exit__ = Mock(return_value=False)
        with patch("generation.generators.gpt_images.requests.post", return_value=response), patch(
            "generation.generators.gpt_images.socket.getaddrinfo",
            side_effect=[
                [(2, 1, 6, "", ("8.8.8.8", 443))],
                [(2, 1, 6, "", ("127.0.0.1", 443))],
            ],
        ) as dns, patch("generation.generators.gpt_images.urllib3.HTTPSConnectionPool",
                        return_value=manager) as pool_factory:
            result = GptImagesClient(self.config()).generate_image("test")
        self.assertTrue(result.startswith(b"\x89PNG"))
        dns.assert_called_once()
        self.assertEqual(pool_factory.call_args.args[0], "8.8.8.8")
        self.assertEqual(pool_factory.call_args.kwargs["server_hostname"], "cdn.example")
        self.assertEqual(pool_factory.call_args.kwargs["assert_hostname"], "cdn.example")
        self.assertEqual(pool.request.call_args.kwargs["headers"], {"Host": "cdn.example"})
        self.assertFalse(pool.request.call_args.kwargs["redirect"])
        self.assertFalse(pool.request.call_args.kwargs["retries"])
        download.close.assert_called_once()

    def test_non_json_response_is_sanitized(self):
        response = Mock(status_code=200, headers={})
        response.json.side_effect = ValueError("synthetic-key")
        with patch("generation.generators.gpt_images.requests.post", return_value=response):
            with self.assertRaisesRegex(ValueError, "JSON") as raised:
                GptImagesClient(self.config()).generate_image("test")
        self.assertNotIn("synthetic-key", str(raised.exception))
