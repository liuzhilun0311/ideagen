from django.test import TestCase

from .catalog import seed
from .catalog_defaults import builtin_entries
from .models import PromptEntry, PromptVersion


class SceneDescriptionsTests(TestCase):
    def test_all_builtin_entries_have_detailed_selection_guidance(self):
        for entry in builtin_entries(current_base=False):
            with self.subTest(entry=entry["id"]):
                self.assertGreater(len(entry["description"]), 30)

    def test_backfill_preserves_prompt_content_and_manual_descriptions(self):
        seed()
        automatic = PromptEntry.objects.get(pk="content.style.0")
        manual = PromptEntry.objects.get(pk="content.style.1")
        content = automatic.content
        for entry in (automatic, manual):
            entry.default_snapshot = {**entry.default_snapshot, "description": ""}
            entry.description = "" if entry == automatic else "User-authored guidance"
            entry.save()
        seed()
        automatic.refresh_from_db()
        manual.refresh_from_db()
        self.assertGreater(len(automatic.description), 30)
        self.assertEqual(automatic.content, content)
        self.assertEqual(manual.description, "User-authored guidance")
        self.assertTrue(PromptVersion.objects.filter(
            entry=automatic, number=automatic.revision,
            snapshot__description=automatic.description).exists())
        revision = automatic.revision
        seed()
        automatic.refresh_from_db()
        self.assertEqual(automatic.revision, revision)
