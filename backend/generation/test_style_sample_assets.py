import json
from pathlib import Path

from django.test import SimpleTestCase
from PIL import Image

from .styles import CATALOG

ROOT = Path(__file__).resolve().parents[2]


class StyleSampleAssetTests(SimpleTestCase):
    def test_all_styles_have_an_explicit_review_outcome(self):
        directory = ROOT / 'frontend/src/features/styles'
        samples = json.loads((directory / 'samples.json').read_text(encoding='utf-8'))
        issues = json.loads((directory / 'sampleIssues.json').read_text(encoding='utf-8'))
        ids = [item['id'] for item in samples + issues]
        self.assertCountEqual(ids, [item['id'] for item in CATALOG])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len({item['image_sha256'] for item in samples}), len(samples))
        self.assertTrue(all(item['reason'] for item in issues))

    def test_published_images_are_real_distinct_2k_files(self):
        samples = json.loads((ROOT / 'frontend/src/features/styles/samples.json').read_text(encoding='utf-8'))
        directions = {item['id']: item['direction'] for item in CATALOG}
        for sample in samples:
            with self.subTest(style=sample['id']):
                self.assertEqual(sample['review'], 'approved')
                self.assertEqual(sample['direction'], directions[sample['id']])
                self.assertTrue(sample['prompt_sha256'])
                for field in ('url', 'thumbnail'):
                    self.assertTrue(sample[field].startswith('/assets/styles/samples/'))
                    path = ROOT / 'frontend/public' / sample[field].lstrip('/')
                    with Image.open(path) as image:
                        image.load()
                        self.assertEqual(image.format, 'WEBP')
                        expected = (sample['width'], sample['height']) if field == 'url' else (576, 768)
                        self.assertEqual(image.size, expected)
                self.assertGreaterEqual(sample['width'], 1536)
                self.assertGreaterEqual(sample['height'], 2048)
