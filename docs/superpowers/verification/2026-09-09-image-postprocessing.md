# Image Postprocessing Verification

Date: 2026-09-09

## Executed

- Frontend: 253 tests in 20 files passed.
- Backend: 67 tests run, 66 passed and 1 skipped for Windows symlink privileges. Mock containment tests passed.
- Real bundled image processor exercised against synthetic images in temporary test storage; no model calls.
- Frontend application and test typechecks passed.
- Vite production build passed.
- Django migration consistency: no changes detected.
- Local migrations `postprocessing.0001_initial` and `0002_imagepage_published_revision` applied.
- Local hidden worker started and restarted after final backend edits; errors log empty before restart.
- Docker Compose configuration validated.
- Git diff whitespace check passed (Windows LF/CRLF warnings only).

## Browser

Separate ephemeral dev-preview tab, not the user's live account:

- Single image queued and completed; switched to publication copy and returned with processed output available.
- Desktop original/processed comparison rendered both images.
- Batch processing skipped existing result and completed remaining two pages.
- Mobile 390x844 comparison displayed one image at a time; no horizontal overflow, images loaded.
- Single-image download defaulted processed and submitted one existing image to browser.
- Whole-work download defaulted processed, listed missing pages and blocked until explicit partial confirmation.
- Both-version choice retained missing-page confirmation and separate output selection.
- Browser console contained no errors.
- Viewport override reset.

## Deployment Limitation

`docker compose build` failed fetching `node:22-slim` and `python:3.11-slim` metadata from Docker Hub due to network timeout. Docker container build and worker execution remain unverified. No proxy, firewall or DNS settings changed.

Compose now includes `image-worker`, shared history/database volumes and healthy-Web dependency. The image includes the processing script, NumPy and ExifTool.

## Operational Notes

- Start worker after reboot using `.venv\Scripts\python.exe backend/manage.py process_images`; local hidden process is not an installed Windows service.
- Local application entry: `http://127.0.0.1:5173/`.
- Processing persists per account/record; refreshing the mock development page intentionally resets synthetic fixture state.
- Old download helper remains unused for source compatibility; active views no longer import or invoke it.
- Superseded processed files remain until record deletion; only one current result is exposed.
- Read-only polling hashes current image sources/outputs for stale-source safety; large works incur disk I/O.
- No claim is made that postprocessing prevents AI detection or changes an image's provenance.
