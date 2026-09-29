import hashlib
import json
import os
import subprocess
import stat
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from PIL import Image, PngImagePlugin

from accounts.models import Token, User
from history.models import HistoryRecord
from history.services import HistoryService
from .models import ImageJob, ImagePage
from .services import claim_job, image_file, record_output_directory, run_job, safe_path


class ProcessingTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.override = override_settings(HISTORY_ROOT=self.root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.owner = User.objects.create(id='u_owner', username='owner')
        self.other = User.objects.create(id='u_other', username='other', is_admin=True)
        for user in (self.owner, self.other):
            Token.objects.create(user=user, key=user.id, expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer u_owner'
        self.record = HistoryRecord.objects.create(
            id='record', user=self.owner,
            outline={'pages': [{'index': 0, 'content': 'first'}, {'index': 1, 'content': 'second'}]},
            images={'task_id': 'task', 'generated': ['0.png', '1.png']},
        )
        self.source_dir = self.root / self.owner.id / 'task'
        self.source_dir.mkdir(parents=True)
        self.image(0)
        self.image(1)
        self.url = '/api/postprocessing/record'

    def image(self, index, color='red'):
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('source', 'must remain intact')
        Image.new('RGB', (96, 96), color).save(self.source_dir / f'{index}.png', pnginfo=metadata)

    def post(self, **data):
        return self.client.post(self.url, json.dumps(data), content_type='application/json')

    def enqueue(self, **extra):
        data = {'action': 'process', 'indices': [0], 'strength': 'light', 'force': False}
        data.update(extra)
        response = self.post(**data)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    @staticmethod
    def transform(source, output, strength):
        # Deliberately mutate input like exiftool does: only the isolated copy may change.
        with Image.open(source) as image:
            image.convert('RGB').save(source)
        Image.new('RGB', (96, 96), 'blue').save(output)

    def finish(self):
        job = claim_job()
        self.assertIsNotNone(job)
        with patch('postprocessing.services.process_image', side_effect=self.transform):
            run_job(job)
        return job

    def test_admin_oversight_reads_images_but_cannot_process(self):
        self.enqueue()
        self.finish()
        page = self.client.get(self.url).json()['pages'][0]
        for url in (self.url, page['original_url'], page['processed_url']):
            response = self.client.get(url, HTTP_AUTHORIZATION='Bearer u_other')
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            response.close()
        self.assertEqual(self.client.post(self.url, '{"action":"process"}',
                                        content_type='application/json',
                                        HTTP_AUTHORIZATION='Bearer u_other').status_code, 404)
        self.other.is_admin = False
        self.other.save(update_fields=['is_admin'])
        for url in (self.url, page['original_url'], page['processed_url']):
            self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION='Bearer u_other').status_code, 404)
        self.assertEqual(self.client.get(self.url, HTTP_AUTHORIZATION='').status_code, 401)

    def test_idempotency_strength_and_immutable_source_outputs(self):
        original = (self.source_dir / '0.png').read_bytes()
        self.enqueue()
        self.enqueue(force=True)
        self.assertEqual(ImageJob.objects.count(), 1)
        self.finish()
        state = self.client.get(self.url).json()
        page = state['pages'][0]
        self.assertEqual(page['adopted'], 'processed')
        self.assertEqual(page['strength'], 'light')
        old_url = page['processed_url']
        self.enqueue(strength='heavy')
        self.assertEqual(ImageJob.objects.count(), 1)
        self.enqueue(strength='heavy', force=True)
        self.finish()
        page = self.client.get(self.url).json()['pages'][0]
        self.assertEqual(page['strength'], 'heavy')
        self.assertNotEqual(old_url, page['processed_url'])
        response = self.client.get(old_url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual((self.source_dir / '0.png').read_bytes(), original)

    def test_active_single_dedup_and_invalid_batch_is_atomic(self):
        self.enqueue()
        self.enqueue(strength='heavy', force=True)
        self.assertEqual(ImageJob.objects.count(), 1)
        response = self.post(action='process', indices=[1, 300], strength='light', force=False)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ImageJob.objects.count(), 1)
        for payload in (
            {'action': 'process', 'indices': [True], 'strength': 'light'},
            {'action': 'process', 'indices': [0], 'strength': 'invalid'},
            {'action': 'preferences', 'automatic': 'false', 'strength': 'light'},
            {'action': 'process', 'indices': [0], 'strength': 'light', 'force': 'false'},
        ):
            self.assertEqual(self.post(**payload).status_code, 400)

    def test_adoption_choice_after_enqueue_wins_and_stale_revision_rejected(self):
        page = self.enqueue()['pages'][0]
        self.assertEqual(self.post(action='adopt', index=0, version='processed',
                                   source_revision=page['source_revision']).status_code, 409)
        self.assertEqual(self.post(action='adopt', index=0, version='original',
                                   source_revision=page['source_revision']).status_code, 200)
        self.finish()
        self.assertEqual(self.client.get(self.url).json()['pages'][0]['adopted'], 'original')
        self.image(0, 'green')
        self.assertEqual(self.post(action='adopt', index=0, version='processed',
                                   source_revision=page['source_revision']).status_code, 409)
        state = self.client.get(self.url).json()['pages'][0]
        self.assertIsNone(state['processed_url'])
        self.assertNotEqual(page['source_revision'], state['source_revision'])

    def test_stale_worker_cannot_attach_to_replaced_source(self):
        self.enqueue()
        job = claim_job()
        self.image(0, 'green')
        with patch('postprocessing.services.process_image', side_effect=self.transform):
            run_job(job)
        self.assertIsNone(self.client.get(self.url).json()['pages'][0]['processed_url'])

    def test_partial_failure_keeps_last_success_and_sanitizes_error(self):
        self.enqueue()
        self.finish()
        old = self.client.get(self.url).json()['pages'][0]['processed_url']
        self.enqueue(indices=[0, 1], force=True)
        with patch('postprocessing.services.process_image', side_effect=RuntimeError('secret C:/private/key')):
            call_command('process_images', once=True)
        state = self.client.get(self.url).json()['pages'][0]
        self.assertEqual(state['status'], 'error')
        self.assertEqual(state['processed_url'], old)
        self.assertNotIn('secret', state['error'])
        self.finish()
        self.assertEqual(self.client.get(self.url).json()['pages'][1]['status'], 'done')

    def test_lease_recovery_fences_old_worker_and_bounds_retries(self):
        self.enqueue()
        old = claim_job()
        ImageJob.objects.filter(pk=old.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        new = claim_job()
        self.assertEqual(old.pk, new.pk)
        self.assertNotEqual(old.lease_token, new.lease_token)
        with patch('postprocessing.services.process_image', side_effect=self.transform):
            run_job(old)
        self.assertEqual(ImageJob.objects.get(pk=old.pk).status, 'processing')
        ImageJob.objects.filter(pk=new.pk).update(
            attempts=3, lease_until=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(claim_job())
        self.assertEqual(ImageJob.objects.get(pk=old.pk).status, 'error')

    def test_preferences_do_not_backfill_and_publication_hook_enqueues(self):
        # Do not rely on filesystem writes and timezone.now having distinct clock ticks.
        before = (timezone.now() - timedelta(minutes=1)).timestamp()
        after = (timezone.now() + timedelta(minutes=1)).timestamp()
        for index in (0, 1):
            os.utime(self.source_dir / f'{index}.png', (before, before))
        response = self.post(action='preferences', automatic=True, strength='medium')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ImageJob.objects.count(), 0)
        service = HistoryService()
        service.sync_record_images('record', 'task', ['0.png', '1.png'])
        self.assertEqual(ImageJob.objects.count(), 0)
        self.image(0, 'green')
        os.utime(self.source_dir / '0.png', (after, after))
        service.sync_record_images('record', 'task', ['0.png', '1.png'])
        self.assertEqual(ImageJob.objects.count(), 1)
        self.assertEqual(ImageJob.objects.get().strength, 'medium')
        self.post(action='preferences', automatic=False, strength='heavy')
        self.image(1, 'green')
        os.utime(self.source_dir / '1.png', (after, after))
        service.sync_record_images('record', 'task', ['0.png', '1.png'])
        self.assertEqual(ImageJob.objects.count(), 1)
        self.assertEqual(self.client.get(self.url).json()['preferences'],
                         {'automatic': False, 'strength': 'heavy'})

    def test_deleted_page_invalidates_inflight_work(self):
        self.enqueue(indices=[1])
        job = claim_job()
        self.record.outline = {'pages': [{'index': 0, 'content': 'first'}]}
        self.record.save()
        with patch('postprocessing.services.process_image', side_effect=self.transform):
            run_job(job)
        self.assertEqual(len(self.client.get(self.url).json()['pages']), 1)
        self.assertFalse(ImagePage.objects.filter(record=self.record, index=1).exists())

    def test_path_traversal_rejected_without_leaking_paths(self):
        self.record.images = {'task_id': '../task', 'generated': ['0.png']}
        self.record.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['pages'], [])
        self.assertNotIn(str(self.root), response.content.decode())

    def test_undecodable_output_never_published(self):
        self.enqueue()
        def invalid(source, output, strength):
            output.write_bytes(b'not an image')
        with patch('postprocessing.services.process_image', side_effect=invalid):
            run_job(claim_job())
        page = self.client.get(self.url).json()['pages'][0]
        self.assertEqual(page['status'], 'error')
        self.assertIsNone(page['processed_url'])

    def test_real_synthetic_image_processing(self):
        original = (self.source_dir / '0.png').read_bytes()
        self.enqueue()
        call_command('process_images', once=True)
        page = self.client.get(self.url).json()['pages'][0]
        self.assertEqual(page['status'], 'done', page)
        response = self.client.get(page['processed_url'])
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content)
        self.assertNotEqual(hashlib.sha256(content).hexdigest(), hashlib.sha256(original).hexdigest())
        self.assertEqual((self.source_dir / '0.png').read_bytes(), original)

    def test_get_before_publication_does_not_consume_automatic_trigger(self):
        self.post(action='preferences', automatic=True, strength='light')
        self.image(0, 'green')
        self.client.get(self.url)
        self.assertEqual(ImageJob.objects.count(), 0)
        HistoryService().sync_record_images('record', 'task', ['0.png', '1.png'])
        self.assertEqual(ImageJob.objects.count(), 1)
        HistoryService().sync_record_images('record', 'task', ['0.png', '1.png'])
        self.assertEqual(ImageJob.objects.count(), 1)

    def test_preferences_are_account_wide_without_old_record_backfill(self):
        record = HistoryRecord.objects.create(
            id='other_record', user=self.owner, outline=self.record.outline, images=self.record.images)
        self.post(action='preferences', automatic=True, strength='heavy')
        self.assertEqual(self.client.get('/api/postprocessing/other_record').json()['preferences'],
                         {'automatic': True, 'strength': 'heavy'})
        HistoryService().sync_record_images(record.pk, 'task', ['0.png', '1.png'])
        self.assertEqual(ImageJob.objects.count(), 0)

    def test_reordered_page_identity_does_not_inherit_processed_version(self):
        self.enqueue()
        self.finish()
        self.record.outline['pages'].reverse()
        for index, page in enumerate(self.record.outline['pages']):
            page['index'] = index
        self.record.save()
        self.assertIsNone(self.client.get(self.url).json()['pages'][0]['processed_url'])

    def test_original_and_processed_old_urls_rejected_after_regeneration(self):
        self.enqueue()
        self.finish()
        page = self.client.get(self.url).json()['pages'][0]
        self.image(0, 'green')
        self.assertEqual(self.client.get(page['original_url']).status_code, 404)
        self.assertEqual(self.client.get(page['processed_url']).status_code, 404)

    def test_output_tampering_invalidates_current_result(self):
        self.enqueue()
        self.finish()
        job = ImageJob.objects.get()
        (self.root / job.output_path).write_bytes(b'invalid')
        page = self.client.get(self.url).json()['pages'][0]
        self.assertIsNone(page['processed_url'])
        self.assertEqual(page['adopted'], 'original')
        self.enqueue()
        self.assertEqual(ImageJob.objects.count(), 2)

    def test_null_json_is_not_a_successful_mutation(self):
        response = self.client.post(self.url, 'null', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_algorithm_change_does_not_mislabel_outputs(self):
        self.enqueue()
        with patch('postprocessing.services.algorithm_version', return_value='different'):
            run_job(claim_job())
        self.assertEqual(ImageJob.objects.get().status, 'error')

    def test_late_expired_attempt_cannot_replace_recovered_attempt_result(self):
        self.enqueue()
        old = claim_job()
        ImageJob.objects.filter(pk=old.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        recovered = claim_job()
        with patch('postprocessing.services.process_image', side_effect=self.transform):
            run_job(recovered)
        before = ImageJob.objects.get().output_digest
        with patch('postprocessing.services.process_image') as processor:
            run_job(old)
        processor.assert_not_called()
        self.assertEqual(ImageJob.objects.get().output_digest, before)

    def test_served_original_is_a_snapshot_during_regeneration(self):
        page = self.client.get(self.url).json()['pages'][0]
        original = (self.source_dir / '0.png').read_bytes()
        stream = image_file('record', self.owner.pk, 0, 'original', page['source_revision'])
        self.image(0, 'green')
        self.assertEqual(stream.read(), original)
        stream.close()

    def test_owner_directory_symlink_cannot_escape_to_another_owner(self):
        link = self.source_dir / 'escape'
        other = self.root / self.other.pk
        other.mkdir()
        try:
            link.symlink_to(other, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symlinks requires platform privileges.')
        with self.assertRaises(ValueError):
            safe_path('u_owner/task/escape/image.png')

    def test_independent_processes_deduplicate_submission_and_claim(self):
        # A file-backed database exercises actual SQLite cross-process locks,
        # rather than TestCase's single-connection transaction or in-memory DB.
        from django.conf import settings
        database = self.root / 'concurrency.sqlite3'
        prefix = (
            "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; "
            "from django.conf import settings; "
            f"settings.DATABASES['default']['NAME']={str(database)!r}; "
            f"settings.HISTORY_ROOT=__import__('pathlib').Path({str(self.root)!r}); "
            "import django; django.setup(); "
        )
        setup = (
            "from django.core.management import call_command; call_command('migrate',verbosity=0); "
            "from accounts.models import User; from history.models import HistoryRecord; "
            "u=User.objects.create(id='u_owner',username='owner'); "
            "HistoryRecord.objects.create(id='record',user=u,"
            "outline={'pages':[{'index':0,'content':'first'}]},"
            "images={'task_id':'task','generated':['0.png']})"
        )
        kwargs = {
            'cwd': settings.BASE_DIR,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'text': True,
            'creationflags': subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        }
        subprocess.run([sys.executable, '-c', prefix + setup], check=True, timeout=30, **kwargs)

        def concurrent(code):
            processes = []
            try:
                processes = [subprocess.Popen([sys.executable, '-c', prefix + code], **kwargs)
                             for _ in range(2)]
                output = []
                for process in processes:
                    stdout, stderr = process.communicate(timeout=30)
                    self.assertEqual(process.returncode, 0, stderr)
                    output.append(stdout.strip())
                return output
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()

        submitted = concurrent(
            "from postprocessing.services import record_state; "
            "from postprocessing.models import ImageJob; "
            "record_state('record','u_owner',{'action':'process','indices':[0],'strength':'light'}); "
            "print(ImageJob.objects.count())"
        )
        self.assertEqual(submitted, ['1', '1'])
        claimed = concurrent(
            "from postprocessing.services import claim_job; "
            "job=claim_job(); print(str(job.pk) if job else 'empty')"
        )
        self.assertEqual(claimed.count('empty'), 1)

    def test_generation_publication_method_automatically_enqueues(self):
        from generation.services.image import ImageService
        self.post(action='preferences', automatic=True, strength='heavy')
        service = ImageService.__new__(ImageService)
        service.history_service = HistoryService()
        self.image(0, 'green')
        self.assertTrue(service._merge_image_into_record('record', 'task', 0, '0.png', total_count=2))
        self.assertEqual(ImageJob.objects.get().strength, 'heavy')

    def test_outline_update_is_not_a_generation_publication(self):
        self.post(action='preferences', automatic=True, strength='light')
        self.image(0, 'green')
        HistoryService().update_record('record', outline=self.record.outline, images=None)
        self.assertEqual(ImageJob.objects.count(), 0)

    def test_resolved_path_must_stay_within_owner(self):
        root = self.root.resolve()
        with patch('postprocessing.services.Path.resolve',
                   side_effect=[root, root / self.other.pk / '0.png']):
            with self.assertRaises(ValueError):
                safe_path('u_owner/task/0.png')

    def test_history_thumbnail_uses_first_valid_adopted_page_without_full_sync(self):
        from history.services import _to_detail, _to_list_item
        from . import services
        self.enqueue(indices=[0, 1])
        self.finish()
        self.finish()
        pages = self.client.get(self.url).json()['pages']
        with patch('postprocessing.services._reconcile', side_effect=AssertionError('Unexpected sync')):
            with patch('postprocessing.services._originals', wraps=services._originals) as originals:
                self.assertEqual(_to_list_item(self.record)['adopted_thumbnail_url'],
                                 pages[0]['processed_url'])
                originals.assert_called_once_with(self.record, indices={0})
            self.assertEqual(_to_detail(self.record)['adopted_thumbnail_url'], pages[0]['processed_url'])
        self.post(action='adopt', index=0, version='original',
                  source_revision=pages[0]['source_revision'])
        self.assertEqual(_to_list_item(self.record)['adopted_thumbnail_url'], pages[1]['processed_url'])
        self.image(1, 'green')
        self.assertIsNone(_to_list_item(self.record)['adopted_thumbnail_url'])
        self.assertIsNone(_to_detail(self.record)['adopted_thumbnail_url'])

    def test_history_thumbnail_ignores_corrupt_output_and_returns_null_for_legacy(self):
        from history.services import _to_list_item
        self.assertIsNone(_to_list_item(self.record)['adopted_thumbnail_url'])
        self.enqueue()
        self.finish()
        (self.root / ImageJob.objects.get().output_path).write_bytes(b'bad')
        self.assertIsNone(_to_list_item(self.record)['adopted_thumbnail_url'])

    def test_delete_record_cleans_only_its_processing_outputs(self):
        self.enqueue()
        self.finish()
        own = record_output_directory(self.record.pk, self.owner.pk)
        self.assertTrue(own.exists())
        other_record = HistoryRecord.objects.create(
            id='second_record', user=self.owner,
            outline=self.record.outline, images=self.record.images)
        self.url = '/api/postprocessing/second_record'
        self.enqueue()
        self.finish()
        other = record_output_directory(other_record.pk, self.owner.pk)
        other_output = ImageJob.objects.get(page__record=other_record).output_path
        before = (self.root / other_output).read_bytes()
        HistoryService().delete_record(self.record.pk)
        self.assertFalse(own.exists())
        self.assertTrue(other.exists())
        self.assertEqual((self.root / other_output).read_bytes(), before)
        self.assertFalse(ImageJob.objects.filter(page__record_id=self.record.pk).exists())

    def test_deleted_record_late_worker_does_not_publish(self):
        self.enqueue()
        job = claim_job()
        def delete_during_processing(source, output, strength):
            self.transform(source, output, strength)
            HistoryService().delete_record(self.record.pk)
        with patch('postprocessing.services.process_image', side_effect=delete_during_processing):
            run_job(job)
        self.assertFalse(ImageJob.objects.exists())
        self.assertFalse(record_output_directory(self.record.pk, self.owner.pk).exists())

    def test_readonly_original_permissions_are_preserved(self):
        source = self.source_dir / '0.png'
        original_mode = source.stat().st_mode
        source.chmod(stat.S_IREAD)
        readonly_mode = source.stat().st_mode
        try:
            self.enqueue()
            self.finish()
            self.assertEqual(source.stat().st_mode, readonly_mode)
            self.assertEqual(self.client.get(self.url).json()['pages'][0]['status'], 'done')
        finally:
            source.chmod(original_mode)

    def assert_selects_only(self, queries):
        for query in queries:
            self.assertTrue(query['sql'].lstrip().upper().startswith('SELECT'), query['sql'])

    def test_image_get_is_readonly_and_only_hashes_requested_source(self):
        from . import services
        self.enqueue()
        self.finish()
        page = self.client.get(self.url).json()['pages'][0]
        for url in (page['original_url'], page['processed_url']):
            with patch('postprocessing.services._reconcile', side_effect=AssertionError('reconcile')):
                with patch('postprocessing.services._originals', wraps=services._originals) as originals:
                    with CaptureQueriesContext(connection) as queries:
                        response = self.client.get(url)
                        self.assertEqual(response.status_code, 200)
                        b''.join(response.streaming_content)
                        response.close()
                    self.assert_selects_only(queries)
                    self.assertEqual(originals.call_count, 1)
                    self.assertEqual(originals.call_args.kwargs, {'indices': {0}})

    def test_polling_is_readonly_including_new_and_stale_pages(self):
        for _ in range(2):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assert_selects_only(queries)
        self.assertFalse(ImagePage.objects.exists())
        self.enqueue()
        self.finish()
        self.image(0, 'green')
        with CaptureQueriesContext(connection) as queries:
            page = self.client.get(self.url).json()['pages'][0]
        self.assert_selects_only(queries)
        self.assertEqual(page['status'], 'idle')
        self.assertIsNone(page['processed_url'])
        # Submission still reconciles persisted state before deduplication.
        self.enqueue()
        self.assertEqual(ImageJob.objects.filter(status='queued').count(), 1)

    def test_image_get_rejects_stale_source_without_prior_polling(self):
        self.enqueue()
        self.finish()
        page = self.client.get(self.url).json()['pages'][0]
        self.image(0, 'green')
        for url in (page['original_url'], page['processed_url']):
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(self.client.get(url).status_code, 404)
            self.assert_selects_only(queries)

    def test_processor_logs_only_fixed_category_and_chinese_ui_error(self):
        self.enqueue()
        error = subprocess.CalledProcessError(
            1, ['secret-command', 'C:/private/credential'], stderr='secret stderr')
        with self.assertLogs('postprocessing.services', level='WARNING') as logs:
            with patch('postprocessing.services.process_image', side_effect=error):
                run_job(claim_job())
        message = '\n'.join(logs.output)
        self.assertIn('category=processor_exit', message)
        self.assertNotIn('secret', message)
        self.assertNotIn('private', message)
        self.assertEqual(self.client.get(self.url).json()['pages'][0]['error'], '图片处理失败，请重试。')
