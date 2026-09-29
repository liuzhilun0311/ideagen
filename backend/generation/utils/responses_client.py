"""Responses adapter for relays exposing the documented minimal input contract."""
import base64
import io
from urllib.parse import urlsplit

import requests
from PIL import Image

from .image_compressor import compress_image
from ..diagnostics import upstream_post


def extract_response_text(result: dict) -> str:
    if not isinstance(result, dict):
        raise ValueError("Responses 响应格式异常：需要 JSON 对象")
    if result.get("error"):
        raise ValueError("Responses 返回错误，请检查模型权限和中转站状态")
    status = result.get("status")
    if status not in (None, "completed"):
        if status == "incomplete":
            raise ValueError("Responses 输出未完成，请减少输入长度或调整服务商输出限额")
        raise ValueError("Responses 请求尚未成功完成，请检查中转站状态")

    texts = []
    output = result.get("output", [])
    if not isinstance(output, list):
        raise ValueError("Responses 响应格式异常：output 必须为数组")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        if item.get("status") not in (None, "completed"):
            raise ValueError("Responses 消息未完成，未将部分输出作为生成结果")
        if item.get("role") not in (None, "assistant"):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            raise ValueError("Responses 响应格式异常：消息 content 必须为数组")
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "refusal":
                raise ValueError("模型拒绝生成此内容，请调整主题或参考资料")
            if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
    text = "\n".join(texts).strip()
    # Some compatible gateways also expose the SDK's output_text convenience value.
    if not text and isinstance(result.get("output_text"), str):
        text = result["output_text"].strip()
    if not text:
        raise ValueError("Responses 未返回最终文本，推理过程或工具调用不能作为文案")
    return text


def _reference_url(image) -> str:
    if isinstance(image, str):
        return image
    if not isinstance(image, bytes):
        raise ValueError("参考图格式不支持")
    compressed = compress_image(image, max_size_kb=200)
    try:
        with Image.open(io.BytesIO(compressed)) as decoded:
            mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(decoded.format)
    except (OSError, ValueError):
        raise ValueError("参考图不是有效的 JPEG、PNG 或 WebP 图片") from None
    if not mime:
        raise ValueError("参考图只支持 JPEG、PNG 和 WebP")
    return f"data:{mime};base64,{base64.b64encode(compressed).decode('ascii')}"


class ResponsesTextClient:
    def __init__(self, api_key: str, base_url: str = None, endpoint_type: str = None, timeout: int = 300):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("API Key 未配置，请在文本模型设置中填写")
        base = (base_url or "https://api.openai.com").strip().rstrip("/")
        parsed = urlsplit(base)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Base URL 必须为不含凭据、查询参数或片段的 HTTP(S) 地址")
        if base.endswith("/v1"):
            base = base[:-3]
        endpoint = (endpoint_type or "/v1/responses").strip()
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        if endpoint.startswith("//") or "://" in endpoint or "?" in endpoint or "#" in endpoint:
            raise ValueError("API 端点必须是相对路径")
        if endpoint.rstrip("/") == "/v1/chat/completions":
            raise ValueError("Responses 协议不能使用 Chat Completions 端点，请改为 /v1/responses")
        self.api_key = api_key.strip()
        self.endpoint = base + endpoint
        self.timeout = timeout

    def generate_text(self, prompt: str, model: str = "", temperature: float = 1.0,
                      max_output_tokens: int = 8000, images=None, system_prompt: str = None, **kwargs) -> str:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("请填写中转站可用的模型 ID")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("生成内容不能为空")
        input_value = prompt
        if images or system_prompt:
            input_value = []
            if system_prompt:
                input_value.append({"role": "system", "content": [{"type": "input_text", "text": system_prompt}]})
            content = [{"type": "input_text", "text": prompt}]
            content.extend({"type": "input_image", "image_url": _reference_url(image)} for image in images or [])
            input_value.append({"role": "user", "content": content})
        # Do not inherit chat-only fields or model-dependent sampling defaults.
        payload = {"model": model.strip(), "input": input_value, "stream": False}
        try:
            response = upstream_post(
                requests.post, self.endpoint, json=payload,
                diagnostic_secret=self.api_key, detect_json_encoding=True,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json"},
                timeout=self.timeout, allow_redirects=False,
            )
        except requests.exceptions.ProxyError:
            raise ValueError("Responses 代理连接失败，请检查代理服务及代理配置") from None
        except requests.exceptions.SSLError:
            raise ValueError("Responses TLS 连接失败，请检查证书、代理及中转站 HTTPS 配置") from None
        except requests.ConnectTimeout:
            raise ValueError("Responses 连接超时，请检查 Base URL、网络及中转站状态") from None
        except requests.ReadTimeout:
            raise ValueError("Responses 读取超时，中转站未及时返回结果，请稍后重试或减少输入") from None
        except requests.Timeout:
            raise ValueError("Responses 请求超时，请检查网络及中转站状态") from None
        except requests.ConnectionError:
            raise ValueError("Responses 连接失败，请检查 Base URL、DNS、网络及中转站状态") from None
        except requests.RequestException:
            raise ValueError("Responses 请求发送失败，请检查请求配置及中转站状态") from None
        if response.status_code != 200:
            hints = {
                401: "API Key 无效或已过期", 402: "中转站账户余额不足",
                403: "API Key 无此模型权限", 404: "模型 ID 或 API 端点不存在",
                429: "请求过于频繁或配额不足",
            }
            hint = hints.get(response.status_code, "请检查协议、模型及中转站状态")
            # Never include the response body: relays may echo keys or private prompts.
            raise ValueError(f"Responses 请求失败（HTTP {response.status_code}）：{hint}")
        # Some relays return completed JSON with an incorrect event-stream header.
        # Detect JSON encoding from bytes, not the text/* default of Latin-1.
        response.encoding = None
        try:
            result = response.json()
        except ValueError:
            if "text/event-stream" in response.headers.get("Content-Type", "").lower():
                raise ValueError("中转站返回了流式数据，请确认支持 stream:false 的 Responses 请求") from None
            raise ValueError("Responses 返回的不是合法 JSON，请检查中转站协议配置") from None
        return extract_response_text(result)
