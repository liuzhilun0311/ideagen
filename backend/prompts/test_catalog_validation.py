from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from library.models import LibraryOrder
from . import catalog
from .catalog_defaults import builtin_entries
from .models import PromptEntry, PromptVersion


class CatalogValidationTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        override = self.settings(USER_CONFIGS_ROOT=Path(temp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.admin = User.objects.create(id="validation-admin", username="validation-admin", is_admin=True)
        self.owner = User.objects.create(id="validation-owner", username="validation-owner")
        self.viewer = User.objects.create(id="validation-viewer", username="validation-viewer")

    def create(self, user=None, **changes):
        return catalog.save(user or self.owner, {
            "module": "image", "category": "style", "name": "Drawing",
            "content": "Draw using clean lines.", **changes,
        })

    def rejected(self, function, *args, status=400, **kwargs):
        with self.assertRaises(catalog.CatalogError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.status, status)

    def test_reserved_names_cannot_be_created_or_assigned_by_rename(self):
        entry = self.create()
        for name in ("自动", "自动判断", "自动匹配", "自动推荐", "自动选择", "自定义",
                     "自定义受众", "auto", "AUTO", "ａｕｔｏ"):
            with self.subTest(name=name):
                self.rejected(self.create, name=name)
                self.rejected(catalog.save, self.owner, {**entry, "name": name})
        self.assertEqual(PromptVersion.objects.count(), 1)

    def test_invalid_request_shapes_and_ids_are_catalog_errors(self):
        for action in (catalog.save, catalog.copy, catalog.restore, catalog.reorder):
            for data in ([], None, "bad", 12):
                with self.subTest(action=action.__name__, data=data):
                    self.rejected(action, self.owner, data)
        for key in ([], {}, True, 1, "", None, "x" * 101):
            with self.subTest(key=key):
                self.rejected(catalog.get_entry, self.owner, key)
                self.rejected(catalog.save, self.owner, {"id": key})
        for module, category in (([], "style"), ("image", {})):
            self.rejected(catalog.reorder, self.owner, {"module": module, "category": category})

    def test_restore_version_must_be_a_positive_integer(self):
        entry = self.create()
        for version in (True, False, 1.0, "1", [], {}, None, 0, -1):
            with self.subTest(version=version):
                self.rejected(catalog.restore, self.owner, {
                    "id": entry["id"], "revision": entry["revision"], "version": version,
                })
        self.assertEqual(PromptVersion.objects.count(), 1)

    def test_base_placeholders_are_module_specific_and_required(self):
        catalog.seed()
        base = catalog.serialize(PromptEntry.objects.get(pk="outline.base.default"), self.admin)
        for content in ("Missing topic", "{topic} {outline}", "{topic} {unknown}",
                        "{topic} {topic.__class__}", "{topic} {topic!r}", "{{topic}}"):
            with self.subTest(content=content):
                self.rejected(catalog.save, self.admin, {**base, "content": content})
        result = catalog.save(self.admin, {**base, "content": '{platform_name}\n{topic}\n{reference_content}\n{"example": "text"}'})
        self.assertEqual(result["revision"], 2)

    def test_option_placeholders_are_not_silently_left_unresolved(self):
        for content in ("{unknown}", "{topic}", "{topic!r}", "{topic[0]}"):
            self.rejected(self.create, content=content)
        self.create(content='Use JSON examples such as {"name": "Example"}.')

    def test_image_base_accepts_growth_rules_but_options_do_not(self):
        catalog.seed()
        base = catalog.serialize(PromptEntry.objects.get(pk="image.base.default"), self.admin)
        result = catalog.save(self.admin, {**base, "content": "{page_content}\n{growth_rules}"})
        self.assertEqual(result["content"], "{page_content}\n{growth_rules}")
        self.rejected(self.create, content="{growth_rules}")

    def test_readonly_viewer_cannot_edit_restore_or_read_history(self):
        entry = self.create(visibility="selected", allowed_users=[self.viewer.pk])
        self.rejected(catalog.save, self.viewer, {**entry, "content": "Hijack"}, status=403)
        self.rejected(catalog.restore, self.viewer, {**entry, "version": 1}, status=403)
        self.rejected(catalog.get_entry, self.viewer, entry["id"], True, status=403)
        shared = catalog.serialize(PromptEntry.objects.get(pk=entry["id"]), self.viewer)
        self.assertEqual(shared["allowed_users"], [self.viewer.pk])

    def test_admin_edit_keeps_owner_and_restore_keeps_current_grants_and_status(self):
        original = self.create(visibility="selected", allowed_users=[self.viewer.pk])
        edited = catalog.save(self.admin, {**original, "content": "Changed", "visibility": "private", "enabled": False})
        restored = catalog.restore(self.admin, {"id": original["id"], "revision": edited["revision"], "version": 1})
        self.assertEqual(restored["owner_id"], self.owner.pk)
        self.assertEqual(restored["content"], original["content"])
        self.assertFalse(restored["enabled"])
        self.assertEqual(restored["visibility"], "private")
        self.assertEqual(restored["allowed_users"], [])
        self.assertEqual(PromptVersion.objects.get(entry_id=original["id"], number=3).actor_id, self.admin.pk)

    def test_users_require_real_ids_and_bounded_lists(self):
        for ids in ([self.viewer.username + "-missing"], [1], [True], [""], ["x" * 65], ["x"] * 1001):
            self.rejected(self.create, visibility="selected", allowed_users=ids)
        entry = self.create(visibility="selected", allowed_users=[self.viewer.pk, self.viewer.pk])
        self.assertEqual(entry["allowed_users"], [self.viewer.pk])

    def test_metadata_is_validated_without_stringifying_untrusted_objects(self):
        for metadata in ([], {"color": "red"}, {"preview": "../private"}, {"preview": "missing-preview"},
                         {"width": "1024"}, {"group": {}}, {"color": "#ffffff", "detail": "x" * 501}):
            self.rejected(self.create, metadata=metadata)
        self.rejected(self.create, module="content", category="style", metadata={"color": "#ffffff"})

    def test_growth_catalog_metadata_supports_platform_arrays_and_preview_fields(self):
        catalog.seed()
        layout_ids = {
            entry["id"] for entry in builtin_entries(current_base=False)
            if entry["module"] == "image" and entry["category"] == "layout"
        }
        style_ids = {
            entry["id"] for entry in builtin_entries(current_base=False)
            if entry["module"] == "image" and entry["category"] == "style"
        }
        self.assertTrue({
            "image.layout.hook-cover", "image.layout.pain-solution",
            "image.layout.comment-proof", "image.layout.cta",
        } <= layout_ids)
        self.assertTrue({
            "image.style.brand-commercial", "image.style.ugc-lifestyle",
            "image.style.knowledge-card", "image.style.case-documentary",
        } <= style_ids)
        entry = self.create(metadata={
            "platforms": ["xiaohongshu", "douyin"],
            "goals": ["follow", "inquiry"],
            "aspect_ratios": ["3:4", "9:16"],
            "text_density": "medium",
            "summary": "适合以痛点和证据推动咨询。",
            "preview": "comic",
            "reference_asset_id": "123e4567-e89b-12d3-a456-426614174000",
        })
        self.assertEqual(entry["metadata"]["platforms"], ["xiaohongshu", "douyin"])
        self.assertEqual(entry["metadata"]["reference_asset_id"],
                         "123e4567-e89b-12d3-a456-426614174000")

    def test_growth_catalog_metadata_rejects_invalid_new_field_shapes(self):
        for key, value in (
            ("platforms", "douyin"), ("goals", [1]), ("aspect_ratios", ["3:4", 9]),
            ("text_density", ["medium"]), ("summary", 123),
        ):
            with self.subTest(key=key):
                self.rejected(self.create, metadata={key: value})

    def test_seed_preserves_current_admin_base_and_independent_restore_default(self):
        default = next(item["content"] for item in builtin_entries(current_base=False) if item["id"] == "image.base.default")
        with patch("prompts.services.get_base_prompt", side_effect=lambda module: f"Admin {module} {{page_content}} {{topic}} {{outline}}") as current:
            catalog.seed()
            self.assertEqual(current.call_count, 3)
        base = PromptEntry.objects.get(pk="image.base.default")
        self.assertTrue(base.content.startswith("Admin image"))
        self.assertEqual(base.default_snapshot["content"], default)
        self.assertEqual(base.versions.get(number=1).snapshot["content"], base.content)
        with patch("prompts.services.get_base_prompt", side_effect=AssertionError("must not reimport")):
            # Two reads (existing IDs and built-in metadata), plus savepoint/release.
            with self.assertNumQueries(4):
                catalog.seed()
        restored = catalog.restore(self.admin, {"id": base.pk, "revision": 1})
        self.assertEqual(restored["content"], default.strip())

    def test_builtin_ids_aliases_are_stable_and_system_behavior_identity_is_reserved(self):
        catalog.seed()
        expected = {
            "outline.organization.0": "自动", "outline.audience.0": "自动判断",
            "outline.audience.4": "自定义", "outline.tone.0": "自动匹配",
            "image.layout.0": "自动", "image.style.auto": "auto",
            "content.style.0": "自动", "content.structure.0": "自动",
        }
        for key, alias in expected.items():
            entry = catalog.serialize(PromptEntry.objects.get(pk=key), self.admin)
            self.assertEqual(entry["legacy_value"], alias)
            self.rejected(catalog.save, self.admin, {**entry, "name": "Renamed system behavior"})
            updated = catalog.save(self.admin, {**entry, "description": "Updated system description"})
            self.assertEqual(updated["revision"], 2)
        # Alias injection must never turn a custom UUID into an automatic selector.
        custom = self.create(legacy_value="auto", builtin=True, owner_id=self.admin.pk)
        self.assertFalse(custom["builtin"])
        self.assertEqual(custom["legacy_value"], "")
        self.assertEqual(custom["owner_id"], self.owner.pk)

    def test_copy_deduplicates_and_inserts_after_source_without_sharing_grants(self):
        source = self.create(visibility="selected", allowed_users=[self.viewer.pk])
        first = catalog.copy(self.viewer, {"id": source["id"]})
        second = catalog.copy(self.viewer, {"id": source["id"]})
        self.assertNotEqual(first["name"], second["name"])
        self.assertNotEqual(first["id"], source["id"])
        self.assertEqual(first["visibility"], "private")
        self.assertEqual(first["allowed_users"], [])
        row = LibraryOrder.objects.get(user=self.viewer, resource="prompt-center", kind="image.style")
        self.assertEqual(row.order[row.order.index(source["id"]) + 1], second["id"])

    def test_disabled_shared_entries_are_not_exposed_in_management_order(self):
        catalog.seed()
        entry = self.create(visibility="selected", allowed_users=[self.viewer.pk], enabled=False)
        self.assertNotIn(entry["id"], [item.pk for item in catalog.entries_for(self.viewer, manage=True)])
        self.assertNotIn(entry["id"], catalog.ordered_ids(self.viewer, "image", "style", [entry["id"]]))
        self.assertIn(entry["id"], catalog.ordered_ids(self.owner, "image", "style", []))

    def test_reorder_rejects_invalid_types_without_writing_order(self):
        self.rejected(catalog.reorder, self.owner, {
            "module": "image", "category": "style", "revision": 0, "ids": [True],
        })
        self.assertFalse(LibraryOrder.objects.exists())
