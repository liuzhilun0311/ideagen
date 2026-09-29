"""Run the bundled local script against isolated inputs, never provider APIs."""
import os
import subprocess
import sys

from django.conf import settings


def process_image(source, output, strength):
    script = settings.PROJECT_ROOT / 'deai-image' / 'scripts' / 'deai.py'
    subprocess.run(
        [sys.executable, str(script), str(source), '--strength', strength, '-o', str(output), '--quiet'],
        check=True,
        timeout=settings.POSTPROCESSING_TIMEOUT_SECONDS,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
