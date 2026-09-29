from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.db import connection
from django.test import TestCase
from .models import PromptEntry, PromptVersion

migration = import_module("prompts.migrations.0005_neutral_copy_symbols")


class NeutralCopySymbolsTests(TestCase):
    def test_upgrade_preserves_custom_text_and_history_and_is_idempotent(self):
        old = f"CUSTOM RULE\r\n{migration.OLD_RULES[1]}。\r\n{{topic}}"
        entry = PromptEntry.objects.create(
            id="content.base.default", module="content", category="base",
            name="Custom name", content=old, builtin=True, default_snapshot={"content": old},
        )
        PromptVersion.objects.create(entry=entry, number=1, snapshot={"content": old})
        for _ in range(2):
            migration.migrate_copy(apps, SimpleNamespace(connection=connection))
        entry.refresh_from_db()
        expected = f"CUSTOM RULE\r\n{migration.NEW_RULE}。\r\n{{topic}}"
        self.assertEqual(entry.content, expected)
        self.assertEqual(entry.default_snapshot["content"], expected)
        self.assertEqual(entry.name, "Custom name")
        self.assertEqual(entry.revision, 2)
        self.assertEqual(entry.versions.count(), 2)
        self.assertEqual(entry.versions.get(number=1).snapshot["content"], old)
        self.assertEqual(entry.versions.get(number=2).snapshot["content"], expected)

    def test_both_known_legacy_rules_are_replaced(self):
        for old in migration.OLD_RULES:
            self.assertEqual(migration.upgrade_content(old), migration.NEW_RULE)

    def test_custom_template_is_not_rewritten(self):
        entry = PromptEntry.objects.create(
            id="content.base.custom", module="content", category="base",
            name="Custom", content=migration.OLD_RULES[1], builtin=False,
        )
        migration.migrate_copy(apps, SimpleNamespace(connection=connection))
        entry.refresh_from_db()
        self.assertEqual(entry.content, migration.OLD_RULES[1])

    def test_unrelated_instructions_are_unchanged(self):
        text = "自定义写作要求，不使用感叹号。"
        self.assertEqual(migration.upgrade_content(text), text)
