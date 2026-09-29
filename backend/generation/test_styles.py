import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, SimpleTestCase
from django.utils import timezone

from accounts.models import User, Token
from history.models import HistoryRecord
from generation.styles import (normalize_style, style_prompt, request_style, STYLE_DIRECTIONS,
                               CATALOG, extract_recommendation, resolve_style, normalize_recommendation, format_image_prompt)


class StyleTests(SimpleTestCase):
    def test_presets_do_not_change_page_placeholders(self):
        for preset in STYLE_DIRECTIONS:
            with self.subTest(preset=preset):
                text = style_prompt('Render {page_content}', {'preset': preset, 'notes': 'blue green'})
                self.assertIn('{page_content}', text)
                self.assertIn('blue green', text)
                self.assertIn('不能改变上图文字', text)

    def test_auto_without_recommendation_uses_concrete_fallback(self):
        self.assertIn(STYLE_DIRECTIONS['infographic'], style_prompt('Original', None))

    def test_catalog_is_complete_and_has_scenarios(self):
        self.assertGreaterEqual(len(CATALOG), 42)
        self.assertEqual(len(STYLE_DIRECTIONS), len(CATALOG) + 1)
        self.assertGreaterEqual(len({style['group'] for style in CATALOG}), 7)
        self.assertTrue({
            'brand-commercial', 'ugc-lifestyle', 'product-detail',
            'talking-cover', 'chat-proof', 'knowledge-card',
        } <= {style['id'] for style in CATALOG})
        for style in CATALOG:
            self.assertTrue(all(style[key] for key in ('scenes', 'caution', 'direction', 'preview')))

    def test_recommendation_is_separate_from_page_content(self):
        text = '[封面]\n上图文字：摄影的三个基础\n画面描述：三个区域'
        recommendation = {'preset': 'sketch-note', 'reason': '结构清楚', 'alternatives': ['comic', 'infographic']}
        clean, parsed = extract_recommendation(text + '\n<style-recommendation>' + json.dumps(recommendation) + '</style-recommendation>', '学习')
        self.assertEqual(clean, text)
        self.assertEqual(parsed, recommendation)
        self.assertEqual(resolve_style({'preset': 'auto', 'recommendation': parsed})['preset'], 'sketch-note')
        self.assertEqual(resolve_style({'preset': 'watercolor', 'recommendation': parsed})['preset'], 'watercolor')
        final = style_prompt('Render {page_content}', {'preset': 'watercolor', 'recommendation': parsed})
        self.assertIn(STYLE_DIRECTIONS['watercolor'], final)
        self.assertNotIn(STYLE_DIRECTIONS['sketch-note'], final)
        self.assertNotIn('结构清楚', final)

    def test_invalid_or_truncated_metadata_falls_back_without_leaking(self):
        for suffix in ('<style-recommendation>{bad}</style-recommendation>',
                       '<style-recommendation>{"preset":',
                       '<style-recommendation>{"preset": []}</style-recommendation>'):
            clean, parsed = extract_recommendation('[内容]笔记\n' + suffix, '学习方法')
            self.assertEqual(clean, '[内容]笔记')
            self.assertEqual(parsed['preset'], 'sketch-note')
        self.assertIsNone(normalize_recommendation({'preset': []}))

    def test_outline_service_requests_and_parses_metadata(self):
        from generation.services.outline import OutlineService
        service = object.__new__(OutlineService)
        service.user_id = None
        service.prompt_template = '{topic}'
        service.client = Mock()
        service.client.generate_text.return_value = (
            '[封面]\n上图文字：三个知识点\n画面描述：并列区域\n'
            '<style-recommendation>{"preset":"whiteboard","reason":"关系清楚","alternatives":["comic","infographic"]}</style-recommendation>')
        with patch('generation.services.outline.get_text_provider_config', return_value={}):
            result = service.generate_outline('知识点')
        self.assertTrue(result['success'])
        self.assertEqual(result['style_recommendation']['preset'], 'whiteboard')
        self.assertNotIn('style-recommendation', result['outline'])
        self.assertEqual(len(result['pages']), 1)
        self.assertIn('独立风格推荐元数据', service.client.generate_text.call_args.kwargs['prompt'])

    def test_old_visual_style_fields_are_not_sent_as_instructions(self):
        page = '上图文字：\n标题：摄影基础\n风格：认识摄影流派\n画面描述：\n风格：写实摄影\n配色方案：暖黄色\n两个主体并排对比'
        compiled = format_image_prompt(style_prompt('{page_content}\n{full_outline}', {'preset': 'ink'}),
                                       {'page_content': page, 'full_outline': page})
        self.assertIn('风格：认识摄影流派', compiled)
        self.assertIn('两个主体并排对比', compiled)
        self.assertNotIn('风格：写实摄影', compiled)
        self.assertNotIn('暖黄色', compiled)
        self.assertIn('最终风格：水墨插画', compiled)

    def test_invalid_values_rejected(self):
        for value in ([], 'comic', {'preset': []}, {'preset': 'missing'},
                      {'notes': 'x' * 601}, {'applied': {'applied': {}}}):
            with self.subTest(value=str(value)[:50]), self.assertRaises(ValueError):
                normalize_style(value)


class StyleApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(id='u_style', username='style')
        Token.objects.create(user=self.user, key='style-token',
                             expires_at=timezone.now() + timedelta(days=1))
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer style-token'
        self.choice = {'preset': 'comic', 'notes': 'blue green'}
        self.record = HistoryRecord.objects.create(
            id='style-work', user=self.user, image_style=self.choice,
            images={'task_id': 'style-task', 'generated': []},
        )

    def test_style_save_restore_and_task_fallback(self):
        self.assertEqual(self.client.get('/api/history/style-work').json()['record']['image_style'], self.choice)
        self.assertEqual(request_style({}, task_id='style-task'), self.choice)
        response = self.client.put('/api/history/style-work',
                                   json.dumps({'image_style': {'preset': 'watercolor', 'notes': ''}}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.image_style['preset'], 'watercolor')
        response = self.client.put('/api/history/style-work', json.dumps({'image_style': {'preset': 'bad'}}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.record.refresh_from_db()
        self.assertEqual(self.record.image_style['preset'], 'watercolor')

    @patch('generation.views.resolve_prompt_text', return_value='Render {page_content}')
    @patch('generation.views.get_image_service')
    def test_generation_and_retries_all_receive_style(self, factory, _resolve):
        service = Mock()
        service.provider_config = {}
        service.generator.config = {}
        service.generate_images.return_value = iter([{'event': 'complete', 'data': {'index': 0}}])
        service.retry_failed_images.return_value = iter([])
        service.retry_single_image.return_value = {'success': True}
        service.regenerate_image.return_value = {'success': True}
        factory.return_value = service
        for endpoint, method in (('generate', 'generate_images'), ('retry', 'retry_single_image'),
                                 ('retry-failed', 'retry_failed_images'), ('regenerate', 'regenerate_image')):
            with self.subTest(endpoint=endpoint):
                response = self.client.post('/api/' + endpoint, json.dumps({
                    'record_id': self.record.pk, 'task_id': 'style-task',
                    'page': {'index': 0, 'type': 'cover', 'content': 'Test'},
                    'pages': [{'index': 0, 'type': 'cover', 'content': 'Test'}],
                }), content_type='application/json')
                self.assertEqual(response.status_code, 200)
                if response.streaming:
                    list(response.streaming_content)
                self.assertIn(STYLE_DIRECTIONS['comic'], getattr(service, method).call_args.kwargs['image_prompt_text'])
                response.close()

    def test_reader_cannot_modify_style(self):
        other = User.objects.create(id='u_style_other', username='style_other')
        self.record.user = other
        self.record.save()
        response = self.client.put('/api/history/style-work', json.dumps({'image_style': self.choice}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 403)

    @patch('generation.views.resolve_prompt_text', return_value='Render {page_content}')
    @patch('generation.views.get_image_service')
    def test_invalid_style_is_rejected_before_provider_creation(self, factory, _resolve):
        response = self.client.post('/api/generate', json.dumps({
            'record_id': self.record.pk,
            'pages': [{'index': 0, 'type': 'cover', 'content': 'Test'}],
            'image_style': {'preset': 'not-a-style'},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        factory.assert_not_called()
