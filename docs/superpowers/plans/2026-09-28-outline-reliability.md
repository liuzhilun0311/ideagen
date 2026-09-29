# Outline Reliability Implementation Plan

**Goal:** Preserve existing work across failed/cancelled outline generation and make reference storage and prompt inspection reliable.

**Architecture:** Keep the current Vue/Pinia workflow. Capture normalized outline inputs in one shared function. Commit successful replacement only after validation. Store image blobs in IndexedDB with a matching manifest in the existing local draft; guard asynchronous restore/write operations against draft and account changes.

**Tech Stack:** Vue, Pinia, TypeScript, native IndexedDB, Django, Pillow, Vitest.

## Constraints
- Preserve unrelated working-tree changes; no commits or paid model requests.
- Keep the current page layout and requested button order.
- Reference limits: 5 images, 5 MiB each, JPEG/PNG/WebP; enforce on both client and server.
- Local drafts are not server backups. Surface storage errors and pending writes.

## Tasks
- [x] Normalize preview/generation input in `frontend/src/features/outlineRequest.ts`; test automatic structure/tone and custom reader validation.
- [x] Remove destructive pre-request reset in `HomeView.vue`; detach the old record only on successful home generation; test failure/cancel/late response.
- [x] Show cancel and cancellation failure states on the home page. Cancellation API now rejects missing acknowledgements and times out after 10 seconds.
- [x] Add IndexedDB reference storage and guarded lifecycle integration; persist all input settings and test recovery, stale reads, write errors and account boundaries.
- [x] Share reference limits across frontend validation and history encoding, and across backend outline/history validation; test size/count/type errors before provider calls.
- [x] Expose preview versus request-record modes in the prompt inspector, with immutable record prompts and shared normalized preview input.
- [x] Run frontend tests/typecheck/build, backend tests, and local fixture browser checks.

## Verification Commands
From `frontend`: bundled Node with `node_modules/vitest/vitest.mjs run`, `node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.test.json`, and `node_modules/vite/bin/vite.js build`.

From `backend`: `..\.venv\Scripts\python.exe manage.py test --verbosity 0`.

## Results
- Frontend: 53 files, 518 tests passed; typecheck passed; production build passed.
- Backend full suite: 328 tests, OK, 1 skipped. After the last validation-response refinement, 18 targeted tests passed.
- Native browser storage check: IndexedDB round trip, fresh-store image/text restoration, and image removal passed. Only synthetic isolated data was used.
- Browser fixture: generate/cancel retained the topic and restored controls; prompt preview/request-record switching and the empty state rendered correctly.
- HTTP 12399 returns 200 and serves `index-DR48GADR.js`.
- The build retains the pre-existing main chunk size warning.

## Boundaries
- No paid upstream calls were made. Cancellation acknowledgement cannot guarantee upstream billing stops.
- IndexedDB is a local browser draft, not a server backup. Storage failures and in-flight image writes are surfaced; server work saving remains explicit.
- An old work is retained when regeneration fails/cancels. Successful replacement still replaces the local result after confirmation; a general undo/version-history UI is outside this round.
- No general structured-editor or quality-check features were added in this round.
