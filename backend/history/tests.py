import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Token, User
from history.models import HistoryRecord
from history.services import HistoryService


class WorkLifecycleTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        settings = override_settings(HISTORY_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        service = patch('history.views.get_history_service', return_value=HistoryService())
        service.start()
        self.addCleanup(service.stop)
        self.user = User.objects.create(id='u_lifecycle', username='lifecycle')
        Token.objects.create(user=self.user, key='lifecycle-token',
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer lifecycle-token'

    def test_create_edit_find_and_delete_work(self):
        response = self.client.post('/api/history', json.dumps({
            'topic': 'City walk',
            'outline': {'raw': 'Walk', 'pages': [{'index': 0, 'content': 'Park'}]},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        record_id = response.json()['record_id']
        url = f'/api/history/{record_id}'
        record = self.client.get(url).json()['record']
        self.assertEqual(record['user_id'], self.user.pk)
        self.assertTrue(record['can_edit'])
        self.assertFalse(record['can_share'])
        response = self.client.put(url, json.dumps({
            'title': 'Weekend walk', 'content': {'copywriting': 'Visit the park'},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(url).json()['record']['content']['copywriting'],
                         'Visit the park')
        self.assertEqual(self.client.get('/api/history', {'keyword': 'Weekend'}).json()['total'], 1)
        self.assertEqual(self.client.get('/api/history', {'source': 'shared'}).json()['total'], 0)
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(self.client.get(url + '/exists').json()['exists'])
        self.assertEqual(self.client.get('/api/history').json()['total'], 0)
        self.assertEqual(self.client.get('/api/history/stats').json()['total'], 0)

    def test_sync_does_not_restore_deleted_works_from_leftover_files(self):
        orphan = self.root / self.user.pk / 'old-task'
        orphan.mkdir(parents=True)
        (orphan / '0.png').write_bytes(b'orphan-image')
        for admin in (False, True):
            self.user.is_admin = admin
            self.user.save(update_fields=['is_admin'])
            response = self.client.post('/api/history/scan-all')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['synced'], 0)
            self.assertEqual(HistoryRecord.objects.count(), 0)
            self.assertEqual(self.client.get('/api/images/old-task/0.png').status_code, 403)
