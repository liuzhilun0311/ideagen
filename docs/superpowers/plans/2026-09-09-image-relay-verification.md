# Image Relay Verification

Date: 2026-09-09

## Backend

- Initial regression run failed because `generation.generators.gpt_images` did not exist.
- After implementation: `manage.py test generation providers --verbosity 1`: 32 tests passed.
- Tests cover generation payload, multipart reference editing, actual image decoding, URL downloads without credentials, wrong endpoint rejection, HTTP/transport errors, and connectivity-only warnings.
- Review identified a DNS re-resolution risk in URL downloads. The fixed downloader connects to a validated numeric IP while preserving TLS hostname validation, with no redirects or environment proxy. A changing-DNS regression test passes; reviewer confirmed the finding closed.
- Existing shared relay image configuration corrected using `save_single_provider`, preserving credentials and other providers.
- One real synthetic 1024x1024 generation was attempted through `ImageApiGenerator`: upstream returned HTTP 403. No output image was produced and the request was not retried. Real generation remains unverified pending relay permission.

## Frontend

- Final combined run: `npm test`: 209 tests passed across 15 files.
- `npm run typecheck` and `npm run test:typecheck`: exit 0.
- `npm run build` and `git diff --check`: exit 0.
- Browser preview: image and copy pages expose only their relevant controls, and copy text survives navigation.
- During a delayed mocked image request, navigating to copy did not stop the task or erase text; image results completed after returning.
- Desktop and 390x844 mobile layouts inspected. Mobile document and scroll width both 390.
- Preview image results are mock fixtures, not evidence of real provider access.
- Retained outline replanning in a collapsed image-page-only section, disabled after images exist. Cancellation labels identify the running task even after navigation.

## Runtime

The original server used `--noreload` and predated Responses implementation.
It was restarted with the normal Django development reloader before this image task.
Never equate a fresh command-line invocation with the previously running server's loaded code.
Desktop and LAN proxy health checks both returned success after implementation.
