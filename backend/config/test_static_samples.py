from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import RequestFactory, SimpleTestCase, override_settings

from .urls import _spa_serve


class StaticSampleTests(SimpleTestCase):
    def test_spa_html_revalidates_the_current_bundle_on_refresh(self):
        with TemporaryDirectory() as folder:
            dist = Path(folder) / "frontend" / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text('<script src="/assets/current.js"></script>', encoding="utf-8")
            with override_settings(PROJECT_ROOT=Path(folder)):
                for path in ("/", "/index.html", "/workspace"):
                    with self.subTest(path=path):
                        response = _spa_serve(RequestFactory().get(path))
                        try:
                            self.assertEqual(response["Cache-Control"], "no-cache")
                            self.assertIn(b"current.js", b"".join(response.streaming_content))
                        finally:
                            response.close()

    def test_webp_has_explicit_image_type(self):
        with TemporaryDirectory() as folder:
            dist = Path(folder) / "frontend" / "dist"
            dist.mkdir(parents=True)
            (dist / "sample.webp").write_bytes(b"test image response")
            with override_settings(PROJECT_ROOT=Path(folder)):
                response = _spa_serve(RequestFactory().get("/sample.webp"))
                try:
                    self.assertEqual(response["Content-Type"], "image/webp")
                    self.assertEqual(b"".join(response.streaming_content), b"test image response")
                finally:
                    response.close()
