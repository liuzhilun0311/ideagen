import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

import yaml
from django.db import IntegrityError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase

from accounts.models import User


class LibraryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings_override = self.settings(
            PROJECT_ROOT=self.root, USER_CONFIGS_ROOT=self.root / 'users',
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create(
            id='owner', username='owner', use_shared_config=False,
        )
        self.other = User.objects.create(id='other', username='other')
        self.admin = User.objects.create(id='admin', username='admin', is_admin=True)
        self.auth = patch('common.api._resolve_user', side_effect=lambda request: {
            'id': self.user.id, 'username': self.user.username,
            'is_admin': self.user.is_admin,
            'use_shared_config': self.user.use_shared_config,
        })
        self.auth.start()
        self.addCleanup(self.auth.stop)
        base = patch('prompts.services.get_base_prompt', return_value='Synthetic base {topic}\nFull content')
        base.start()
        self.addCleanup(base.stop)
        from providers.config import reload_config
        reload_config()
        self.addCleanup(reload_config)

    def config(self, kind='text', shared=False, names=None):
        path = (self.root if shared else self.root / 'users' / self.user.id)
        path.mkdir(parents=True, exist_ok=True)
        path = path / f'{kind}_providers.yaml'
        config = {
            'active_provider': 'source',
            'providers': {name: {
                'api_key': 'fake-secret-not-for-response',
                'type': 'openai_compatible', 'enabled': True,
                'model': 'fake-model', 'allowed_users': ['other'],
                'api_protocol': 'responses', 'extra': {'temperature': 0.2},
            } for name in (names if names is not None else ['source', 'last'])},
        }
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
        return path, config

    def call(self, resource='models', kind='text', action='', **body):
        url = f'/api/library/{resource}/{kind}' + (f'/{action}' if action else '')
        return self.client.post(url, body, content_type='application/json') if action else self.client.get(url)

    def copy(self, source='source', revision=0, request_id='copy-1', **kwargs):
        return self.call(action='copy', source=source, revision=revision,
                         request_id=request_id, **kwargs)

    def test_empty_and_reorder_validation(self):
        self.config(names=[])
        self.assertEqual(self.call().json(), {'success': True, 'revision': 0, 'order': []})
        response = self.call(action='reorder', revision=0, order=[])
        self.assertEqual(response.json()['revision'], 1)
        self.assertEqual(self.call(action='reorder', revision=0, order=[]).status_code, 409)
        self.assertEqual(self.call(action='reorder', revision=1, order=['foreign']).status_code, 400)

    def test_order_is_account_scoped_and_serialization_matches(self):
        self.config()
        self.assertEqual(self.call(action='reorder', revision=0, order=['last', 'source']).status_code, 200)
        self.assertEqual(self.call().json()['order'], ['last', 'source'])
        config = self.client.get('/api/config').json()['config']
        self.assertEqual(list(config['text_generation']['providers']), ['last', 'source'])
        self.user = self.other
        self.config()
        self.user.use_shared_config = False
        self.user.save()
        self.assertEqual(self.call().json()['order'], ['source', 'last'])

    def test_model_copy_is_secret_preserving_disabled_and_idempotent(self):
        for kind in ('text', 'image'):
            with self.subTest(kind=kind):
                path, original = self.config(kind=kind)
                response = self.copy(kind=kind, request_id=kind)
                self.assertEqual(response.status_code, 200, response.content)
                body = response.json()
                self.assertNotIn('fake-secret', response.content.decode())
                name = body['created']['name']
                self.assertEqual(body['created']['id'], name)
                self.assertEqual(body['order'], ['source', name, 'last'])
                stored = yaml.safe_load(path.read_text(encoding='utf-8'))
                self.assertEqual(stored['active_provider'], original['active_provider'])
                self.assertEqual(stored['providers']['source'], original['providers']['source'])
                expected = {
                    **original['providers']['source'], 'enabled': False, 'allowed_users': [],
                    'provider_label': name, 'display_name': f'{name}:fake-model',
                }
                self.assertEqual(stored['providers'][name], expected)
                self.assertEqual(self.copy(kind=kind, request_id=kind).json(), body)
                self.assertEqual(len(yaml.safe_load(path.read_text(encoding='utf-8'))['providers']), 3)

    def test_copied_model_labels_are_unique_and_source_is_unchanged(self):
        for kind in ('text', 'image'):
            with self.subTest(kind=kind):
                path, original = self.config(kind=kind)
                original['providers']['source'].update(
                    provider_label='Friendly', display_name='Friendly:fake-model',
                )
                original['providers']['last']['provider_label'] = 'Friendly\uff08\u526f\u672c\uff09'
                path.write_text(yaml.safe_dump(original, allow_unicode=True), encoding='utf-8')
                first = self.copy(kind=kind, request_id=kind).json()
                second = self.copy(kind=kind, revision=1, request_id=f'{kind}-second').json()
                stored = yaml.safe_load(path.read_text(encoding='utf-8'))
                labels = set()
                for result in (first, second):
                    value = stored['providers'][result['created']['id']]
                    label = value['provider_label']
                    self.assertNotIn(label, {'Friendly', 'Friendly\uff08\u526f\u672c\uff09'})
                    self.assertNotIn(label, labels)
                    labels.add(label)
                    self.assertEqual(value['display_name'], f'{label}:fake-model')
                    self.assertEqual(value['model'], 'fake-model')
                    self.assertEqual(value['extra'], original['providers']['source']['extra'])
                self.assertEqual(stored['providers']['source'], original['providers']['source'])

    def test_idempotent_replay_returns_current_order_and_original_created(self):
        from library.models import CopyRequest
        from prompts.services import BASE_NAME
        for resource, kind, source in (
            ('models', 'text', 'source'),
            ('prompts', 'outline', json.dumps(['base', BASE_NAME], ensure_ascii=False, separators=(',', ':'))),
        ):
            with self.subTest(resource=resource):
                if resource == 'models':
                    self.config()
                first = self.copy(resource=resource, kind=kind, source=source, request_id=resource).json()
                current = self.call(resource=resource, kind=kind, action='reorder',
                                    revision=first['revision'], order=list(reversed(first['order']))).json()
                replay = self.copy(resource=resource, kind=kind, source=source, request_id=resource).json()
                self.assertEqual(replay, {**current, 'created': first['created']})
                self.assertEqual(CopyRequest.objects.get(request_id=resource).response, first)
                self.assertEqual(self.call(resource=resource, kind=kind).json(), current)

    def test_legacy_image_adapter_and_long_model_names_are_preserved(self):
        path, config = self.config(kind='image', names=['google_genai'])
        config['providers']['google_genai'].pop('type')
        path.write_text(yaml.safe_dump(config), encoding='utf-8')
        response = self.copy(kind='image', source='google_genai')
        self.assertEqual(response.status_code, 200)
        name = response.json()['created']['name']
        stored = yaml.safe_load(path.read_text(encoding='utf-8'))
        self.assertEqual(stored['providers'][name]['type'], 'google_genai')
        self.assertNotIn('type', stored['providers']['google_genai'])
        source = 'x' * 100
        self.config(names=[source])
        first = self.copy(source=source, request_id='long').json()
        second = self.copy(source=source, revision=1, request_id='long2').json()
        self.assertEqual(len(first['created']['name']), 50)
        self.assertNotEqual(first['created']['name'], second['created']['name'])

    def test_shared_model_cannot_be_copied_by_non_admin_even_on_private_fallback(self):
        self.config(shared=True)
        self.assertEqual(self.copy().status_code, 403)
        self.user = self.other
        self.assertEqual(self.copy().status_code, 403)
        self.user = self.admin
        self.assertEqual(self.copy().status_code, 200)

    def test_duplicates_stale_copy_and_reused_request_id(self):
        self.config()
        self.assertEqual(self.call(action='reorder', revision=0, order=['source', 'source']).status_code, 400)
        self.assertEqual(self.copy(revision=7).status_code, 409)
        self.assertEqual(self.copy().status_code, 200)
        self.assertEqual(self.copy(source='last').status_code, 409)
        self.assertEqual(self.copy(revision=1, request_id='copy-2').status_code, 200)
        order = self.call().json()['order']
        self.assertEqual(len(order), len(set(order)))

    def test_base_and_foreign_prompt_copies_for_all_kinds(self):
        from prompts.services import BASE_NAME, _write_user_prompts, list_all_prompts
        for kind in ('outline', 'content', 'image'):
            with self.subTest(kind=kind):
                _write_user_prompts(self.other.id, kind, [{
                    'name': 'Shared', 'content': '{topic}\nComplete content',
                    'allowed_users': ['owner'],
                }])
                base = json.dumps(['base', BASE_NAME], ensure_ascii=False, separators=(',', ':'))
                response = self.copy(resource='prompts', kind=kind, source=base, request_id=kind)
                self.assertEqual(response.status_code, 200, response.content)
                created = response.json()['created']
                items = list_all_prompts(self.user.id)[kind]
                self.assertEqual(items[1]['name'], created['name'])
                self.assertFalse(items[1]['is_base'])
                self.assertEqual(items[1]['owner_id'], self.user.id)
                shared = json.dumps(['other', 'Shared'], separators=(',', ':'))
                response = self.copy(resource='prompts', kind=kind, source=shared,
                                     revision=1, request_id=f'{kind}-shared')
                self.assertEqual(response.status_code, 200, response.content)
                items = list_all_prompts(self.user.id)[kind]
                self.assertEqual(items[-1]['content'], '{topic}\nComplete content')
                self.assertFalse(items[-1]['is_shared'])
                self.assertEqual(items[-1]['allowed_users'], [])

    def test_file_failure_rolls_back_order_and_request(self):
        from library.models import CopyRequest, LibraryOrder
        path, original = self.config()
        with patch('library.services.os.replace', side_effect=OSError('fake failure')):
            self.assertEqual(self.copy().status_code, 500)
        self.assertEqual(yaml.safe_load(path.read_text(encoding='utf-8')), original)
        self.assertFalse(CopyRequest.objects.exists())
        self.assertFalse(LibraryOrder.objects.exists())
        self.assertEqual(self.copy().status_code, 200)

    def test_db_failure_restores_file(self):
        path, original = self.config()
        with patch('library.services.CopyRequest.objects.create', side_effect=RuntimeError('fake DB failure')):
            self.assertEqual(self.copy().status_code, 500)
        self.assertEqual(yaml.safe_load(path.read_text(encoding='utf-8')), original)
        self.assertEqual(self.copy().status_code, 200)

    def test_long_prompt_names_and_collisions(self):
        from prompts.services import _write_user_prompts, _read_user_prompts
        name = 'x' * 50
        _write_user_prompts(self.user.id, 'outline', [{
            'name': name, 'content': 'All of the content', 'allowed_users': ['other'],
        }])
        source = json.dumps([self.user.id, name], separators=(',', ':'))
        first = self.copy(resource='prompts', kind='outline', source=source).json()
        second = self.copy(resource='prompts', kind='outline', source=source,
                           revision=1, request_id='second').json()
        self.assertEqual(len(first['created']['name']), 50)
        self.assertEqual(len(second['created']['name']), 50)
        self.assertNotEqual(first['created']['name'], second['created']['name'])
        stored = _read_user_prompts(self.user.id, 'outline')
        self.assertEqual(stored[0]['allowed_users'], ['other'])
        self.assertEqual(stored[1]['content'], stored[0]['content'])

    def test_revocation_and_deletion_reject_old_ids_and_retries(self):
        from prompts.services import _write_user_prompts
        shared = {'name': 'Shared', 'content': 'secret prompt', 'allowed_users': ['owner']}
        _write_user_prompts(self.other.id, 'outline', [shared])
        source = json.dumps([self.other.id, shared['name']], separators=(',', ':'))
        self.assertEqual(self.copy(resource='prompts', kind='outline', source=source).status_code, 200)
        _write_user_prompts(self.other.id, 'outline', [{**shared, 'allowed_users': []}])
        self.assertEqual(self.copy(resource='prompts', kind='outline', source=source).status_code, 404)
        self.assertEqual(self.copy(resource='prompts', kind='outline', source=source,
                                   revision=1, request_id='new').status_code, 404)
        self.assertNotIn(source, self.call(resource='prompts', kind='outline').json()['order'])

    def test_new_and_removed_models_merge_without_changing_default(self):
        path, config = self.config()
        self.call(action='reorder', revision=0, order=['last', 'source'])
        config['providers']['new'] = config['providers'].pop('last')
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
        self.assertEqual(self.call().json()['order'], ['source', 'new'])
        self.assertEqual(self.call(action='reorder', revision=1, order=['last', 'source']).status_code, 400)
        self.assertEqual(yaml.safe_load(path.read_text(encoding='utf-8'))['active_provider'], 'source')

    def test_invalid_inputs_methods_and_authentication(self):
        self.assertEqual(self.call(resource='unknown').status_code, 404)
        self.assertEqual(self.call(kind='outline').status_code, 404)
        for value in (True, -1, '0', None):
            self.assertEqual(self.copy(revision=value).status_code, 400)
        for value in ('', 'x' * 129, [], None):
            self.assertEqual(self.copy(request_id=value).status_code, 400)
        self.assertEqual(self.client.get('/api/library/models/text/copy').status_code, 405)
        self.assertEqual(self.client.post('/api/library/models/text/copy', [],
                                         content_type='application/json').status_code, 400)
        with patch('common.api._resolve_user', return_value=None):
            self.assertEqual(self.call().status_code, 401)

    def test_new_prompt_file_removed_on_database_failure(self):
        from prompts.services import BASE_NAME, _prompts_file
        source = json.dumps(['base', BASE_NAME], ensure_ascii=False, separators=(',', ':'))
        with patch('library.services.CopyRequest.objects.create', side_effect=RuntimeError('fake failure')):
            response = self.copy(resource='prompts', kind='outline', source=source)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(_prompts_file(self.user.id, 'outline').exists())

    def test_same_request_id_can_be_used_by_different_accounts(self):
        self.config()
        self.assertEqual(self.copy().status_code, 200)
        self.user = self.other
        self.user.use_shared_config = False
        self.user.save()
        self.config()
        self.assertEqual(self.copy().status_code, 200)

    def test_shared_same_name_prompts_have_distinct_ids_and_can_be_sorted(self):
        from prompts.services import _write_user_prompts, list_all_prompts
        third = User.objects.create(id='third', username='third')
        for user in (self.other, third):
            _write_user_prompts(user.id, 'image', [{
                'name': 'Same name', 'content': user.id, 'allowed_users': ['owner'],
            }])
        response = self.call(resource='prompts', kind='image').json()
        self.assertEqual(len(set(response['order'])), 3)
        order = list(reversed(response['order']))
        self.assertEqual(self.call(resource='prompts', kind='image', action='reorder',
                                   revision=0, order=order).status_code, 200)
        items = list_all_prompts(self.user.id)['image']
        self.assertEqual(items[0]['owner_id'], third.id)
        self.assertTrue(items[-1]['is_base'])
        self.assertEqual(self.copy(resource='prompts', kind='image', source=order[0],
                                   revision=1).status_code, 200)
        self.assertEqual(list_all_prompts(self.user.id)['image'][1]['content'], third.id)

    def test_model_visibility_filters_shared_keys_and_rejects_reordering_foreign_ids(self):
        self.config(shared=True)
        self.user = self.other
        self.assertEqual(self.call().json()['order'], ['source', 'last'])
        self.assertEqual(self.call(action='reorder', revision=0, order=['last', 'source']).status_code, 200)
        self.assertEqual(self.copy(revision=1).status_code, 403)
        self.user = User.objects.create(id='outsider', username='outsider')
        self.assertEqual(self.call().json()['order'], [])
        self.assertEqual(self.call(action='reorder', revision=0, order=['source', 'last']).status_code, 400)

    def test_malformed_prompt_file_is_not_overwritten_and_error_is_sanitized(self):
        from prompts.services import BASE_NAME, _prompts_file
        source = json.dumps(['base', BASE_NAME], ensure_ascii=False, separators=(',', ':'))
        path = _prompts_file(self.user.id, 'outline')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"fake-secret": broken', encoding='utf-8')
        response = self.copy(resource='prompts', kind='outline', source=source)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('fake-secret', response.content.decode())
        self.assertEqual(path.read_text(encoding='utf-8'), '{"fake-secret": broken')


class LibraryConcurrencyTests(TransactionTestCase):
    setUp = LibraryTests.setUp
    config = LibraryTests.config

    def simultaneous(self, operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(run, operations))

    def test_two_admins_copy_shared_file_without_lost_updates_or_name_collision(self):
        from library.services import copy_resource
        second = User.objects.create(id='admin2', username='admin2', is_admin=True)
        path, original = self.config(shared=True)
        results = self.simultaneous([
            lambda: copy_resource(self.admin.id, 'models', 'text', 'source', 0, 'admin-copy'),
            lambda: copy_resource(second.id, 'models', 'text', 'source', 0, 'admin-copy'),
        ])
        names = [result['created']['name'] for result in results]
        self.assertEqual(len(set(names)), 2)
        stored = yaml.safe_load(path.read_text(encoding='utf-8'))
        self.assertEqual(len(stored['providers']), 4)
        self.assertEqual(stored['providers']['source'], original['providers']['source'])
        for name in names:
            self.assertIn(name, stored['providers'])

    def test_concurrent_reorders_reject_one_stale_revision(self):
        from library.services import LibraryError, reorder
        self.config()

        def operation():
            try:
                return reorder(self.user.id, 'models', 'text', 0, ['last', 'source'])['revision']
            except LibraryError as exc:
                return exc.status

        self.assertCountEqual(self.simultaneous([operation, operation]), [1, 409])

    def test_concurrent_retry_creates_only_once(self):
        from library.services import copy_resource
        path, _ = self.config()

        def operation():
            return copy_resource(self.user.id, 'models', 'text', 'source', 0, 'same-request')

        first, second = self.simultaneous([operation, operation])
        self.assertEqual(first, second)
        self.assertEqual(len(yaml.safe_load(path.read_text(encoding='utf-8'))['providers']), 3)

    def test_commit_failure_restores_file_and_database(self):
        from library.models import CopyRequest, LibraryOrder
        from library.services import copy_resource
        path, original = self.config()
        with patch.object(connection, '_commit', side_effect=IntegrityError('fake commit failure')):
            with self.assertRaises(IntegrityError):
                copy_resource(self.user.id, 'models', 'text', 'source', 0, 'commit-test')
        self.assertEqual(yaml.safe_load(path.read_text(encoding='utf-8')), original)
        self.assertFalse(CopyRequest.objects.exists())
        self.assertFalse(LibraryOrder.objects.exists())
