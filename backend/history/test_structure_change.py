from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import Token, User
from history.models import HistoryRecord, ImageCandidate


class StructureChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(id='structure-user', username='structure-user')
        Token.objects.create(user=self.user, key='structure-token',
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer structure-token'
        self.old = {'raw': 'old', 'pages': [{'index': 0, 'type': 'cover', 'content': 'old'}]}
        self.new = {'raw': 'new', 'pages': [{'index': 0, 'type': 'cover', 'content': 'new'}]}
        self.record = HistoryRecord.objects.create(
            id='structure-record', user=self.user, outline=self.old,
            images={'task_id': 'old-task', 'generated': ['0.png']}, thumbnail='0.png')
        self.candidate = ImageCandidate.objects.create(
            id='old-candidate', record=self.record, page_index=0,
            page_content='old', task_id='old-task', status='ready')

    def change(self, expected=None, outline=None):
        return self.client.put('/api/history/structure-record', {
            'structure_change': {
                'expected_outline': self.old if expected is None else expected,
                'outline': self.new if outline is None else outline,
            },
        }, content_type='application/json')

    def test_reset_detaches_old_task_and_candidates(self):
        self.assertEqual(self.change().status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.outline, self.new)
        self.assertEqual(self.record.images, {'task_id': None, 'generated': []})
        self.assertIsNone(self.record.thumbnail)
        self.assertFalse(self.record.image_candidates.exists())

    def test_stale_outline_preserves_images(self):
        self.assertEqual(self.change(expected={}).status_code, 409)
        self.record.refresh_from_db()
        self.assertEqual(self.record.images['generated'], ['0.png'])
        self.assertTrue(self.record.image_candidates.exists())

    def test_running_generation_blocks_reset(self):
        self.candidate.status = 'generating'
        self.candidate.save()
        self.assertEqual(self.change().status_code, 409)
        self.assertTrue(self.record.image_candidates.exists())

    def test_invalid_pages_are_rejected(self):
        self.assertEqual(self.change(outline={'raw': '', 'pages': []}).status_code, 400)

    def test_infographic_page_is_accepted(self):
        outline = {'raw': '知识图', 'pages': [
            {'index': 0, 'type': 'infographic', 'content': '知识图内容'},
        ]}
        self.assertEqual(self.change(outline=outline).status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.outline, outline)

    def test_unsupported_page_type_is_rejected(self):
        outline = {'raw': 'old', 'pages': [
            {'index': 0, 'type': 'unknown', 'content': '内容'},
        ]}
        self.assertEqual(self.change(outline=outline).status_code, 400)

    def test_boolean_page_index_is_rejected(self):
        outline = {'raw': 'old', 'pages': [
            {'index': False, 'type': 'cover', 'content': '内容'},
        ]}
        self.assertEqual(self.change(outline=outline).status_code, 400)

    def test_failed_save_rolls_back_candidate_removal(self):
        with patch.object(HistoryRecord, 'save', side_effect=RuntimeError('write failed')):
            self.assertGreaterEqual(self.change().status_code, 400)
        self.assertTrue(self.record.image_candidates.exists())
        self.record.refresh_from_db()
        self.assertEqual(self.record.outline, self.old)

    def test_other_user_cannot_reset(self):
        stranger = User.objects.create(id='stranger', username='stranger')
        Token.objects.create(user=stranger, key='stranger-token',
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer stranger-token'
        self.assertEqual(self.change().status_code, 403)
