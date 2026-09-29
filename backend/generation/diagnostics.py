"""Best-effort, redacted image-generation diagnostics."""
import json
import os
import threading
import re
import time
from uuid import uuid4
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

_lock = threading.Lock()
_context = ContextVar("image_diagnostics", default=None)


@contextmanager
def capture(task_id, page_index, generation_id=None):
    token = _context.set((task_id, page_index, generation_id))
    try:
        yield
    finally:
        _context.reset(token)


def record_current(event, secrets=()):
    context = _context.get()
    if context:
        task_id, index, generation_id = context
        metadata = {"page_index": index, "source": "local"}
        if generation_id:
            metadata["generation_id"] = generation_id
        record(task_id, sanitize({**metadata, **event}, secrets))


def sanitize(value, secrets=(), key=""):
    name = key.lower().replace("-", "_")
    if any(part in name for part in ("authorization", "cookie", "api_key", "secret", "token")) and "tokens" not in name:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): sanitize(v, secrets, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item, secrets, key) for item in value]
    if isinstance(value, bytes):
        return {"omitted": "binary", "bytes": len(value)}
    if isinstance(value, str):
        if name in ("b64_json", "base64") or value.startswith("data:image/"):
            return {"omitted": "image_base64", "characters": len(value)}
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", value)
        value = re.sub(r"(https?://[^\s?\"<>]+)\?[^\s\"<>]+", r"\1?[REDACTED]", value)
        return value
    return value if value is None or isinstance(value, (bool, int, float)) else str(type(value).__name__)


def upstream_post(post, url, *, diagnostic_secret="", detect_json_encoding=False, **kwargs):
    """Capture each transport attempt without changing retry policy."""
    context = _context.get()
    if not context:
        return post(url, **kwargs)
    task_id, index, generation_id = context
    started = time.monotonic()
    common = {"page_index": index, "source": "upstream", "attempt_id": uuid4().hex}
    if generation_id:
        common["generation_id"] = generation_id
    record(task_id, sanitize({
        **common, "event": "request", "endpoint": url,
        "body": kwargs.get("json", kwargs.get("data")),
        "files": kwargs.get("files", []),
    }, (diagnostic_secret,)))
    try:
        response = post(url, **kwargs)
    except Exception as exc:
        record(task_id, sanitize({**common, "event": "response", "status": "network_error",
                                 "elapsed_ms": round((time.monotonic() - started) * 1000),
                                 "error": str(exc)}, (diagnostic_secret,)))
        raise
    if detect_json_encoding:
        response.encoding = None
    try:
        body = response.json()
    except ValueError:
        body = response.text[:20000]
    headers = {k: v for k, v in response.headers.items()
               if k.lower() in ("content-type", "retry-after", "x-request-id", "request-id",
                                "x-trace-id", "traceparent", "date")}
    record(task_id, sanitize({
        **common, "event": "response", "http_status": response.status_code,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "headers": headers, "body": body,
    }, (diagnostic_secret,)))
    return response


def _path(task_id):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "diagnostics"))
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, f"{task_id}.jsonl")


def record(task_id, event):
    if not task_id:
        return
    try:
        with _lock, open(_path(task_id), "a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), **event}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read(task_id):
    try:
        with open(_path(task_id), encoding="utf-8") as stream:
            return [json.loads(line) for line in stream if line.strip()]
    except (OSError, ValueError):
        return []
