def resolve_text_protocol(config: dict) -> str:
    protocol = config.get("api_protocol")
    if protocol:
        if protocol not in ("responses", "chat_completions"):
            raise ValueError("不支持的文本 API 协议，请选择 Responses 或 Chat Completions")
        return protocol
    endpoint = (config.get("endpoint_type") or "").strip().rstrip("/")
    return "responses" if endpoint.endswith("/responses") else "chat_completions"
