from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.db import IntegrityError, connection
from django.test import TestCase, TransactionTestCase

from accounts.models import User
from library.models import LibraryOrder
from library.services import get_order, prompt_id, reorder
from prompts.services import _prompts_file, _read_user_prompts, _write_user_prompts


class RenameSetup:
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        override = self.settings(USER_CONFIGS_ROOT=Path(self.temp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.owner = User.objects.create(id='rename-owner', username='rename-owner')
        self.viewer = User.objects.create(id='rename-viewer', username='rename-viewer')
        auth = patch('common.api._resolve_user', return_value={
            'id': self.owner.id, 'username': self.owner.username, 'is_admin': False,
        })
        auth.start()
        self.addCleanup(auth.stop)
        base = patch('prompts.services.get_base_prompt', return_value='Synthetic base')
        base.start()
        self.addCleanup(base.stop)
        _write_user_prompts(self.owner.id, 'outline', [
            {'name': 'Original', 'content': 'Old content', 'allowed_users': [self.viewer.username]},
            {'name': 'Other', 'content': 'Unchanged', 'allowed_users': []},
        ])
        self.path = _prompts_file(self.owner.id, 'outline')
        self.original_bytes = self.path.read_bytes()
        self.old_id = prompt_id({'owner_id': self.owner.id, 'name': 'Original'})
        self.new_id = prompt_id({'owner_id': self.owner.id, 'name': 'Renamed'})

    def save(self, **overrides):
        return self.client.post('/api/prompts/save', {
            'kind': 'outline', 'name': 'Renamed', 'content': 'New content',
            'original_name': 'Original', **overrides,
        }, content_type='application/json')


class PromptRenameTests(RenameSetup, TestCase):
    def test_rename_preserves_owner_and_shared_viewer_orders(self):
        for user in (self.owner, self.viewer):
            snapshot = get_order(user.id, 'prompts', 'outline')
            order = list(reversed(snapshot['order']))
            reorder(user.id, 'prompts', 'outline', 0, order)
        before = {
            user.id: get_order(user.id, 'prompts', 'outline')
            for user in (self.owner, self.viewer)
        }
        response = self.save()
        self.assertEqual(response.status_code, 200, response.content)
        for user in (self.owner, self.viewer):
            after = get_order(user.id, 'prompts', 'outline')
            self.assertEqual(after['revision'], before[user.id]['revision'] + 1)
            self.assertEqual(after['order'], [
                self.new_id if item == self.old_id else item
                for item in before[user.id]['order']
            ])
        items = _read_user_prompts(self.owner.id, 'outline')
        self.assertEqual(items[0], {
            'name': 'Renamed', 'content': 'New content', 'allowed_users': [self.viewer.username],
        })
        self.assertEqual(items[1]['content'], 'Unchanged')
        response = self.client.post('/api/library/prompts/outline/reorder', {
            'revision': 1, 'order': get_order(self.owner.id, 'prompts', 'outline')['order'],
        }, content_type='application/json')
        self.assertEqual(response.status_code, 409)

    def test_unsorted_rename_preserves_position_and_creates_revision(self):
        before = get_order(self.owner.id, 'prompts', 'outline')
        self.assertEqual(self.save().status_code, 200)
        after = get_order(self.owner.id, 'prompts', 'outline')
        self.assertEqual(after['order'], [
            self.new_id if item == self.old_id else item for item in before['order']
        ])
        self.assertEqual(after['revision'], 1)

    def test_conflict_missing_foreign_and_invalid_source_preserve_old_file(self):
        for overrides in (
            {'name': 'Other'}, {'original_name': 'Missing'},
            {'original_name': ''}, {'original_name': []}, {'name': 'x' * 51},
            {'content': ''},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.save(**overrides).status_code, 400)
                self.assertEqual(self.path.read_bytes(), self.original_bytes)
        _write_user_prompts(self.viewer.id, 'outline', [
            {'name': 'Foreign', 'content': 'Shared', 'allowed_users': [self.owner.username]},
        ])
        self.assertEqual(self.save(original_name='Foreign').status_code, 400)
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_write_failure_preserves_old_prompt_and_order(self):
        with patch('library.services.os.replace', side_effect=OSError('synthetic write error')):
            self.assertEqual(self.save().status_code, 500)
        self.assertEqual(self.path.read_bytes(), self.original_bytes)
        self.assertFalse(LibraryOrder.objects.exists())

    def test_database_failure_restores_old_prompt_and_order(self):
        # Precreate the row so the injected failure occurs after file replacement.
        LibraryOrder.objects.create(user=self.owner, resource='prompts', kind='outline')
        with patch.object(LibraryOrder, 'save', side_effect=RuntimeError('synthetic DB error')):
            self.assertEqual(self.save().status_code, 500)
        self.assertEqual(self.path.read_bytes(), self.original_bytes)
        self.assertEqual(LibraryOrder.objects.get().revision, 0)

    def test_same_name_edit_preserves_metadata_and_legacy_upsert_still_works(self):
        self.assertEqual(self.save(name='Original').status_code, 200)
        self.assertEqual(_read_user_prompts(self.owner.id, 'outline')[0]['allowed_users'],
                         [self.viewer.username])
        response = self.client.post('/api/prompts/save', {
            'kind': 'outline', 'name': 'Legacy', 'content': 'Created without original_name',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_read_user_prompts(self.owner.id, 'outline')), 3)


class PromptRenameCommitTests(RenameSetup, TransactionTestCase):
    def test_commit_failure_restores_original_file(self):
        with patch.object(connection, '_commit', side_effect=IntegrityError('synthetic commit error')):
            self.assertEqual(self.save().status_code, 500)
        self.assertEqual(self.path.read_bytes(), self.original_bytes)
        self.assertFalse(LibraryOrder.objects.exists())
