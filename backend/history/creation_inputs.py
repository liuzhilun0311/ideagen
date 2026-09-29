"""Validate optional private material snapshots before storing a work."""
import base64
import binascii
from generation.reference_images import (
    MAX_REFERENCE_DATA_URL_LENGTH, validate_reference_count, validate_reference_image,
)
from generation.parameters import normalize_image_parameters
from generation.reference_roles import validate_reference_roles


def validate_creation_inputs(outline):
    if not isinstance(outline, dict) or "creation_inputs" not in outline:
        return
    value = outline["creation_inputs"]
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("创作输入快照版本无效。")
    text = value.get("reference_content", "")
    if not isinstance(text, str) or len(text) > 100000:
        raise ValueError("参考资料最多100000字。")
    validate_reference_roles(value.get("reference_roles"))
    normalize_image_parameters(value.get("image_parameters"))
    if type(value.get("use_cover_reference")) is not bool:
        raise ValueError("首图参考设置无效。")
    models = value.get("models")
    if not isinstance(models, dict) or any(
        not isinstance(models.get(key), str) or len(models[key]) > 255
        for key in ("outline", "content", "image")
    ):
        raise ValueError("模型快照格式无效。")
    references = value.get("reference_images", [])
    if not isinstance(references, list):
        raise ValueError("参考图片必须为列表。")
    validate_reference_count(len(references))
    for reference in references:
        if not isinstance(reference, dict) or not isinstance(reference.get("name"), str):
            raise ValueError("参考图片快照无效。")
        data = reference.get("data")
        if not isinstance(data, str) or len(data) > MAX_REFERENCE_DATA_URL_LENGTH:
            raise ValueError("参考图片每张不超过5 MiB。")
        try:
            header, content = data.split(",", 1)
            if header not in ("data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"):
                raise ValueError()
            binary = base64.b64decode(content, validate=True)
            validate_reference_image(binary, header[5:-7])
            reference["type"] = header[5:-7]
        except (ValueError, OSError, binascii.Error):
            raise ValueError("参考图片编码或格式无效。") from None
