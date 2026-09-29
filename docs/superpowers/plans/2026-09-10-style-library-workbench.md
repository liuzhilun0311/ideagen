# Style Library and Workbench Implementation Plan

**Goal:** Deliver the approved 30-style library, outline-time recommendations, final-choice prompt isolation, and a clearer responsive image workbench.

**Architecture:** A shared JSON catalog supplies backend directions and frontend presentation. Outline recommendations are separate metadata; automatic selection resolves to a concrete style for each work, while explicit selection wins. Candidate and adopted images remain separate states within one preview surface.

**Tech Stack:** Django, Vue 3, Pinia, TypeScript, Vitest.

## Constraints
- Preserve existing works, candidates, custom prompts and manual style choices.
- Back up current system prompt files before editing.
- No paid model requests during verification.
- Keep existing style IDs compatible; 30 concrete styles plus auto.
- A recommendation is not page text, image text or publishing copy.
- Do not stop unrelated processes or replace the fixed launcher address.

## Tasks
- [x] 1. Back up prompts; introduce a shared catalog with 30 concrete styles, scenarios, cautions and render directions.
- [x] 2. Add separate, validated outline recommendation metadata and concrete automatic resolution; test explicit override and legacy fallback.
- [x] 3. Improve the three prompts, separate final art direction from old visual directions, and test actual request composition.
- [x] 4. Add searchable, categorized style selection with recommendations and recent selections.
- [x] 5. Unify candidate/adopted preview workflow; add thumbnail selection, loading recovery, responsive settings and clearer states.
- [x] 6. Run backend/frontend tests and typechecks, build, inspect desktop/mobile browser rendering and verify port 12399 serves the updated build.

## Verification
Record commands and actual outcomes below after execution. Static style previews are illustrative, not proof of provider output quality.

- `pnpm test`: 375 passed in 29 files.
- `python backend/manage.py test history.test_sharing history.tests generation postprocessing library providers prompts`: 145 run, 144 passed, 1 skipped.
- `pnpm typecheck` and `pnpm test:typecheck`: exit 0.
- `pnpm build`: exit 0; production JS `index-CCEOFD-c.js`, CSS `index-HvT8i2ZZ.css`.
- `makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: exit 0; existing CRLF warnings only.
- Live port 12399 returns the verified bundle; launcher `start_web_server.ps1 -CheckOnly` succeeds.
- Browser checks used isolated development fixtures, not real accounts or provider calls: category/search selection, independent page style, candidate preservation, adoption, apply-to-set, remaining-only generation, and original/processed controls.
- At 390x844, drawer and nested style selector work; starting a trial closes the drawer and returns to the preview. Candidate image loaded; document scroll width 375 <= viewport width 390.
- At 1440x1000, desktop columns and main preview render, adopted image loads, document width 1425 <= viewport width 1440. Browser viewport override was reset.
- Stabilized a pre-existing timestamp-sensitive postprocessing test by explicitly setting old/new fixture modification times; no production postprocessing behavior changed.
- Prompt backups: `data/prompt-backups/2026-09-10-style-library/`. Custom prompts and real works untouched.
- Docker catalog COPY path updated for frontend compilation; a complete Docker image build was not run.
- Limitations: style thumbnails reuse labeled illustrative references, not 30 paid model-generated specimens. Actual provider typography, content accuracy and artistic quality still need user review.
