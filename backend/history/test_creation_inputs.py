import base64
import io
from django.test import SimpleTestCase
from PIL import Image
from .creation_inputs import validate_creation_inputs


class CreationInputTests(SimpleTestCase):
    def snapshot(self):
        data = io.BytesIO()
        Image.new("RGB", (8, 8)).save(data, "PNG")
        return {"creation_inputs": {
            "version": 1, "reference_content": "source", "reference_roles": ["subject"],
            "reference_images": [{"name": "reference.png", "type": "image/png",
                "data": "data:image/png;base64," + base64.b64encode(data.getvalue()).decode()}],
            "image_parameters": {"resolution": "2K"}, "use_cover_reference": False,
            "models": {"outline": "text", "content": "copy", "image": "image"},
        }}

    def test_valid_snapshot_and_legacy_outline(self):
        validate_creation_inputs(self.snapshot())
        validate_creation_inputs({"raw": "legacy", "pages": []})

    def test_more_than_five_references_can_be_saved(self):
        value = self.snapshot()
        value["creation_inputs"]["reference_images"] *= 12
        validate_creation_inputs(value)
        self.assertEqual(len(value["creation_inputs"]["reference_images"]), 12)

    def test_invalid_images_and_versions_fail(self):
        value = self.snapshot()
        value["creation_inputs"]["reference_images"][0]["data"] = "data:image/png;base64,AAAA"
        with self.assertRaises(ValueError):
            validate_creation_inputs(value)
        value = self.snapshot()
        value["creation_inputs"]["version"] = 5
        with self.assertRaises(ValueError):
            validate_creation_inputs(value)
