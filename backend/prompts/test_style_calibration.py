from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from generation.styles import CATALOG
from prompts.models import PromptEntry, PromptVersion

migration = import_module("prompts.migrations.0002_calibrate_style_directions")


class StyleCalibrationTests(TestCase):
    def test_updates_only_unchanged_builtin_and_keeps_revision(self):
        for style_id, (old, new) in migration.DIRECTIONS.items():
            entry = PromptEntry.objects.create(
                id=f"image.style.{style_id}", module="image", category="style",
                name=style_id, content=old, builtin=True, default_snapshot={"content": old},
            )
            PromptVersion.objects.create(entry=entry, number=1, snapshot={"content": old})
        migration.calibrate(apps, SimpleNamespace(connection=connection))
        migration.calibrate(apps, SimpleNamespace(connection=connection))
        for style_id, (_, new) in migration.DIRECTIONS.items():
            entry = PromptEntry.objects.get(pk=f"image.style.{style_id}")
            self.assertEqual(entry.content, new)
            self.assertEqual(entry.revision, 2)
            self.assertEqual(entry.versions.count(), 2)
            self.assertEqual(entry.default_snapshot["content"], new)

    def test_preserves_user_edits(self):
        old, new = migration.DIRECTIONS["chat-proof"]
        entry = PromptEntry.objects.create(
            id="image.style.chat-proof", module="image", category="style",
            name="Custom name", content="My edited direction", builtin=True,
            default_snapshot={"content": old},
        )
        migration.calibrate(apps, SimpleNamespace(connection=connection))
        entry.refresh_from_db()
        self.assertEqual(entry.content, "My edited direction")
        self.assertEqual(entry.name, "Custom name")
        self.assertEqual(entry.revision, 1)
        self.assertEqual(entry.default_snapshot["content"], new)

    def test_migration_matches_current_catalog(self):
        by_id = {item["id"]: item for item in CATALOG}
        for style_id, (_, new) in migration.DIRECTIONS.items():
            self.assertEqual(by_id[style_id]["direction"], new)
