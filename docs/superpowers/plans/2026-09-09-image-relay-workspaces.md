# Image Relay and Workspace Implementation Plan

**Goal:** Make the documented image relay contract usable and separate image/copy page controls.

**Architecture:** A dedicated GPT Images adapter is selected by the existing image generator; existing provider types remain compatible. Two workspace routes share one controller and store to preserve task ownership.

**Tech Stack:** Django, requests, Pillow, Vue Router, Pinia, Vitest. No new dependencies.

## Constraints

No key output, no bulk paid generation, no unrelated Docker/YAML example changes. Only the existing relay image provider may be corrected. Preserve the successful Responses text path.

## Task 1: Image Adapter

- [x] Add `backend/generation/generators/gpt_images.py`, consumed by `ImageApiGenerator.generate_image`; retain the `generate_image(prompt,aspect_ratio,model,reference_images)` byte-returning boundary.
- [x] Add mocked tests in `backend/generation/test_gpt_images.py`. Assert generation has `size` and no `image_size/watermark/aspect_ratio`; references use `/edits` multipart with actual MIME types; wrong endpoints fail before network; non-image bodies never succeed; transient errors are not automatically resubmitted.
- [x] Implement and run `.venv\Scripts\python.exe backend/manage.py test generation providers`.
- [x] Update provider smoke test to reject Responses image configurations and return explicit connectivity-only warning for model-list checks.
- [x] Correct the existing relay image configuration with the application's structured save API, not text replacement; never print the key.

## Task 2: Independent Workspaces

- [x] Modify workspace route/view and generation panel to expose `/workspace` and `/workspace/copy`, sharing the controller but showing only relevant actions and settings.
- [x] Preserve KeepAlive ownership, route guards, page selection and unsaved draft. Copy view does not show image generation or page structure; image view does not show copy generation.
- [x] Add route and scoped-render regression coverage, then run `npm test`, `npm run typecheck`, `npm run test:typecheck`, `npm run build`.

## Task 3: Verification

- [x] Inspect desktop and 390px mobile previews, including navigation during a delayed generation.
- [ ] Real image generation remains blocked: the one synthetic test request returned HTTP 403. No image pixels exist to inspect. Stop retrying until the key/group permission is corrected.
- [x] Confirm running backend is new/reloading and both desktop/LAN proxies respond.
- [x] Record exact test outcomes and remaining limitations; keep user data out of verification artifacts.
