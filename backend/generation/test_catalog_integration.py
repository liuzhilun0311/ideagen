import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import Token, User
from history.models import HistoryRecord
from prompts.catalog import seed
from prompts.catalog_runtime import base, option, options, prompt_scope, snapshot
from prompts.models import PromptEntry, PromptVersion
from .image_prompt import automatic_image_template
from .models import OutlineRun
from .styles import format_image_prompt, normalize_style, resolve_style


class CatalogIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(id="catalog-actor", username="catalog-actor")
        self.other = User.objects.create(id="catalog-other", username="catalog-other")
        Token.objects.create(user=self.user, key="catalog-token",
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer catalog-token"
        seed()

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def custom(self, module, category, **kwargs):
        return PromptEntry.objects.create(
            id=f"custom-{module}-{category}", module=module, category=category,
            owner=self.user, name="Custom", content="CUSTOM RULE", **kwargs)

    def test_scope_isolation_aliases_and_revocation(self):
        original = base("image")
        PromptEntry.objects.filter(pk="image.base.default").update(content="MANAGED {page_content}")
        custom = self.custom("image", "style")
        with prompt_scope(self.user.pk):
            self.assertIn("MANAGED", base("image"))
            self.assertEqual(normalize_style({"preset": "image.style.auto"})["preset"], "auto")
            self.assertEqual(resolve_style({"preset": custom.pk})["preset"], custom.pk)
            self.assertEqual(option("image", "style", "comic")["id"], "image.style.comic")
            with prompt_scope(self.other.pk), self.assertRaises(ValueError):
                option("image", "style", custom.pk)
            self.assertIn(custom.pk, [entry["id"] for entry in snapshot()])
        self.assertEqual(base("image"), original)
        PromptEntry.objects.filter(pk="image.style.comic").update(enabled=False)
        with prompt_scope(self.user.pk):
            for value in ("comic", "image.style.comic"):
                with self.assertRaises(ValueError):
                    option("image", "style", value)
            self.assertNotIn("image.style.comic", [entry["id"] for entry in options("image", "style")])

    @patch("generation.views.get_content_service")
    def test_custom_copy_preview_matches_actual(self, factory):
        entry = self.custom("content", "style")
        PromptEntry.objects.filter(pk="content.base.default").update(content="MANAGED {topic} {outline}")
        data = {"topic": "Desk", "outline": "Facts", "copy_preferences": {"style": entry.pk}}
        preview = self.post("/api/content/preview", data)
        self.assertEqual(preview.status_code, 200)
        self.assertIn("CUSTOM RULE", preview.json()["prompt"])
        self.assertIn("JSON", preview.json()["prompt"])
        factory.assert_not_called()
        factory.return_value.generate_content.return_value = {"success": True}
        self.assertEqual(self.post("/api/content", data).status_code, 200)
        self.assertEqual(preview.json()["prompt"],
                         factory.return_value.generate_content.call_args.kwargs["prepared_prompt"])
        entry.enabled = False
        entry.save()
        factory.reset_mock()
        self.assertEqual(self.post("/api/content", data).status_code, 400)
        factory.assert_not_called()

    @patch("generation.views.get_outline_service")
    def test_outline_snapshot_contains_managed_revisions(self, factory):
        entry = self.custom("outline", "organization")
        PromptEntry.objects.filter(pk="outline.base.default").update(content="MANAGED {topic}", revision=8)
        data = {"topic": "Desk", "organization": entry.pk}
        preview = self.post("/api/outline/preview", data)
        factory.return_value.generate_outline.return_value = {"success": True, "pages": []}
        self.assertEqual(self.post("/api/outline", data).status_code, 200)
        run = OutlineRun.objects.get()
        self.assertEqual(run.prompt, preview.json()["prompt"])
        self.assertIn("CUSTOM RULE", run.prompt)
        self.assertIn("<page>", run.prompt)
        audit = {entry["id"]: entry for entry in run.preferences["catalog_snapshot"]}
        self.assertEqual(audit["outline.base.default"]["revision"], 8)
        self.assertIn(entry.pk, audit)

    def test_frozen_image_template_never_reads_catalog_in_worker(self):
        entry = self.custom("image", "layout")
        with prompt_scope(self.user.pk):
            template = automatic_image_template({"preset": "comic"})
        values = {"page_content": f"单页布局：{entry.pk}\nFacts", "page_type": "content"}
        expected = format_image_prompt(template, values)
        entry.content = "NEW RULE"
        entry.save()
        with patch("prompts.catalog_runtime._entries", side_effect=AssertionError("worker catalog read")):
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertEqual(pool.submit(format_image_prompt, template, values).result(), expected)
        self.assertIn("CUSTOM RULE", expected)
        self.assertNotIn("NEW RULE", expected)
        self.assertIn(entry.pk, [row["id"] for row in template.audit(values["page_content"])])
        self.assertIn("接口参数为准", expected)

    def test_generated_layout_names_resolve_to_authorized_catalog_entries(self):
        with prompt_scope(self.user.pk):
            template = automatic_image_template({"preset": "comic"})
            for entry in options("image", "layout"):
                with self.subTest(layout=entry["name"]):
                    content = f'单页布局：{entry["name"]}\n上图文字：保留已有事实'
                    self.assertEqual(template.layout_entry(content)["id"], entry["id"])
                    self.assertEqual(option("image", "layout", entry["name"])["id"], entry["id"])
            text = format_image_prompt(template, {
                "page_content": "单页布局：数据结论\n上图文字：保留已有事实", "page_type": "content",
            })
            self.assertIn("突出已有数据和结论", text)
            self.assertIn("image.layout.data-conclusion", [entry["id"] for entry in snapshot()])

    def test_layout_name_resolution_rejects_revoked_and_ambiguous_choices(self):
        entry = self.custom("image", "layout")
        with prompt_scope(self.user.pk):
            template = automatic_image_template({"preset": "comic"})
            self.assertEqual(template.layout_entry("单页布局：Custom")["id"], entry.pk)
        with prompt_scope(self.other.pk):
            with self.assertRaises(ValueError):
                automatic_image_template({"preset": "comic"}).layout_entry("单页布局：Custom")
        entry.name = "数据结论"
        entry.save()
        with prompt_scope(self.user.pk):
            template = automatic_image_template({"preset": "comic"})
            with self.assertRaisesRegex(ValueError, "名称不唯一"):
                template.layout_entry("单页布局：数据结论")
            self.assertEqual(template.layout_entry("单页布局：data-conclusion")["id"], "image.layout.data-conclusion")
            self.assertEqual(template.layout_entry(f"单页布局：{entry.pk}")["id"], entry.pk)
        entry.enabled = False
        entry.save()
        PromptEntry.objects.filter(pk="image.layout.data-conclusion").update(enabled=False)
        with prompt_scope(self.user.pk):
            template = automatic_image_template({"preset": "comic"})
            for value in ("数据结论", "data-conclusion", "image.layout.data-conclusion", entry.pk):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    template.layout_entry(f"单页布局：{value}")

    @patch("generation.views.get_image_service")
    def test_all_image_boundaries_use_actor_scope(self, factory):
        self.user.is_admin = True
        self.user.save()
        entry = self.custom("image", "style")
        record = HistoryRecord.objects.create(id="catalog-work", user=self.other,
                                              images={"task_id": "catalog-task"})
        service = Mock()
        service.provider_config = {}
        service.generator.config = {}
        factory.return_value = service
        service.generate_images.return_value = iter([])
        service.retry_failed_images.return_value = iter([])
        service.retry_single_image.return_value = {"success": True}
        service.regenerate_image.return_value = {"success": True}
        page = {"index": 0, "type": "cover", "content": "Facts"}
        for endpoint, method in (("generate", "generate_images"), ("retry", "retry_single_image"),
                                 ("retry-failed", "retry_failed_images"), ("regenerate", "regenerate_image")):
            response = self.post("/api/" + endpoint, {
                "record_id": record.pk, "task_id": "catalog-task", "page": page, "pages": [page],
                "image_style": {"preset": entry.pk},
            })
            self.assertEqual(response.status_code, 200)
            if response.streaming:
                list(response.streaming_content)
            template = getattr(service, method).call_args.kwargs["image_prompt_text"]
            self.assertIn("CUSTOM RULE", template)
            self.assertEqual(factory.call_args.args[0], self.other.pk)
            response.close()

    def test_preview_does_not_seed_catalog(self):
        PromptVersion.objects.all().delete()
        PromptEntry.objects.all().delete()
        self.assertEqual(self.post("/api/content/preview", {"topic": "Desk", "outline": "Facts"}).status_code, 200)
        self.assertFalse(PromptEntry.objects.exists())
