"""Reference image limits shared by outline requests and saved works."""
import io
from PIL import Image

MAX_REFERENCE_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REFERENCE_DATA_URL_LENGTH = 7 * 1024 * 1024
REFERENCE_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")


def validate_reference_count(count):
    if type(count) is not int or count < 0:
        raise ValueError("参考图片数量必须为非负整数。")


def validate_reference_image(binary, expected_type=None):
    if not binary or len(binary) > MAX_REFERENCE_IMAGE_BYTES:
        raise ValueError("参考图片每张必须大于0字节且不超过5 MiB。")
    try:
        with Image.open(io.BytesIO(binary)) as image:
            mime = Image.MIME.get(image.format)
            if mime not in REFERENCE_IMAGE_TYPES or (expected_type and mime != expected_type):
                raise ValueError()
            image.verify()
    except (ValueError, OSError, Image.DecompressionBombError):
        raise ValueError("参考图片编码或格式无效，仅支持 JPEG、PNG 或 WebP。") from None
    return mime
