import io
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock

from django.test import SimpleTestCase
from PIL import Image

from .style_samples import run, sample_prompt


class StyleSampleTests(SimpleTestCase):
    def test_uses_actual_style_and_page_prompt(self):
        prompt = sample_prompt('watercolor')
        self.assertIn('透明水彩', prompt)
        self.assertIn('观察叶片', prompt)
        self.assertIn('检查盆土', prompt)

    def test_resume_does_not_repeat_paid_calls(self):
        buffer = io.BytesIO()
        Image.new('RGB', (1536, 2048), 'white').save(buffer, 'PNG')
        generate = Mock(return_value=buffer.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            args = dict(root=Path(directory), interval=0, generate=generate)
            run({'model': 'gpt-image-test'}, ['comic'], **args)
            run({'model': 'gpt-image-test'}, ['comic'], **args)
            self.assertEqual(generate.call_count, 1)

    def test_failure_stops_batch_and_is_not_retried(self):
        generate = Mock(side_effect=RuntimeError('secret-error'))
        with tempfile.TemporaryDirectory() as directory:
            args = dict(root=Path(directory), interval=0, generate=generate)
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    run({'model': 'gpt-image-test'}, ['comic', 'watercolor'], **args)
            self.assertEqual(generate.call_count, 1)
            record = (Path(directory) / 'run.json').read_text(encoding='utf-8')
            self.assertNotIn('secret-error', record)
            self.assertEqual(json.loads(record)['samples']['comic']['status'], 'failed')
