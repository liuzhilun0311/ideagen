from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from .models import PromptEntry, PromptVersion

migration = import_module("prompts.migrations.0003_platform_aware_outline")


class OutlinePlatformTemplateTests(TestCase):
    def test_upgrade_keeps_custom_body_line_endings_and_prior_versions(self):
        old = migration.OLD_ROLE + "\r\n\r\n用户要求：\r\n{topic}\r\nCUSTOM RULE"
        entry = PromptEntry.objects.create(
            id="outline.base.default", module="outline", category="base",
            name="Custom name", content=old, builtin=True, default_snapshot={"content": old},
        )
        PromptVersion.objects.create(entry=entry, number=1, snapshot={"content": old})
        migration.update_outline(apps, SimpleNamespace(connection=connection))
        migration.update_outline(apps, SimpleNamespace(connection=connection))
        entry.refresh_from_db()
        expected = migration.NEW_ROLE + "\r\n\r\n用户创作的主题：\r\n{topic}\r\nCUSTOM RULE"
        self.assertEqual(entry.content, expected)
        self.assertEqual(entry.name, "Custom name")
        self.assertEqual(entry.default_snapshot["content"], expected)
        self.assertEqual(entry.revision, 2)
        self.assertEqual(entry.versions.count(), 2)
        self.assertEqual(entry.versions.get(number=1).snapshot["content"], old)

    def test_unrelated_custom_role_and_text_are_not_rewritten(self):
        custom = "自定义编辑身份\n{topic}\n用户要求：保留这句话"
        self.assertEqual(migration.upgrade_content(custom), custom)

    def test_lf_templates_are_upgraded(self):
        old = migration.OLD_ROLE + "\n\n用户要求：\n{topic}"
        expected = migration.NEW_ROLE + "\n\n用户创作的主题：\n{topic}"
        self.assertEqual(migration.upgrade_content(old), expected)
