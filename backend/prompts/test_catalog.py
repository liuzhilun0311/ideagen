from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from .models import PromptEntry


class CatalogApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(id="catalog-admin", username="catalog-admin", is_admin=True)
        self.owner = User.objects.create(id="catalog-owner", username="catalog-owner")
        self.viewer = User.objects.create(id="catalog-viewer", username="catalog-viewer")
        self.current = self.admin
        auth = patch("common.api._resolve_user", side_effect=lambda request: {
            "id": self.current.pk, "username": self.current.username, "is_admin": self.current.is_admin,
        })
        auth.start()
        self.addCleanup(auth.stop)

    def post(self, action, data):
        return self.client.post(f"/api/prompt-center/{action}", data, content_type="application/json")

    def create(self, **changes):
        response = self.post("save", {
            "module": "image", "category": "style", "name": "Test style",
            "content": "Use pencil strokes.", **changes,
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["entry"]

    def test_catalog_route_seeds_once_and_preserves_edits(self):
        response = self.client.get("/api/prompt-center?manage=1")
        self.assertEqual(response.status_code, 200, response.content)
        entries = response.json()["entries"]
        self.assertGreater(len(entries), 30)
        entry = next(item for item in entries if item["id"] == "image.base.default")
        result = self.post("save", {**entry, "content": "Changed {page_content}"})
        self.assertEqual(result.status_code, 200, result.content)
        again = self.client.get("/api/prompt-center?manage=1").json()["entries"]
        self.assertEqual(next(item for item in again if item["id"] == entry["id"])["content"],
                         "Changed {page_content}")
        self.assertEqual(PromptEntry.objects.count(), len(entries))

    def test_revision_conflict_and_history_restore(self):
        entry = self.create()
        updated = self.post("save", {**entry, "content": "Updated"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.post("save", {**entry, "content": "Stale"}).status_code, 409)
        versions = self.client.get(f'/api/prompt-center/{entry["id"]}/versions').json()["versions"]
        self.assertEqual([version["revision"] for version in versions], [2, 1])
        restored = self.post("restore", {"id": entry["id"], "revision": 2, "version": 1})
        self.assertEqual(restored.status_code, 200, restored.content)
        self.assertEqual(restored.json()["entry"]["content"], entry["content"])
        self.assertEqual(restored.json()["entry"]["revision"], 3)

    def test_private_shared_permissions_and_copy(self):
        self.current = self.owner
        entry = self.create()
        self.current = self.viewer
        self.assertEqual(self.post("copy", {"id": entry["id"]}).status_code, 404)
        self.current = self.owner
        shared = self.post("save", {**entry, "visibility": "selected", "allowed_users": [self.viewer.pk]})
        self.assertEqual(shared.status_code, 200)
        self.current = self.viewer
        self.assertEqual(self.post("save", {**shared.json()["entry"], "content": "Hijack"}).status_code, 403)
        duplicate = self.post("copy", {"id": entry["id"]})
        self.assertEqual(duplicate.status_code, 200, duplicate.content)
        self.assertEqual(duplicate.json()["entry"]["owner_id"], self.viewer.pk)
        self.assertEqual(duplicate.json()["entry"]["visibility"], "private")
        self.assertEqual(self.post("save", {**duplicate.json()["entry"], "visibility": "public"}).status_code, 403)

    def test_order_revision_and_invalid_body(self):
        listing = self.client.get("/api/prompt-center?manage=1").json()
        order = listing["orders"]["outline.organization"]
        data = {"module": "outline", "category": "organization", "ids": order["ids"][::-1],
                "revision": order["revision"]}
        response = self.post("reorder", data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.post("reorder", data).status_code, 409)
        self.assertEqual(self.post("save", []).status_code, 400)

    def test_disabled_shared_entry_cannot_be_used_or_copied(self):
        entry = self.create(visibility="public", enabled=False)
        self.current = self.viewer
        usable = self.client.get("/api/prompt-center").json()["entries"]
        self.assertNotIn(entry["id"], [item["id"] for item in usable])
        self.assertEqual(self.post("copy", {"id": entry["id"]}).status_code, 403)
