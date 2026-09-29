import io
import json
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event
from unittest.mock import patch

from django.db import OperationalError, close_old_connections, connection, connections
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from PIL import Image

from accounts.models import Token, User
from history.models import HistoryRecord
from history.services import HistoryService
from postprocessing.models import ImageJob, ImagePage, ProcessingPreference
from postprocessing.services import digest_file, record_state


class SharingTests(TestCase):
    def test_creation_inputs_are_not_exposed_to_shared_readers(self):
        self.setUpSnapshot()
        self.record.shared_users.add(self.recipient)
        owner = self.client.get(self.url).json()["record"]
        self.assertEqual(owner["outline"]["creation_inputs"]["reference_content"], "Private material")
        self.login(self.recipient)
        reader = self.client.get(self.url).json()["record"]
        self.assertNotIn("creation_inputs", reader["outline"])

    def setUpSnapshot(self):
        self.record.outline["creation_inputs"] = {
            "version": 1, "reference_content": "Private material", "reference_images": [],
            "reference_roles": ["subject"], "image_parameters": {"resolution": "2K"},
            "use_cover_reference": False, "models": {"outline": "text", "content": "copy", "image": "image"},
        }
        self.record.save()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        override = override_settings(HISTORY_ROOT=self.root)
        override.enable()
        self.addCleanup(override.disable)
        service = patch('history.views.get_history_service', return_value=HistoryService())
        service.start()
        self.addCleanup(service.stop)
        self.owner = self.user('owner', True)
        self.recipient = self.user('recipient')
        self.stranger = self.user('stranger')
        self.admin = self.user('admin', True)
        self.record = HistoryRecord.objects.create(
            id='shared-record', user=self.owner, title='Shared flowers',
            outline={'raw': 'garden', 'pages': [{'index': 0, 'content': 'flowers'}]},
            content={'copywriting': 'Spring'}, status='completed',
            images={'task_id': 'task', 'generated': ['0.png']},
        )
        self.directory = self.root / self.owner.pk / 'task'
        self.directory.mkdir(parents=True)
        for name in ('0.png', 'thumb_0.png', 'secret.png'):
            Image.new('RGB', (8, 8), 'red').save(self.directory / name)
        self.url = '/api/history/shared-record'
        self.login(self.owner)

    def user(self, name, admin=False):
        user = User.objects.create(id=f'u_{name}', username=name, is_admin=admin)
        Token.objects.create(user=user, key=user.pk,
                             expires_at=timezone.now() + timedelta(days=1))
        return user

    def login(self, user):
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {user.pk}' if user else ''

    def grant(self, ids=None):
        return self.client.put(
            self.url + '/sharing', json.dumps({'user_ids': ids if ids is not None else [self.recipient.pk]}),
            content_type='application/json',
        )

    def test_grant_revoke_and_capabilities(self):
        self.assertEqual(self.grant().status_code, 200)
        self.assertEqual(self.client.get(self.url + '/sharing').json(),
                         {'success': True, 'user_ids': [self.recipient.pk]})
        owner = self.client.get(self.url).json()['record']
        self.assertTrue(owner['can_share'])
        self.assertEqual(owner['shared_count'], 1)
        self.login(self.recipient)
        detail = self.client.get(self.url)
        self.assertEqual(detail.status_code, 200)
        record = detail.json()['record']
        self.assertEqual(record['owner'], {'id': self.owner.pk, 'username': 'owner'})
        self.assertFalse(record['can_edit'])
        self.assertFalse(record['can_share'])
        self.assertTrue(record['is_shared'])
        self.assertNotIn('shared_count', record)
        self.assertNotIn('user_ids', record)
        self.assertIn('no-store', detail['Cache-Control'])
        self.login(self.owner)
        self.assertEqual(self.grant([]).status_code, 200)
        self.login(self.recipient)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertFalse(self.client.get(self.url + '/exists').json()['exists'])

    def test_invalid_sets_are_atomic_and_only_admin_owner_can_share(self):
        self.assertEqual(self.grant().status_code, 200)
        for ids in ([self.stranger.pk, 'missing'], [1], 'u_recipient', [self.owner.pk]):
            self.assertEqual(self.grant(ids).status_code, 400)
            self.assertEqual(self.client.get(self.url + '/sharing').json()['user_ids'],
                             [self.recipient.pk])
        for user in (self.recipient, self.stranger, self.admin):
            self.login(user)
            self.assertEqual(self.grant([]).status_code, 403)
            self.assertEqual(self.client.get(self.url + '/sharing').status_code, 403)
        self.login(None)
        self.assertEqual(self.grant([]).status_code, 401)

    def test_shared_reads_never_sync_or_write(self):
        self.assertEqual(self.grant().status_code, 200)
        self.login(self.recipient)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(self.url).status_code, 200)
            self.assertEqual(self.client.get('/api/postprocessing/shared-record').status_code, 200)
        writes = [query['sql'] for query in queries
                  if query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(writes, [])
        self.record.refresh_from_db()
        self.assertEqual(self.record.images['generated'], ['0.png'])
        self.assertEqual(ImagePage.objects.count(), 0)
        self.assertEqual(ProcessingPreference.objects.count(), 0)

    def test_existing_private_records_and_admin_oversight(self):
        self.assertFalse(self.record.shared_users.exists())
        for user, expected in ((self.recipient, 403), (self.stranger, 403),
                               (self.admin, 200), (None, 401)):
            self.login(user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, expected)
            self.assertIn('no-store', response['Cache-Control'])
        self.login(self.admin)
        record = self.client.get(self.url).json()['record']
        self.assertTrue(record['can_edit'])
        self.assertFalse(record['can_share'])
        self.assertNotIn('shared_count', record)
        self.owner.is_admin = False
        self.owner.save(update_fields=['is_admin'])
        self.login(self.owner)
        self.assertEqual(self.grant().status_code, 403)

    def test_shared_list_search_pagination_and_stats(self):
        self.grant()
        own = HistoryRecord.objects.create(id='own', user=self.recipient, title='Spring')
        other = HistoryRecord.objects.create(
            id='another', user=self.owner, title='Spring meadow', status='partial',
        )
        other.shared_users.add(self.recipient)
        HistoryRecord.objects.create(id='private', user=self.owner, title='Spring secret')
        self.login(self.recipient)
        self.assertEqual([r['id'] for r in self.client.get('/api/history').json()['records']], [own.pk])
        first = self.client.get('/api/history', {
            'source': 'shared', 'keyword': 'spring', 'page_size': 1, 'page': 1,
        }).json()
        second = self.client.get('/api/history', {
            'source': 'shared', 'keyword': 'spring', 'page_size': 1, 'page': 2,
        }).json()
        self.assertEqual(first['total'], 2)
        self.assertEqual(first['total_pages'], 2)
        self.assertNotEqual(first['records'][0]['id'], second['records'][0]['id'])
        self.assertFalse(first['records'][0]['can_edit'])
        self.assertNotIn('shared_count', first['records'][0])
        query = {'source': 'shared', 'keyword': 'garden', 'status': 'completed'}
        result = self.client.get('/api/history', query).json()
        search = self.client.get('/api/history/search', query).json()
        self.assertEqual([r['id'] for r in result['records']], [self.record.pk])
        self.assertEqual(search['records'], result['records'])
        stats = self.client.get('/api/history/stats?source=shared').json()
        self.assertEqual(stats, {'success': True, 'total': 2,
                                 'by_status': {'completed': 1, 'partial': 1}})
        self.login(self.owner)
        self.assertEqual(self.client.get('/api/history?source=shared').json()['total'], 0)
        self.login(self.stranger)
        self.assertEqual(self.client.get('/api/history?source=shared').json()['total'], 0)

    def test_original_thumbnail_and_zip_require_source_membership(self):
        self.grant()
        self.login(self.recipient)
        for url in ('/api/images/task/0.png', '/api/images/task/0.png?thumbnail=false'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            response.close()
        for url in ('/api/images/task/secret.png', '/api/images/task/thumb_0.png',
                    '/api/images/unshared/0.png'):
            self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.get(self.url + '/download')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(archive.namelist(), ['page_1.png'])
        self.login(self.stranger)
        self.assertEqual(self.client.get('/api/images/task/0.png').status_code, 403)
        self.assertEqual(self.client.get(self.url + '/download').status_code, 403)

    def processed_urls(self):
        record_state(self.record.pk, self.owner.pk,
                     {'action': 'process', 'indices': [0], 'strength': 'light'})
        page = ImagePage.objects.get(record=self.record)
        job = ImageJob.objects.get(page=page)
        output = self.root / self.owner.pk / '_postprocessing' / 'test.png'
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (8, 8), 'blue').save(output)
        job.status = 'done'
        job.output_path = output.relative_to(self.root).as_posix()
        job.output_digest = digest_file(output)
        job.save()
        page.current_job = job
        page.adopted = 'processed'
        page.save()
        state = record_state(self.record.pk, self.owner.pk)
        return state['pages'][0]['original_url'], state['pages'][0]['processed_url']

    def test_processed_reads_revoke_and_demotion(self):
        original, processed = self.processed_urls()
        self.grant()
        protected = [self.url, self.url + '/download', '/api/images/task/0.png',
                     '/api/images/task/0.png?thumbnail=false',
                     '/api/postprocessing/shared-record', original, processed]
        self.login(self.recipient)
        for url in protected:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn('no-store', response['Cache-Control'])
            response.close()
        self.login(self.owner)
        self.grant([])
        self.login(self.recipient)
        for url in protected:
            self.assertIn(self.client.get(url).status_code, (403, 404), url)
        self.login(self.owner)
        self.grant()
        self.owner.is_admin = False
        self.owner.save(update_fields=['is_admin'])
        self.login(self.recipient)
        for url in protected:
            self.assertIn(self.client.get(url).status_code, (403, 404), url)
        self.assertEqual(self.client.get('/api/history?source=shared').json()['total'], 0)
        self.assertEqual(self.client.get('/api/history/stats?source=shared').json()['total'], 0)

    def test_recipient_and_record_deletion_remove_access(self):
        self.grant()
        self.recipient.delete()
        self.assertFalse(self.record.shared_users.exists())
        self.assertEqual(self.client.get(self.url + '/sharing').json()['user_ids'], [])
        self.recipient = self.user('replacement')
        self.grant()
        self.record.delete()
        self.login(self.recipient)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertFalse(self.client.get(self.url + '/exists').json()['exists'])
        self.assertEqual(self.client.get('/api/images/task/0.png').status_code, 403)
        self.assertEqual(self.client.get('/api/history?source=shared').json()['total'], 0)

    def test_recipient_writes_rejected_before_provider_or_sync(self):
        self.grant()
        self.login(self.recipient)
        self.assertEqual(self.client.put(self.url, '{"title":"hijacked"}',
                                        content_type='application/json').status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.assertEqual(self.grant([]).status_code, 403)
        with patch('generation.views.resolve_prompt_text') as prompts, \
                patch('generation.views.get_image_service') as provider, \
                patch('generation.views.ImageService') as named_provider:
            for endpoint in ('generate', 'retry', 'retry-failed', 'regenerate'):
                for reference in ({'task_id': 'task'}, {'record_id': self.record.pk},
                                  {'task_id': 'task', 'record_id': self.record.pk}):
                    body = {**reference, 'pages': [{'index': 0}], 'page': {'index': 0},
                            'provider_name': 'must-not-load', 'force': True}
                    response = self.client.post('/api/' + endpoint, json.dumps(body),
                                                content_type='application/json')
                    self.assertEqual(response.status_code, 403, (endpoint, reference))
            self.assertEqual(self.client.get('/api/task/task').status_code, 403)
            prompts.assert_not_called()
            provider.assert_not_called()
            named_provider.assert_not_called()
        for action in ({'action': 'preferences', 'automatic': True, 'strength': 'heavy'},
                       {'action': 'process', 'indices': [0]},
                       {'action': 'adopt', 'index': 0, 'version': 'original'}):
            response = self.client.post('/api/postprocessing/shared-record', json.dumps(action),
                                        content_type='application/json')
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get('/api/history/scan/task').status_code, 403)
        self.assertEqual(self.client.post('/api/history/scan-all').status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.images['generated'], ['0.png'])
        self.assertEqual(self.record.title, 'Shared flowers')
        self.assertEqual(ImageJob.objects.count(), 0)
        self.assertEqual(ProcessingPreference.objects.count(), 0)

    def test_generation_checks_indirect_task_references_and_mismatches(self):
        own = HistoryRecord.objects.create(
            id='own', user=self.recipient, images={'task_id': 'task'},
        )
        self.login(self.recipient)
        with patch('generation.views.get_image_service') as provider:
            response = self.client.post('/api/generate', json.dumps({
                'record_id': own.pk, 'pages': [{'index': 0}],
            }), content_type='application/json')
            self.assertEqual(response.status_code, 403)
            for task in ('../u_owner/task', 'different'):
                response = self.client.post('/api/generate', json.dumps({
                    'record_id': own.pk, 'task_id': task, 'pages': [{'index': 0}],
                }), content_type='application/json')
                self.assertEqual(response.status_code, 400)
            provider.assert_not_called()

    def test_recipient_reads_show_owner_changes_without_mutating_processing(self):
        self.processed_urls()
        self.grant()
        HistoryRecord.objects.filter(pk=self.record.pk).update(title='Owner revision')
        self.login(self.recipient)
        with CaptureQueriesContext(connection) as queries:
            detail = self.client.get(self.url).json()['record']
            state = self.client.get('/api/postprocessing/shared-record').json()
        self.assertEqual(detail['title'], 'Owner revision')
        self.assertEqual(state['pages'][0]['adopted'], 'processed')
        self.assertIsNotNone(detail['adopted_thumbnail_url'])
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(
            ('UPDATE', 'INSERT', 'DELETE')) for query in queries))

    def test_own_record_cannot_bind_another_owners_task_or_traversal_path(self):
        own = HistoryRecord.objects.create(id='own', user=self.recipient)
        self.login(self.recipient)
        for task in ('task', '../u_owner/task', 'C:\\private'):
            response = self.client.post('/api/history', json.dumps({
                'topic': 'test', 'outline': {'pages': []}, 'task_id': task,
            }), content_type='application/json')
            self.assertEqual(response.status_code, 400)
            response = self.client.put('/api/history/own', json.dumps({
                'images': {'task_id': task, 'generated': ['0.png']},
            }), content_type='application/json')
            self.assertEqual(response.status_code, 400)
        # Legacy malformed data must not make deletion escape this owner's directory.
        own.images = {'task_id': '../u_owner/task'}
        own.save(update_fields=['images'])
        self.assertEqual(self.client.delete('/api/history/own').status_code, 200)
        self.assertTrue((self.directory / '0.png').exists())
        self.assertTrue(HistoryRecord.objects.filter(pk=self.record.pk).exists())

    def test_generation_rejects_path_like_page_indices_before_loading_provider(self):
        self.login(self.recipient)
        with patch('generation.views.get_image_service') as provider:
            for index in ('../../u_owner/task/0', -1, True):
                response = self.client.post('/api/generate', json.dumps({
                    'task_id': 'new_task', 'pages': [{'index': index}],
                }), content_type='application/json')
                self.assertEqual(response.status_code, 400)
            provider.assert_not_called()

    def test_processed_route_requires_current_record_page_membership(self):
        original, processed = self.processed_urls()
        self.grant()
        self.login(self.recipient)
        self.assertEqual(self.client.get(processed.replace('/0/', '/1/')).status_code, 404)
        self.record.images = {'task_id': 'task', 'generated': []}
        self.record.save(update_fields=['images'])
        for url in (original, processed):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_shared_source_excludes_grants_from_non_admin_owners(self):
        self.grant()
        private = HistoryRecord.objects.create(
            id='nonadmin', user=self.stranger, title='Private',
        )
        private.shared_users.add(self.recipient)
        self.login(self.recipient)
        self.assertEqual(self.client.get('/api/history/nonadmin').status_code, 403)
        response = self.client.get('/api/history?source=shared').json()
        self.assertEqual([record['id'] for record in response['records']], [self.record.pk])

    def test_malformed_sharing_requests_do_not_replace_grants(self):
        self.grant()
        for body in ('{}', 'null', '[]', '{', '{"user_ids":[null]}'):
            response = self.client.put(self.url + '/sharing', body, content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.client.get(self.url + '/sharing').json()['user_ids'],
                             [self.recipient.pk])
        self.assertEqual(self.grant([self.recipient.pk, self.recipient.pk]).status_code, 200)
        self.assertEqual(self.record.shared_users.count(), 1)
        self.assertEqual(self.client.post(self.url + '/sharing').status_code, 405)

    def test_admin_nonowner_processing_reads_are_readonly_and_mutations_denied(self):
        original, processed = self.processed_urls()
        self.login(self.admin)
        with CaptureQueriesContext(connection) as queries:
            for url in ('/api/postprocessing/shared-record', original, processed):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                response.close()
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(
            ('UPDATE', 'INSERT', 'DELETE')) for query in queries))
        for action in ({'action': 'preferences', 'automatic': True, 'strength': 'heavy'},
                       {'action': 'process', 'indices': [0]},
                       {'action': 'adopt', 'index': 0, 'version': 'original'}):
            response = self.client.post('/api/postprocessing/shared-record', json.dumps(action),
                                        content_type='application/json')
            self.assertEqual(response.status_code, 404)
        self.assertEqual(ImageJob.objects.count(), 1)

    def test_revocation_after_authorization_only_affects_the_inflight_read(self):
        from history.permissions import source_file

        self.grant()
        self.login(self.recipient)

        def revoke_before_file_resolution(record, filename):
            record.shared_users.clear()
            return source_file(record, filename)

        with patch('generation.views.source_file', side_effect=revoke_before_file_resolution):
            response = self.client.get('/api/images/task/0.png')
            self.assertEqual(response.status_code, 200)
            response.close()
        self.assertEqual(self.client.get('/api/images/task/0.png').status_code, 403)
        self.assertFalse(self.client.get(self.url + '/exists').json()['exists'])


class SharingConcurrencyTests(TransactionTestCase):
    def test_overlapping_sqlite_sets_never_publish_mixed_or_partial_grants(self):
        if connection.vendor != 'sqlite':
            self.skipTest('This test exercises SQLite writer contention.')
        from history.sharing import sharing

        owner = User.objects.create(id='u_concurrent_owner', username='concurrent_owner', is_admin=True)
        users = [User.objects.create(id=f'u_concurrent_{index}', username=f'concurrent_{index}')
                 for index in range(5)]
        Token.objects.create(user=owner, key=owner.pk,
                             expires_at=timezone.now() + timedelta(days=1))
        record = HistoryRecord.objects.create(id='concurrent', user=owner)
        record.shared_users.add(users[0])
        first_ids = [user.pk for user in users[1:3]]
        second_ids = [user.pk for user in users[3:5]]
        manager_class = type(record.shared_users)
        original_set = manager_class.set
        first_pending = Event()
        release_first = Event()

        def hold_first_set(manager, recipients, **kwargs):
            recipients = list(recipients)
            result = original_set(manager, recipients, **kwargs)
            if {user.pk for user in recipients} == set(first_ids):
                first_pending.set()
                if not release_first.wait(10):
                    raise AssertionError('Timed out waiting for concurrent request.')
            return result

        def put(ids):
            close_old_connections()
            try:
                request = RequestFactory().put(
                    '/api/history/concurrent/sharing', json.dumps({'user_ids': ids}),
                    content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {owner.pk}',
                )
                response = sharing(request, record.pk)
                return response.status_code, json.loads(response.content)
            except OperationalError as error:
                if 'locked' not in str(error).lower():
                    raise
                return 'locked', None
            finally:
                connections.close_all()

        with patch.object(manager_class, 'set', hold_first_set), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(put, first_ids)
            try:
                self.assertTrue(first_pending.wait(10))
                second = pool.submit(put, second_ids)
                self.assertEqual(second.result(timeout=10)[0], 'locked')
            finally:
                release_first.set()
            status, payload = first.result(timeout=10)
            self.assertEqual(status, 200)
            self.assertEqual(set(payload['user_ids']), set(first_ids))
        self.assertEqual(set(record.shared_users.values_list('pk', flat=True)), set(first_ids))
        status, payload = put(second_ids)
        self.assertEqual(status, 200)
        self.assertEqual(set(payload['user_ids']), set(second_ids))
        self.assertEqual(set(record.shared_users.values_list('pk', flat=True)), set(second_ids))
