# Admin Work Sharing Verification

Date: 2026-09-10

## Delivered Behavior

- Administrator owners select recipient accounts on their own work cards.
- Recipients use a separate shared source with independent status/search filters.
- Shared preview is read-only and isolated from the active creation draft.
- Preview prefers processed images; downloads retain version selection.
- Permissions cover record details, originals/thumbnails, processed files, and ZIP membership.
- Sharing does not grant editing, generation, processing, deletion, synchronization, or resharing.
- Revocation and owner demotion deny subsequent protected requests.
- Mobile work actions remain visible without hover.

## Automated Evidence

- `npm test`: 27 files, 342 tests passed.
- `npm run typecheck`: exit 0.
- `npm run test:typecheck`: exit 0.
- `npm run build`: exit 0; production entry `index-Cym1fx9J.js`.
- `.venv/Scripts/python.exe backend/manage.py test history.test_sharing history.tests generation postprocessing library providers prompts`: 117 tests, 116 passed, 1 skipped due to local permission conditions.
- `makemigrations --check --dry-run`: no changes detected.
- `migrate`: additive history migration 0002 applied successfully.
- `git diff --check`: exit 0; existing Windows line-ending warnings only.

Backend sharing coverage includes atomic grant validation, source-filtered reads,
file membership, mutation denial, owner-demotion/revocation, administrator
oversight, task binding, path validation, and concurrent SQLite saves.
Frontend coverage includes API contracts, shared controls, transient versus
authorization errors, sparse image page indices, stale responses, and draft isolation.

## Browser And Served Build

Isolated preview fixtures only; no real user grants were changed.

- Administrator selected an account in the sharing modal and saw the updated recipient count.
- Recipient saw an empty own list and the granted work under the shared source.
- Recipient controls exposed preview/download without edit/delete/share.
- Publishing copy was displayed and copied, with success feedback.
- Closing preview preserved the shared source.
- Download defaulted to processed images and allowed selecting originals; no processing shortcut appeared.
- Mobile viewport 390 x 844: image loaded, action buttons visible, download modal fit.
- Mobile document width 375 was within the 390-pixel viewport.
- Timed fixture revocation closed the preview, removed content and showed an unavailable-work message.
- Restored the browser's default desktop viewport after testing.
- Local production endpoint on port 12398 returned HTTP 200 with the exact current dist index.
- Current JS and CSS assets returned HTTP 200; health endpoint reported success.

## Limits

- No paid generation calls, physical-phone testing, or Docker/cloud deployment run.
- Browser fixtures use bundled images; backend tests verify actual protected image-route permissions.
- Already downloaded bytes and already-authorized in-flight reads cannot be revoked.
- Overlapping SQLite sharing writes preserve complete recipient sets; a competing locked request can fail and require retry. The dialog preserves selections after failure.
- No implementation commit was requested; unrelated workspace changes were preserved.
