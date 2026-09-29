# Prompt Options Repair Implementation Plan

**Goal:** Repair the approved prompt-options audit across outline, copy, image, history, and diagnostics.

**Architecture:** Preserve requested preferences separately from resolved preferences. Share prompt builders across preview and execution. Store creation inputs with each work, and reject unsupported provider options instead of silently ignoring them.

**Tech Stack:** Vue, Pinia, TypeScript, Django, existing provider adapters, Vitest and Django tests.

## Constraints

- Preserve existing dirty-worktree changes and administrator-authored templates.
- No paid model calls or secrets in diagnostics.
- Migrate only known built-in template fragments.
- Existing saved works remain readable; missing original inputs are explicitly unavailable.
- Do not equate prompt coverage with model-output verification.

## Tasks

- [x] 1. Preserve current reference roles and manual copy preferences; persist requested and effective outline preferences; test regeneration and auto recommendations.
- [x] 2. Share platform-aware context across image previews/candidates; remove provider-added creative instructions; support all Google references; test actual payloads.
- [x] 3. Migrate the built-in copy role; strengthen platform/goal-specific rules, material boundaries, selected emoji policy and page-count priorities; test prompt composition and output validation.
- [x] 4. Normalize image parameters at the adapter boundary; update cached attributes; reject unsupported controls; preserve requested output encodings and record actual image metadata.
- [x] 5. Save and restore a versioned creation snapshot with material, models, parameters and requested options; carry references through legacy retries.
- [x] 6. Make usage diagnostics reflect compilation rather than claimed result compliance; add end-to-end path regressions.
- [x] 7. Run backend/frontend suites, type checks and production build; migrate local templates and verify the serving app.

## Completed Verification

- Backend: 318 tests, no failures, one platform-dependent skip.
- Frontend: 464 tests across 45 files passed.
- Application and test TypeScript checks passed; production build passed.
- Applied `prompts.0004_platform_neutral_copy` and `generation.0002_contentrun`.
- Serving app on port 12399 returns bundle `index-CM3fjLs6.js` with `Cache-Control: no-cache`.
- Browser: desktop/mobile parameter layout, copy option selection/preview, and always-open copy diagnostics empty state checked in isolated development fixtures.
- Added independent content diagnostics after discovering the copy page incorrectly read image-task events.
- No paid model calls; semantic adherence is not claimed by local test results.

## Verification

Use `backend/manage.py test` for generation, prompts, history, and providers. Run `frontend/node_modules/vitest/vitest.mjs run`, `vue-tsc --noEmit` for both application and test configurations, and `vite build`. Add focused regression tests before fixes; use mocked transports, never upstream credentials. Inspect production HTTP and browser state after rebuilding.

## Acceptance

Every supported choice has one effective value and a traceable prompt or request field. Unsupported choices fail before network calls. Previews reflect the same material roles and effective settings used by requests. Repeat generation preserves manual choices. Historical works restore their own settings rather than inheriting another work's settings.
