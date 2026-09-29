import importlib.util
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeploymentTests(TestCase):
    def test_package_excludes_secrets_and_runtime_data(self):
        pack = load("pack", ROOT / "pack_deploy.py")
        for path in ("image_providers.yaml", "text_providers.yaml", ".env", ".env.production",
                     "data/db.sqlite3", "history/u/test.png", "output/style-samples/run.json",
                     "user_configs/u/config.yaml", "frontend/test-results/test.png",
                     ".superpowers/brainstorm/test.html", "private.key"):
            self.assertTrue(pack._skip(path, False), path)
        for path in ("README.md", ".dockerignore", ".env.example", "requirements.txt",
                     "backend/history/models.py", "frontend/pnpm-lock.yaml",
                     "frontend/public/assets/styles/samples/a.webp", "deploy/start.py"):
            self.assertFalse(pack._skip(path, False), path)

    def test_production_requires_explicit_credentials_and_hosts(self):
        start = load("start", ROOT / "deploy/start.py")
        good = {"DJANGO_SECRET_KEY": "a" * 64, "ADMIN_PASSWORD": "a-long-password",
                "DJANGO_ALLOWED_HOSTS": "127.0.0.1,example.com"}
        start.validate_environment(good)
        for key, value in (("DJANGO_SECRET_KEY", ""), ("ADMIN_PASSWORD", "admin123"),
                           ("DJANGO_ALLOWED_HOSTS", "*"), ("DJANGO_ALLOWED_HOSTS", "example.com")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                start.validate_environment({**good, key: value})
