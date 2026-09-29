from pathlib import Path

from django.test import SimpleTestCase

from .catalog_defaults import builtin_entries, validate_builtin_layout_previews


class LayoutPreviewContractTests(SimpleTestCase):
    def test_every_builtin_layout_has_complete_preview_metadata_and_asset(self):
        layouts = [
            entry for entry in builtin_entries(current_base=False)
            if entry["module"] == "image" and entry["category"] == "layout"
            and entry["legacy_value"] != "自动"
        ]

        self.assertGreaterEqual(len(layouts), 23)
        self.assertTrue(all({
            "preview", "preview_alt", "summary",
        } <= set(entry["metadata"]) for entry in layouts))
        self.assertEqual(
            len({entry["metadata"]["preview"] for entry in layouts}),
            len(layouts),
        )
        validate_builtin_layout_previews(layouts)

    def test_layout_preview_validator_rejects_missing_assets(self):
        layouts = [
            entry for entry in builtin_entries(current_base=False)
            if entry["module"] == "image" and entry["category"] == "layout"
            and entry["legacy_value"] != "自动"
        ]
        layouts[0]["metadata"]["preview"] = "missing-layout-preview"

        with self.assertRaisesRegex(ValueError, "missing-layout-preview"):
            validate_builtin_layout_previews(layouts)
