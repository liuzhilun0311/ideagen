# Generation Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Record and expose a safe, per-request audit trail for image generation so users can compare submitted prompts and parameters with relay billing.

**Architecture:** Add a local JSONL diagnostic sink owned by the image-generation service. Each actual upstream attempt records a redacted request snapshot, reference-image metadata, response status, retry number, duration, and optional upstream request/usage fields. Expose read-only diagnostics through the existing authenticated candidate/workspace APIs and a frontend dialog with copy/export, never storing authorization headers or raw secrets.

**Tech Stack:** Django 5.2, existing JSON/HTTP clients, Vue 3 + TypeScript, Vitest.

## Global Constraints

- No paid upstream model call is made by tests.
- API keys, Authorization headers, signed URLs, and raw base64 image data are never persisted or returned.
- Existing image generation behavior and user-owned prompt storage remain unchanged.
- Diagnostic writes are best-effort and must never make a successful generation fail.
- Existing records without diagnostics display an explicit “未记录” state.

---

### Task 1: Capture Redacted Upstream Attempts

**Files:**
- Create: `backend/generation/diagnostics.py`
- Modify: `backend/generation/generators/image_api_client.py`
- Modify: `backend/generation/generators/gpt_images.py`
- Test: `backend/generation/test_diagnostics.py`

**Interfaces:**
- `record_attempt(kind, payload)` writes one JSON line under `data/diagnostics/`.
- `redact_payload(payload)` removes secrets, base64 data, and signed URLs while retaining field names and sizes.
- HTTP clients call `record_attempt` once per actual POST attempt, including retry number, status, elapsed milliseconds, response request ID, and usage if present.

- [ ] **Step 1: Write failing redaction and attempt tests**
- [ ] **Step 2: Implement the diagnostics sink with atomic append and size limits**
- [ ] **Step 3: Instrument image API and GPT Images clients**
- [ ] **Step 4: Run `generation.test_diagnostics` without network access**
- [ ] **Step 5: Commit capture implementation**

### Task 2: Link Diagnostics to Image Requests

**Files:**
- Modify: `backend/generation/services/image.py`
- Modify: `backend/generation/candidates.py`
- Modify: `backend/history/models.py` only if a nullable diagnostic identifier is required
- Test: `backend/generation/test_diagnostics.py`

**Interfaces:**
- Every generation attempt includes `task_id`, `record_id`, page index, provider, model, selected resolution, and whether a cover/user reference was attached.
- Candidate generation keeps its existing immutable prompt record and adds a diagnostic lookup key without changing candidate response compatibility.

- [ ] **Step 1: Add correlation context to generator calls**
- [ ] **Step 2: Preserve correlation context across batch, retry, and candidate flows**
- [ ] **Step 3: Add tests for pure text-to-image versus reference-image request metadata**
- [ ] **Step 4: Run generation and candidate tests**
- [ ] **Step 5: Commit correlation implementation**

### Task 3: Add Authenticated Diagnostic API

**Files:**
- Modify: `backend/generation/views.py`
- Modify: `backend/generation/urls.py`
- Create or modify: `backend/generation/diagnostic_views.py`
- Test: `backend/generation/test_diagnostics.py`

**Interfaces:**
- `GET /api/generation-diagnostics/<task_id>` returns only the authenticated owner or authorized shared-user’s redacted records.
- Optional `record_id` and `page_index` query filters narrow the result.
- Response includes `request`, `prompt`, `parameters`, `references`, `response`, `retry`, and `timing`; raw secrets and image bytes are excluded.

- [ ] **Step 1: Write authenticated owner/shared-access API tests**
- [ ] **Step 2: Implement listing and filtering**
- [ ] **Step 3: Add URL registration and error handling**
- [ ] **Step 4: Run API tests and permission tests**
- [ ] **Step 5: Commit diagnostic API**

### Task 4: Add Frontend Diagnostic Viewer and Export

**Files:**
- Create: `frontend/src/api/diagnostics.ts`
- Create: `frontend/src/components/common/GenerationDiagnosticsDialog.vue`
- Modify: `frontend/src/components/workspace/PageStyleTrials.vue`
- Modify: `frontend/src/views/WorkspaceView.vue`
- Test: `frontend/tests/studio/diagnostics.test.ts`

**Interfaces:**
- A “查看本次生成参数” action opens the diagnostics dialog for the current task/page.
- The dialog shows request count, prompt, model, endpoint, dimensions, reference-image count/source, retries, status, duration, and upstream request ID/usage when available.
- Copy and download export JSON are local-only actions; exported content is already redacted.

- [ ] **Step 1: Write failing API/component tests**
- [ ] **Step 2: Implement API client and dialog states**
- [ ] **Step 3: Add entry points to candidate and current-image views**
- [ ] **Step 4: Run focused frontend tests and type checks**
- [ ] **Step 5: Commit frontend viewer**

### Task 5: Full Verification and Documentation

**Files:**
- Create: `docs/generation-diagnostics.md`
- Create: `docs/superpowers/verification/2026-09-11-generation-diagnostics.md`

- [ ] **Step 1: Run full backend tests from `backend`**
- [ ] **Step 2: Run frontend tests, type checks, and build**
- [ ] **Step 3: Verify migration check and `git diff --check`**
- [ ] **Step 4: Document billing-audit workflow and limitations**
- [ ] **Step 5: Commit verification evidence**
