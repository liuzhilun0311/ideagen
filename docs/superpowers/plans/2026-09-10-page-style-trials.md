# Page Style Trials Implementation Plan

**Goal:** Implement the approved single-page trial, explicit version adoption, and remaining-page generation workflow in the existing workspace.

**Architecture:** Persist immutable candidate files outside published image paths. Only adoption publishes an image and reconciles postprocessing. All generation paths use explicit style precedence over reference-image appearance and legacy outline art direction.

**Tech Stack:** Django, Vue, Pinia, existing image adapters and postprocessing.

## Approved Behavior
- Per-page trial style is independent of the set default.
- Successful trials remain candidates until adopted; failures leave adopted images unchanged.
- Candidates retain page content, style, and final prompt; stale-page candidates cannot be adopted.
- Applying a candidate's style to the set does not generate or replace images.
- Remaining generation runs sequentially for missing pages only; full replacement requires confirmation.
- Original/processed comparison always belongs to the adopted version.
- No paid model calls during development verification.

## Tasks
- [x] Strengthen preset-specific constraints and remove unconditional reference-style copying in the image adapter. Test assembled prompts.
- [x] Add candidate model/migration and owner-authorized list/generate/adopt/image endpoints. Store immutable files in candidate subdirectories, preserve previous adopted images, and validate content snapshots.
- [x] Add an inline trial panel with local style controls, candidate preview, adoption, set-style application, and actual submitted prompt disclosure.
- [x] Add remaining-page generation and confirmed full regeneration through candidates, preserving successful images on failure.
- [x] Verify permissions, publication isolation, stale versions, style forwarding, frontend type checks, regression suites, build, and served assets.

## Verification Commands
` .venv/Scripts/python.exe backend/manage.py test generation history.tests history.test_sharing postprocessing library providers prompts `

`npm test`, `npm run typecheck`, `npm run test:typecheck`, `npm run build` in frontend.

Inspect actual served bundle. Browser verification uses isolated fixtures and mocked generation only.

## Results
- Frontend: 364 tests passed; application and test type checks passed.
- Backend: 138 tests run, 137 passed, 1 skipped.
- Production build passed. Migration 0004 applied; no additional model migrations required.
- Desktop and 390px mobile browser checks passed: single-page trial, two retained styles, explicit adoption, set-style application, remaining-page generation. Mobile document width equals viewport width.
- User-uploaded reference images remain supported; old covers are not automatically injected into trials. Provider adapters no longer append conflicting reference-style instructions.
- Candidate publication integrates with postprocessing source revisions. Existing-image scan routines do not republish archived versions.
- The existing port 12398 process was serving stale backend routes with autoreload disabled. Automatic shutdown was blocked by execution policy; no workaround shutdown was attempted. A new autoreloading development server runs on port 12399. Its new candidate route was verified to require authentication.
- The idle image-processing worker was restarted with the updated code.
- No paid image-generation request was made. Model rendering quality is not asserted by mocked integration tests.
