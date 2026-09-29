import json
import io
import base64
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from accounts.models import User, Token
from history.models import HistoryRecord, ImageCandidate
from history.services import get_history_service
from postprocessing.services import _originals
from generation.candidates import directory
from generation.styles import style_prompt, format_image_prompt
from prompts.services import safe_format


class CandidateTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = override_settings(HISTORY_ROOT=Path(self.temp.name))
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.user = User.objects.create(id='trial-owner', username='trial-owner')
        Token.objects.create(user=self.user, key='trial-token', expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer trial-token'
        self.record = HistoryRecord.objects.create(
            id='trial-work', user=self.user, title='Desk tips',
            outline={'pages': [{'index': 0, 'type': 'cover', 'content': 'Desk'},
                               {'index': 1, 'type': 'content', 'content': 'Clear desk'}]},
            images={'generated': []},
        )
        self.factory = patch('generation.candidates.get_image_service')
        self.service = self.factory.start().return_value
        self.service.provider_config = {}
        self.service.generator.config = {}
        self.addCleanup(self.factory.stop)
        self.service._generate_single_image.side_effect = self.render
        self.prompt = patch('generation.image_prompt.get_base_prompt', return_value='Draw {page_content} as a photo')
        self.prompt.start()
        self.addCleanup(self.prompt.stop)

    def render(self, page, task, **kwargs):
        Image.new('RGB', (20, 20), '#56aa88').save(Path(kwargs['task_dir']) / f'{page["index"]}.png')
        return page['index'], True, f'{page["index"]}.png', None

    def create(self, index=1, request_id=None, **extra):
        return self.client.post('/api/image-candidates/trial-work', json.dumps({
            'request_id': request_id or str(uuid.uuid4()), 'index': index,
            'image_style': {'preset': 'sketch-note', 'notes': 'blue'},
            **extra,
        }), content_type='application/json')

    def adopt(self, candidate, expected=''):
        return self.client.post(f'/api/image-candidates/trial-work/{candidate["id"]}/adopt',
                                json.dumps({'expected_filename': expected}), content_type='application/json')

    def test_trial_forwards_style_and_does_not_publish(self):
        response = self.create()
        self.assertEqual(response.status_code, 200)
        candidate = response.json()['candidate']
        self.record.refresh_from_db()
        self.assertEqual(self.record.images['generated'], [])
        self.assertEqual(self.record.image_style, {})
        kwargs = self.service._generate_single_image.call_args.kwargs
        self.assertNotIn('record_id', kwargs)
        self.assertNotIn('reference_image', kwargs)
        self.assertIn('禁止摄影主体', kwargs['prompt_text'])
        self.assertEqual(candidate['prompt'], format_image_prompt(kwargs['prompt_text'], {
            'page_content': 'Clear desk', 'page_type': 'content',
            'full_outline': 'Desk\n\n<page>\n\nClear desk', 'user_topic': 'Desk tips',
        }))
        image_response = self.client.get(candidate['image_url'])
        self.assertEqual(image_response.status_code, 200)
        image_response.close()

    def test_preview_matches_candidate_and_does_not_generate_or_save(self):
        page = self.record.outline['pages'][1]
        payload = {
            'page': page, 'topic': self.record.title,
            'image_style': {'preset': 'sketch-note', 'notes': 'blue'},
            'image_parameters': {'resolution': '1K', 'aspect_ratio': '3:4', 'quality': 'low', 'output_format': 'png'},
        }
        response = self.client.post('/api/image-prompt/preview', json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.service._generate_single_image.assert_not_called()
        self.assertFalse(ImageCandidate.objects.exists())
        self.assertEqual(response.json()['references']['mode'], 'text_to_image')
        self.assertEqual(response.json()['gpt_images_parameters']['quality'], 'low')
        generated = self.create(image_prompt_name='obsolete-template')
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(response.json()['prompt'], generated.json()['candidate']['prompt'])

    def test_platform_preview_matches_actual_candidate(self):
        preferences = {"platform": "douyin", "goal": "follow"}
        self.record.outline["generation_preferences"] = preferences
        self.record.save()
        preview = self.client.post('/api/image-prompt/preview', json.dumps({
            "page": self.record.outline["pages"][1], "topic": self.record.title,
            "generation_preferences": preferences,
            "image_style": {"preset": "sketch-note", "notes": "blue"},
        }), content_type="application/json")
        actual = self.create()
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(actual.status_code, 200)
        self.assertEqual(preview.json()["prompt"], actual.json()["candidate"]["prompt"])
        self.assertIn("douyin", actual.json()["candidate"]["prompt"])

    def test_preview_rejects_invalid_settings_without_generation(self):
        response = self.client.post('/api/image-prompt/preview', json.dumps({
            'page': self.record.outline['pages'][0], 'image_parameters': {'quality': 'invalid'},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.service._generate_single_image.assert_not_called()
        self.assertFalse(ImageCandidate.objects.exists())

    def test_palette_layout_and_parameters_match_preview_and_generation(self):
        self.record.outline["pages"][1]["content"] = "[内容]\n单页布局：对比\n上图文字：整理前后"
        self.record.save()
        style = {"preset": "infographic", "notes": "保留安全边距",
                 "palette": {"mode": "custom", "primary": "#123456",
                             "background": "#FFFFFF", "accent": "#FFAA00"}}
        parameters = {"resolution": "2K", "aspect_ratio": "9:16",
                      "quality": "low", "output_format": "png"}
        preview = self.client.post("/api/image-prompt/preview", json.dumps({
            "page": self.record.outline["pages"][1], "topic": self.record.title,
            "image_style": style, "image_parameters": parameters,
        }), content_type="application/json")
        actual = self.create(image_style=style, image_parameters=parameters)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(actual.status_code, 200)
        self.assertEqual(preview.json()["parameters"], parameters)
        self.assertEqual(preview.json()["prompt"], actual.json()["candidate"]["prompt"])
        for phrase in ("#123456", "#FFAA00", "单页布局规则：对比", "保留安全边距"):
            self.assertIn(phrase, preview.json()["prompt"])

    def test_reference_palette_adds_only_color_permission_and_matches_preview(self):
        style = {"preset": "infographic", "notes": "", "palette": {"mode": "reference"}}
        preview = self.client.post("/api/image-prompt/preview", json.dumps({
            "page": self.record.outline["pages"][1], "topic": self.record.title,
            "image_style": style, "reference_count": 1, "reference_roles": ["subject"],
        }), content_type="application/json")
        actual = self.create(image_style=style, reference_roles=["subject"],
                             user_images=[base64.b64encode(b"reference").decode()])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(actual.status_code, 200)
        self.assertEqual(preview.json()["references"]["roles"], ["subject", "color"])
        self.assertEqual(preview.json()["prompt"], actual.json()["candidate"]["prompt"])
        self.assertIn("参考图片仅用于：图片主体与关键特征、色彩与材质", preview.json()["prompt"])

    def test_subject_only_preview_matches_actual_request(self):
        payload = {
            'page': self.record.outline['pages'][1], 'topic': self.record.title,
            'image_style': {'preset': 'sketch-note', 'notes': 'blue'},
            'reference_count': 1, 'reference_roles': ['subject'],
        }
        preview = self.client.post('/api/image-prompt/preview', json.dumps(payload),
                                   content_type='application/json')
        generated = self.create(user_images=[base64.b64encode(b'reference').decode()],
                                reference_roles=['subject'])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(preview.json()['prompt'], generated.json()['candidate']['prompt'])
        self.assertEqual(preview.json()['references']['roles'], ['subject'])
        self.assertIn('参考图片仅用于：图片主体与关键特征。',
                      self.service._generate_single_image.call_args.kwargs['prompt_text'])

    def test_invalid_reference_selection_does_not_generate(self):
        response = self.create(reference_roles=[{}])
        self.assertEqual(response.status_code, 400)
        self.service._generate_single_image.assert_not_called()

    def test_adoption_preserves_versions_and_postprocessing_source(self):
        first = self.create().json()['candidate']
        with self.captureOnCommitCallbacks(execute=True):
            response = self.adopt(first)
        self.assertEqual(response.status_code, 200)
        filename = response.json()['filename']
        self.record.refresh_from_db()
        self.assertEqual(self.record.images['generated'], ['', filename])
        sources = _originals(self.record)
        self.assertEqual([source[0] for source in sources], [1])
        revision = sources[0][2]
        second = self.create().json()['candidate']
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.adopt(second, filename).status_code, 200)
        self.record.refresh_from_db()
        self.assertNotEqual(_originals(self.record)[0][2], revision)
        image_response = self.client.get(first['image_url'])
        self.assertEqual(image_response.status_code, 200)
        image_response.close()
        self.assertEqual(self.record.image_candidates.count(), 2)
        self.assertEqual(self.adopt(first, filename).status_code, 409)
        current = self.record.images['generated'][1]
        self.assertEqual(self.adopt(first, current).status_code, 200)

    def test_candidate_image_accepts_browser_query_token_and_stays_private(self):
        candidate = self.create().json()['candidate']
        self.client.defaults.pop('HTTP_AUTHORIZATION')
        self.assertEqual(self.client.get(candidate['image_url']).status_code, 401)
        response = self.client.get(candidate['image_url'], {'token': 'trial-token'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('no-store', response['Cache-Control'])
        response.close()

    def test_trial_resolves_auto_and_respects_explicit_selection(self):
        self.record.image_style = {'preset': 'auto', 'notes': '',
                                   'recommendation': {'preset': 'ink', 'reason': '文化主题', 'alternatives': ['pencil']}}
        self.record.save()
        automatic = self.create(image_style={'preset': 'auto', 'notes': ''}).json()['candidate']
        self.assertEqual(automatic['style'], {'preset': 'ink', 'notes': ''})
        explicit = self.create(image_style={'preset': 'clay', 'notes': ''}).json()['candidate']
        self.assertEqual(explicit['style'], {'preset': 'clay', 'notes': ''})
        self.assertNotIn('文化主题', explicit['prompt'])
        self.assertNotIn('水墨写意', explicit['prompt'])
        self.assertIn('黏土', explicit['prompt'])
        self.record.refresh_from_db()
        self.assertEqual(self.record.image_style['preset'], 'auto')

    def test_failure_and_stale_adoption_leave_original_unchanged(self):
        first = self.create().json()['candidate']
        self.adopt(first)
        self.record.refresh_from_db()
        images = self.record.images
        self.service._generate_single_image.return_value = (1, False, None, 'Failed')
        self.service._generate_single_image.side_effect = None
        self.assertEqual(self.create().status_code, 502)
        self.record.refresh_from_db()
        self.assertEqual(self.record.images, images)
        self.record.outline['pages'][1]['content'] = 'Changed content'
        self.record.save()
        self.assertEqual(self.adopt(first, images['generated'][1]).status_code, 409)

    def test_idempotency_and_permission(self):
        request_id = str(uuid.uuid4())
        first = self.create(request_id=request_id).json()['candidate']
        self.assertEqual(self.create(request_id=request_id).json()['candidate']['id'], first['id'])
        self.assertEqual(self.service._generate_single_image.call_count, 1)
        other = User.objects.create(id='other-trial', username='other-trial')
        self.record.user = other
        self.record.save()
        self.assertEqual(self.client.get('/api/image-candidates/trial-work').status_code, 403)
        self.assertEqual(self.client.get(first['image_url']).status_code, 403)
        self.assertEqual(self.adopt(first).status_code, 403)
        self.assertEqual(self.create().status_code, 403)
        self.assertEqual(self.service._generate_single_image.call_count, 1)

    def test_scan_does_not_publish_candidates_or_archives(self):
        first = self.create().json()['candidate']
        self.adopt(first)
        second = self.create().json()['candidate']
        self.record.refresh_from_db()
        images = dict(self.record.images)
        service = get_history_service()
        service._sync_record_images(self.record)
        self.record.refresh_from_db()
        self.assertEqual(self.record.images, images)
        self.assertFalse(second['adopted'])

    def test_legacy_image_preserved_on_first_adoption(self):
        candidate = self.create().json()['candidate']
        self.record.refresh_from_db()
        root = Path(self.temp.name) / self.user.pk / self.record.images['task_id']
        Image.new('RGB', (20, 20), 'red').save(root / '1.png')
        self.record.images['generated'] = ['', '1.png']
        self.record.save()
        self.assertEqual(self.adopt(candidate, '1.png').status_code, 200)
        legacy = self.record.image_candidates.get(filename='1.png')
        self.assertTrue((directory(self.record, legacy.task_id, legacy.pk) / '1.png').exists())

    def test_style_conflict_constraints(self):
        for preset in ('comic', 'sketch-note', 'watercolor', 'pencil', 'infographic'):
            prompt = style_prompt('Original photography {page_content}', {'preset': preset})
            self.assertIn('最高优先级视觉约束', prompt)
            self.assertIn('参考图外观冲突', prompt)
            self.assertIn('{page_content}', prompt)

    def test_explicit_references_are_forwarded_without_an_old_cover(self):
        reference = b'synthetic-reference'
        response = self.create(user_images=[base64.b64encode(reference).decode()])
        self.assertEqual(response.status_code, 200)
        kwargs = self.service._generate_single_image.call_args.kwargs
        self.assertEqual(kwargs['user_images'], [reference])
        self.assertNotIn('reference_image', kwargs)
        self.assertIn('1 张用户参考图片', response.json()['candidate']['prompt'])
        self.assertEqual(self.create(user_images=['not-base64']).status_code, 400)

    def test_enabled_cover_uses_adopted_version_not_latest_trial(self):
        first = self.create(index=0).json()['candidate']
        self.adopt(first)
        self.create(index=0)
        self.record.refresh_from_db()
        root = Path(self.temp.name) / self.user.pk / self.record.images['task_id']
        from generation.utils.image_compressor import compress_image
        expected = compress_image((root / self.record.images['generated'][0]).read_bytes(), max_size_kb=200)
        response = self.create(use_reference=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service._generate_single_image.call_args.kwargs['reference_image'], expected)
        self.assertIn('第一张', response.json()['candidate']['prompt'])
        self.assertEqual(self.create(use_reference=False).status_code, 200)
        self.assertNotIn('reference_image', self.service._generate_single_image.call_args.kwargs)

    def test_cover_required_only_for_following_pages(self):
        response = self.create(use_reference=True)
        self.assertEqual(response.status_code, 400)
        self.service._generate_single_image.assert_not_called()
        self.assertFalse(ImageCandidate.objects.exists())
        self.assertEqual(self.create(index=0, use_reference=True).status_code, 200)
        self.assertNotIn('reference_image', self.service._generate_single_image.call_args.kwargs)
        self.assertEqual(self.create(use_reference='false').status_code, 400)

    def test_missing_cover_file_does_not_silently_generate_without_reference(self):
        first = self.create(index=0).json()['candidate']
        self.adopt(first)
        self.record.refresh_from_db()
        root = Path(self.temp.name) / self.user.pk / self.record.images['task_id']
        (root / self.record.images['generated'][0]).unlink()
        self.service._generate_single_image.reset_mock()
        self.assertEqual(self.create(use_reference=True).status_code, 400)
        self.service._generate_single_image.assert_not_called()

    def test_candidate_pipeline_uploads_cover_to_edits(self):
        from generation.services.image import ImageService
        from generation.utils.image_compressor import compress_image
        image = io.BytesIO()
        Image.new('RGB', (20, 20), 'red').save(image, 'PNG')
        config = {'type': 'image_api', 'api_key': 'test-only', 'base_url': 'https://relay.example',
                  'model': 'gpt-image-2.5-flare', 'endpoint_type': '/v1/images/edits',
                  'request_interval_seconds': 0}
        with patch('generation.services.image.get_image_provider_config', return_value=config):
            service = ImageService('test-relay', self.user.pk)
        response = Mock(status_code=200, headers={}, json=lambda: {
            'data': [{'b64_json': base64.b64encode(image.getvalue()).decode()}]})
        with patch('generation.candidates.get_image_service', return_value=service), \
                patch('generation.diagnostics.record') as upstream_log, \
                patch('generation.services.image.record') as local_log, \
                patch('generation.generators.gpt_images.requests.post', return_value=response) as post:
            first_response = self.create(index=0, use_reference=True)
            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(post.call_args.args[0], 'https://relay.example/v1/images/generations')
            first = first_response.json()['candidate']
            self.adopt(first)
            second = self.create(use_reference=True)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(post.call_args.args[0], 'https://relay.example/v1/images/edits')
            kwargs = post.call_args.kwargs
            self.assertEqual(kwargs['files'][0][0], 'image')
            self.assertEqual(kwargs['files'][0][1][1], compress_image(image.getvalue(), max_size_kb=200))
            self.assertEqual(kwargs['files'][0][1][2], 'image/png')
            self.assertEqual(kwargs['data']['n'], 1)
            self.assertNotIn('json', kwargs)
            local = next(call.args[1] for call in reversed(local_log.call_args_list)
                         if call.args[1]['event'] == 'request')
            self.assertEqual(local['references']['cover_count'], 1)
            self.assertEqual(local['generation_id'], second.json()['candidate']['id'])
            upstream = next(call.args[1] for call in reversed(upstream_log.call_args_list)
                            if call.args[1]['event'] == 'request')
            self.assertEqual(upstream['endpoint'], 'https://relay.example/v1/images/edits')
            self.assertEqual(upstream['generation_id'], local['generation_id'])
            self.assertEqual(upstream['files'][0][1][1]['omitted'], 'binary')

    def test_preview_and_generation_agree_on_cover_reference(self):
        first = self.create(index=0).json()['candidate']
        self.adopt(first)
        response = self.client.post('/api/image-prompt/preview', json.dumps({
            'record_id': self.record.pk, 'use_reference': True,
            'page': self.record.outline['pages'][1], 'topic': self.record.title,
            'image_style': {'preset': 'sketch-note', 'notes': 'blue'},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['references'], {
            'count': 1, 'user_count': 0, 'cover_count': 1, 'mode': 'reference', 'roles': []})
        self.assertEqual(response.json()['prompt'], self.create(use_reference=True).json()['candidate']['prompt'])
