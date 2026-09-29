"""Encode the stored artifact explicitly, independently of upstream transport."""
import io
from PIL import Image


def encode_output(data, output_format="png"):
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        width, height = image.size
        target = output_format.upper()
        if target not in ("PNG", "JPEG", "WEBP"):
            raise ValueError("图片输出格式无效。")
        output = io.BytesIO()
        if target == "JPEG":
            image = image.convert("RGB")
        image.save(output, target, **({"quality": 95} if target in ("JPEG", "WEBP") else {}))
    return output.getvalue(), {"width": width, "height": height, "format": output_format,
                               "verification": "decoded_output"}
