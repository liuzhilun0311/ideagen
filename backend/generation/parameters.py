"""Normalize output specifications before any image generation path."""
from copy import copy

DEFAULTS = {"resolution": "1K", "aspect_ratio": "3:4",
            "quality": "low", "output_format": "png"}
OPTIONS = {
    "resolution": {"AUTO", "1K", "2K", "4K"},
    "aspect_ratio": {"1:1", "16:9", "9:16", "3:2", "2:3", "4:3", "3:4", "4:5", "5:4", "21:9"},
    "quality": {"auto", "low", "medium", "high", "ultra", "highest"},
    "output_format": {"png", "jpeg", "webp"},
}


def normalize_image_parameters(values=None):
    if values is None:
        values = {}
    if not isinstance(values, dict):
        raise ValueError("图片参数必须是对象。")
    result = {}
    for key, default in DEFAULTS.items():
        value = values.get(key)
        value = default if value is None or value == "" else value
        if not isinstance(value, str):
            raise ValueError(f"图片参数 {key} 无效。")
        value = value.strip().upper() if key == "resolution" else value.strip().lower()
        if value not in OPTIONS[key]:
            raise ValueError(f"图片参数 {key} 不支持值 {value}。")
        result[key] = "1K" if key == "resolution" and value == "AUTO" else value
    return result


def apply_image_parameters(service, values=None):
    values = normalize_image_parameters(values)
    # The default service is cached. Do not let concurrent requests overwrite it.
    service = copy(service)
    service.provider_config = dict(service.provider_config)
    service.generator = copy(service.generator)
    service.generator.config = dict(service.generator.config)
    config = {
        "image_size": values["resolution"],
        "default_aspect_ratio": values["aspect_ratio"],
        "quality": values["quality"],
        "output_format": values["output_format"],
    }
    # Both layers must see the same request-scoped specifications.
    service.provider_config.update(config)
    service.generator.config.update(config)
    from .generators.gpt_images import image_size
    service.provider_config["default_size"] = image_size(values["aspect_ratio"], values["resolution"])
    validate_provider_parameters(service.provider_config, values)
    for key in ("image_size", "default_aspect_ratio"):
        if hasattr(service.generator, key):
            setattr(service.generator, key, config[key])
    return service


def validate_provider_parameters(config, values):
    model = str(config.get("model", ""))
    provider = config.get("type")
    if model.startswith("gpt-image-"):
        return
    if provider in ("google_genai", "image_api", "openai_compatible", "openai"):
        # Older saved low settings represented the previous universal default.
        if values["quality"] not in ("auto", "low"):
            raise ValueError("当前图片接口不支持质量档位，请选择自动；旧版低档按接口默认执行。")
    endpoint = str(config.get("endpoint_type", ""))
    if provider in ("image_api", "openai_compatible", "openai") and ("chat" in endpoint or "completions" in endpoint):
        raise ValueError("此旧版聊天图片接口不支持可靠的尺寸参数，请改用图片生成接口。")
