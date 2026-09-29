# Project Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the confirmed cross-module regressions, reduce avoidable frontend startup cost, and publish an honest verification status before packaging the shared platform-expression skill.

**Architecture:** Keep the existing history transaction and page-shape contract, extending its accepted page types from the already-supported frontend/backend generation set. Scope the download test to the intended control, lazy-load management-only routes without changing route names or guards, and record verified versus unverified behavior in one current status document. The platform risk-expression feature remains prompt-only and is explicitly tracked as not implemented in this remediation.

**Tech Stack:** Django, Django TestCase, Vue 3, Vue Router 4, TypeScript, Vitest, Vite, Docker Compose.

## Global Constraints

- Preserve unrelated user changes in the dirty worktree.
- Do not rewrite generated copy after generation; platform-risk guidance may only enter prompts.
- Accept the existing page types `cover`, `content`, `summary`, and `infographic` consistently.
- Do not run destructive Docker commands against project volumes.
- Do not claim Docker or upstream provider calls are verified when the local Docker daemon or credentials are unavailable.

### Task 1: Protect infographic structure edits

**Files:**
- Modify: `backend/history/views.py`
- Test: `backend/history/test_structure_change.py`

**Interfaces:**
- The `PUT /api/history/<record_id>` `structure_change` endpoint continues returning `200`, `400`, `403`, or `409` with its existing response shape.
- A valid page has an integer index matching its position, a supported type, and string content.

- [x] **Step 1: Add a regression test for a valid infographic page**

Add a test that submits a one-page `infographic` outline and asserts `200`, then verifies the saved outline.

- [x] **Step 2: Add validation tests for malformed index/type values**

Assert that an unsupported type and a boolean index are rejected with `400`; Python booleans must not be accepted as integer page indexes.

- [x] **Step 3: Run the focused tests and confirm the new tests fail before the fix**

Run `python manage.py test history.test_structure_change`.
Expected before implementation: the infographic case is rejected with `400`; malformed-index behavior demonstrates the current validation gap.

- [x] **Step 4: Make the smallest validation change**

Use the shared four-value page-type contract and require `type(page.get('index')) is int` before comparing the index to `enumerate`.

- [x] **Step 5: Run the focused tests**

Run `python manage.py test history.test_structure_change`.
Expected: all structure-change tests pass.

### Task 2: Scope the download dialog assertion

**Files:**
- Modify: `frontend/tests/history/sharing.test.ts`

**Interfaces:**
- The test checks `#download-version` for `processed`, `original`, and `both`.
- The separate `#download-format` control remains covered by the postprocessing tests.

- [x] **Step 1: Replace the global option query**

Use the existing renderer helpers to find `select#download-version`, collect its descendant options, and assert the three version values.

- [x] **Step 2: Run the focused Vitest file**

Run `pnpm exec vitest run tests/history/sharing.test.ts`.
Expected: the sharing/history tests pass without removing the directory/ZIP format feature.

### Task 3: Reduce initial route bundle cost

**Files:**
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Keep all existing route names, paths, redirects, guards, and component behavior.
- Keep `WorkspaceView` as the shared synchronous component for `/workspace` and `/workspace/copy`.
- Load settings, prompt management, reference assets, and admin users with dynamic imports.

- [x] **Step 1: Convert management view imports to lazy route components**

Remove only the four eager management imports and use `() => import(...)` at their route definitions.

- [x] **Step 2: Run router-related and full frontend tests**

Run `pnpm test`.
Expected: all frontend tests pass.

- [x] **Step 3: Run typecheck and production build**

Run `pnpm run typecheck`, then `pnpm run build`.
Expected: both pass; build output contains separate management chunks and no new fatal warning.

### Task 4: Publish current audit status

**Files:**
- Create: `docs/project-status-2026-09-29.md`
- Modify: `README.md`

**Interfaces:**
- The status document distinguishes implemented and test-verified behavior, browser mock-preview coverage, unavailable Docker verification, unpaid-provider gaps, and the implemented prompt-only platform-risk guidance.

- [x] **Step 1: Record exact verification commands and outcomes**

Include backend test count, frontend test result, typecheck/build result, `git diff --check`, deploy-check warnings, and Docker daemon availability as observed during this audit.

- [x] **Step 2: Record residual risks and deferred work**

Explicitly list stable page IDs, cross-device revision conflict handling, durable multi-worker cancellation, real provider calls, full browser interaction coverage, and platform-specific prompt rules as follow-up items.

- [x] **Step 3: Link the status document from the README**

Add one concise project-status link near the existing development/deployment documentation.

- [x] **Step 4: Run final validation**

Run the backend suite, frontend suite, typecheck, build, and `git diff --check`; report any unavailable environment checks instead of substituting assumptions.

## Self-Review

- The plan covers the confirmed backend compatibility defect, the frontend test defect, the low-risk bundle optimization, and the audit-status requirement.
- Platform-risk-expression guidance is now implemented separately through the shared generation context and its focused tests; it remains intentionally prompt-only.
- No task changes data models, deletes legacy views, resets user data, or changes provider protocols.
