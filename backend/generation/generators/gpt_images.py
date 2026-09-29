"""Synchronous GPT Images generation and reference-image editing."""
import base64
import binascii
import io
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

import requests
import urllib3
from PIL import Image, UnidentifiedImageError

from .image_provider_policy import ImageProviderPolicy
from ..diagnostics import upstream_post


MAX_IMAGE_BYTES = 50 * 1024 * 1024


def validate_image_endpoint(endpoint):
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/responses"):
        raise ValueError(
            "图片模型与接口不匹配：图片生成不能使用 /v1/responses；"
            "请配置图片模型和 /v1/images/generations 或 /v1/images/edits 接口"
        )


def _image_info(data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("图片数据为空、格式错误或超过 50MB")
    try:
        with Image.open(io.BytesIO(data)) as image:
            mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image.format)
            image.verify()
            if not mime:
                raise ValueError("只支持 PNG、JPEG 和 WebP 图片")
            return mime
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise ValueError("图片接口返回或参考图包含无效图片数据") from None


def _png_bytes(data):
    _image_info(data)
    with Image.open(io.BytesIO(data)) as image:
        out = io.BytesIO()
        image.save(out, "PNG")
        return out.getvalue()


def image_size(aspect_ratio, resolution):
    sizes = {
        "1:1": (1024, 1024), "3:4": (768, 1024), "4:3": (1024, 768),
        "2:3": (1024, 1536), "3:2": (1536, 1024), "4:5": (1024, 1280),
        "5:4": (1280, 1024), "9:16": (768, 1360), "16:9": (1360, 768),
        "21:9": (1536, 656),
    }
    if aspect_ratio not in sizes:
        raise ValueError("不支持的图片宽高比")
    width, height = sizes[aspect_ratio]
    scale = {"1K": 1, "2K": 2, "4K": 4}.get(resolution)
    if scale is None:
        raise ValueError("图片分辨率只支持 1K、2K、4K")
    # Cap the longest edge at 4096 while preserving the requested ratio.
    factor = min(scale, 4096 / max(width, height))
    return f"{round(width * factor / 16) * 16}x{round(height * factor / 16) * 16}"


class GptImagesClient:
    def __init__(self, config):
        self.policy = ImageProviderPolicy.from_config(config)
        self.config = config
        parsed = urlsplit(self.policy.base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.netloc
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("图片 Base URL 必须为不含凭据或查询参数的 HTTP(S) 地址")
        endpoint = self.policy.endpoint_type.rstrip("/")
        validate_image_endpoint(endpoint)
        if not (endpoint.endswith("/images/generations") or endpoint.endswith("/images/edits")) or "?" in endpoint or "#" in endpoint:
            raise ValueError("GPT 图片模型与接口不匹配：请使用 /v1/images/generations 或 /v1/images/edits 图片接口")
        if not isinstance(self.policy.api_key, str) or not self.policy.api_key.strip():
            raise ValueError("图片 API Key 未配置")
        self.endpoint = self.policy.base_url + endpoint

    def generate_image(self, prompt, aspect_ratio="3:4", model=None, reference_images=None):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("图片提示词不能为空")
        payload = {
            "n": 1,
            "model": model or self.policy.model,
            "prompt": prompt,
            "size": image_size(aspect_ratio, self.config.get("image_size", "1K")),
            "output_format": self.config.get("output_format", "png"),
        }
        quality = self.config.get("quality")
        payload["quality"] = quality or "low"
        headers = {"Authorization": f"Bearer {self.policy.api_key}", "Accept": "application/json"}
        kwargs = {"headers": headers, "timeout": 300, "allow_redirects": False}
        url = self.endpoint
        if reference_images:
            files = []
            for index, data in enumerate(reference_images):
                mime = _image_info(data)
                extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
                files.append(("image[]" if len(reference_images) > 1 else "image",
                              (f"reference-{index}.{extension}", data, mime)))
            kwargs.update(data=payload, files=files)
            url = self.endpoint.rsplit("/", 1)[0] + "/edits"
        else:
            if url.endswith("/edits"):
                url = url.removesuffix("/edits") + "/generations"
            payload["n"] = 1
            kwargs["json"] = payload
        try:
            response = upstream_post(requests.post, url, diagnostic_secret=self.policy.api_key, **kwargs)
        except requests.RequestException:
            # A timed-out POST can still incur a charge; do not auto-resubmit.
            raise ValueError("图片请求连接失败或超时；未自动重试，请先检查中转站任务和计费记录") from None
        if response.status_code != 200:
            hint = {
                400: "图片参数不兼容，请检查模型和尺寸",
                401: "API Key 无效或已过期", 402: "账户余额不足",
                403: "当前 API Key 没有图片生成权限",
                404: "图片模型或图片接口不存在",
                429: "图片请求被限流，请检查并发和账户配额",
            }.get(response.status_code, "图片服务暂时不可用，请检查中转站状态")
            raise ValueError(f"图片请求失败（HTTP {response.status_code}）：{hint}")
        if "text/event-stream" in response.headers.get("Content-Type", "").lower():
            raise ValueError("图片接口返回流式数据，当前需要同步 JSON 图片响应")
        try:
            result = response.json()
        except ValueError:
            raise ValueError("图片接口未返回有效 JSON") from None
        data = result.get("data") if isinstance(result, dict) and not result.get("error") else None
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise ValueError("图片接口未返回可用的 data 图片数据")
        item = data[0]
        if isinstance(item.get("b64_json"), str):
            encoded = item["b64_json"]
            if len(encoded) > MAX_IMAGE_BYTES * 4 / 3 + 4:
                raise ValueError("返回图片超过 50MB")
            try:
                image = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError("图片接口返回无效 Base64 图片") from None
        elif isinstance(item.get("url"), str):
            image = self.download_image(item["url"])
        else:
            raise ValueError("图片接口未返回 b64_json 或图片 URL")
        _image_info(image)
        return image

    def download_image(self, url):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("图片下载地址必须是不含凭据的公网 HTTPS 地址")
        try:
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
                raise ValueError("图片下载地址不能指向内网或本机")
            ips = [row[4][0] for row in addresses]
            pinned_ip = next((ip for ip in ips if ipaddress.ip_address(ip).version == 4), ips[0])
        except (OSError, ValueError):
            raise ValueError("图片下载地址无法解析为公网地址") from None
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        try:
            # Pin TCP to the checked IP; keep the original TLS SNI and certificate
            # hostname. No second hostname resolution or environment proxy is used.
            with urllib3.HTTPSConnectionPool(
                pinned_ip, port=parsed.port or 443, server_hostname=parsed.hostname,
                assert_hostname=parsed.hostname, cert_reqs=ssl.CERT_REQUIRED,
                ca_certs=requests.certs.where(),
            ) as pool:
                response = pool.request(
                    "GET", path, headers={"Host": parsed.netloc},
                    timeout=urllib3.Timeout(connect=10, read=60),
                    retries=False, redirect=False, preload_content=False,
                )
                try:
                    if response.status != 200:
                        raise ValueError(f"图片下载失败（HTTP {response.status}）")
                    chunks, length = [], 0
                    for chunk in response.stream(64 * 1024):
                        length += len(chunk)
                        if length > MAX_IMAGE_BYTES:
                            raise ValueError("下载图片超过 50MB")
                        chunks.append(chunk)
                    return b"".join(chunks)
                finally:
                    response.close()
        except (urllib3.exceptions.HTTPError, OSError):
            raise ValueError("图片下载连接失败或超时") from None
