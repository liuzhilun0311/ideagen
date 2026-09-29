# Outline Diagnostics Implementation Plan

**Goal:** Let the owner inspect outline requests, responses, and failures independently of image tasks.

**Approved Design:** Bind diagnostics to OutlineRun IDs. Reuse redacted JSONL transport capture under an outline-specific namespace, and provide an owner-only no-store endpoint. Keep failed record IDs in the draft without relabeling a previous successful outline. Show explicit unavailable-response information for old records.

**Tech Stack:** Django, requests, Vue, Pinia, Vitest.

## Constraints

- Preserve provider settings and unrelated working tree changes.
- Never record authorization headers, API keys, or reference image base64.
- Keep authentication and record ownership checks before reading diagnostic files.
- No schema migration: use the existing OutlineRun and diagnostic file store.
- Keep image and copy diagnostic behavior unchanged.

## Work

- [x] Capture local outline lifecycle and upstream text transport events, including failed attempts.
- [x] Add a record-owned API with legacy snapshot fallback and no-store responses.
- [x] Persist failed diagnostic record IDs separately from successful outline provenance.
- [x] Replace the home button with a record-based dialog, including record selection, loading, errors, refresh, and legacy empty states.
- [x] Test transport redaction, success/failure, ownership, legacy records, frontend persistence and dialog interaction.
- [x] Run backend/frontend regression suites, type checks, build, and browser verification.

## Verification

- Backend: `python backend/manage.py test generation providers --verbosity 0`, 153 passed.
- Frontend: `pnpm test`, 455 passed across 43 files.
- `pnpm run typecheck` and `pnpm run test:typecheck`: passed.
- `pnpm run build`: passed; existing bundle-size advisory remains.
- Playwright using installed Edge, isolated preview data: empty state, record lookup,
  request/response rendering, refresh and close passed without browser errors.
- Screenshots checked at 1440x1000 and 390x844; dialog scrollWidth equals clientWidth.
- Running application on port 12399 serves the updated build. The diagnostics route
  rejects unauthenticated access with HTTP 401 and private, no-store headers.
- No live model calls or changes to provider settings were needed for this task.

## Follow-Up: Disabled Entry

- Removed the read-only outline diagnostics button's disabled condition entirely.
- During generation/cancellation, opening the dialog selects the latest server record
  instead of pinning a previous outline.
- HTML entry responses now use `Cache-Control: no-cache`; already-open tabs still need
  a refresh to load the new bundle.
- Regressions reproduced disabled buttons during generation/cancellation and missing
  cache headers before the changes.
- Latest verification: 458 frontend tests and 4 deployment/static tests passed; both
  type checks and production build passed.
- Browser click with no image task or outline record visibly opened the dialog.
- Port 12399 verified serving `index-iH70HdLD.js` with the new cache header.
