"""Shared production launcher for Linux and Docker; never starts paid jobs."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def validate_environment(env):
    secret = env.get("DJANGO_SECRET_KEY", "")
    if len(secret) < 50:
        raise ValueError("DJANGO_SECRET_KEY must be a random value of at least 50 characters.")
    if len(env.get("ADMIN_PASSWORD", "")) < 12:
        raise ValueError("ADMIN_PASSWORD must contain at least 12 characters.")
    hosts = [host.strip() for host in env.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
    if not hosts or "*" in hosts:
        raise ValueError("Set explicit DJANGO_ALLOWED_HOSTS; wildcard is not allowed.")
    if "127.0.0.1" not in hosts:
        raise ValueError("Include 127.0.0.1 in DJANGO_ALLOWED_HOSTS for healthchecks.")


def main():
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode not in ("web", "worker"):
        raise ValueError("Usage: python deploy/start.py web|worker")
    validate_environment(os.environ)
    os.environ["DJANGO_DEBUG"] = "False"
    for name in ("image_providers.yaml", "text_providers.yaml"):
        if not (ROOT / name).is_file():
            raise ValueError(f"Create {name} from its .example template before starting.")
    os.chdir(ROOT / "backend")
    if mode == "web":
        for command in ("migrate", "initadmin", "collectstatic"):
            args = [sys.executable, "manage.py", command]
            if command != "initadmin":
                args.append("--noinput")
            subprocess.run(args, check=True)
        # One process keeps generation coordination and configuration caches coherent.
        args = [sys.executable, "-m", "gunicorn", "config.wsgi:application",
                "--bind", "0.0.0.0:12398", "--workers", "1", "--threads", "8",
                "--timeout", "600", "--access-logfile", "-", "--error-logfile", "-",
                "--access-logformat", "%(h)s %(m)s %(U)s %(s)s"]
    else:
        args = [sys.executable, "manage.py", "process_images"]
    os.execv(sys.executable, args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f"Startup refused: {error}", file=sys.stderr)
        sys.exit(1)
