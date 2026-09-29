# Model and Prompt Copy/Sort Verification

Date: 2026-09-10

## Delivered

- Models and prompts: copy beneath source, server-selected unique names, immediate editor, account/category-scoped persisted order, pointer drag and up/down controls.
- Model copies preserve server-side configuration including credentials; remain disabled, without shared users, and do not change the active model.
- Prompt copies support default and visible shared prompts. Renaming now validates and writes the replacement before removing the old identity, compensates on failure, and preserves order for owner/shared viewers.
- Refresh/copy/reorder responses are guarded against changed accounts, categories and cached-page navigation. Failed reorders roll back. Retry keys prevent duplicate creation after uncertain responses.
- Added HTTP LAN request-ID fallback, 44px mobile sorting/copy targets, and removed the obsolete 760px minimum-width rule that hid model actions on phones.
- Pinned TypeScript 5.9.3 to resolve the reproduced vue-tsc crash with installed TypeScript 5.3.2. Retained JSZip 3.10.1; enabled existing esbuild/vue-demi build hooks in pnpm workspace configuration.

## Executed Checks

- `npm test`: 24 files, 308 tests passed.
- `npm run typecheck`: passed.
- `npm run test:typecheck`: passed.
- `npm run build`: passed; final assets `index-Ca5u3P9Y.js` and `index-DNWShbOG.css`.
- `.venv\Scripts\python.exe backend/manage.py test library prompts providers postprocessing history generation`: 98 tests, OK, 1 skipped.
- `.venv\Scripts\python.exe backend/manage.py migrate`: library.0001_initial applied.
- `.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run`: no changes.
- `git diff --check`: passed (existing CRLF conversion warnings only).
- HTTP GET on port 12398: index and current JS bundle returned 200; bundle contains new copy control.

## Browser Checks

Isolated `dev-preview.html?screen=models` fixtures only, without real model/configuration requests:

- Desktop 1440x1000 and mobile-sized 390x844 screenshots inspected.
- Model copy appeared directly below source with distinct label and disabled state; its editor opened without exposing a key.
- Dragged model copy above source in desktop and mobile-sized layouts; order visibly updated.
- Copied default prompt, renamed the copy, saved, and moved it above default; original stayed present.
- Navigated models to prompts and back; retained order and active controls, including KeepAlive reentry.
- On mobile-sized model and prompt pages, document scroll width equaled 390px; model-list scroll width equaled client width.
- Mobile sorting handles measured 44x44px.
- Browser error log empty at final inspection; viewport override reset.

## Boundaries

- No real credentials/configuration contents were used or modified; no provider generation/test calls.
- Preview fixture state resets on full reload by design. Persistence and account isolation are covered by backend tests; live user-account mutations were not used for verification.
- Responsive browser pointer checks are not physical-phone touch hardware tests.
- This change does not claim a new Docker deployment test.
- Resource files and database updates have compensating rollback, not distributed transactions. Forced process termination and concurrent legacy provider-file edits retain the limitations documented in backend/library/README.md.
