# Image Postprocessing Implementation Plan

> Execute in bounded backend, workspace UI, and export tasks; review integrated changes and verify before completion.

**Goal:** Persist original/processed image versions, process independently of downloads, and default selectable downloads to processed images.

**Architecture:** A database-backed postprocessing worker owns jobs and immutable outputs. A record-scoped API exposes image versions and preferences. Frontend polling restores state across navigation; downloads only read existing files.

**Tech Stack:** Existing Django/SQLite, Pillow processing script, Vue/Pinia, Vite/Vitest, Docker Compose.

## Constraints

- Source: `docs/superpowers/specs/2026-09-09-image-postprocessing-design.md`.
- Preserve existing worktree edits and original image bytes; no paid model calls.
- Default strength light; automatic processing initially off; every download dialog defaults processed.
- Never silently substitute originals for missing processed images.

## Shared API Contract

`GET /api/postprocessing/<record_id>` returns:

```ts
interface ProcessingState {
  success: boolean
  preferences: { automatic: boolean; strength: 'light' | 'medium' | 'heavy' }
  pages: {
    index: number
    source_revision: string
    original_url: string
    processed_url: string | null
    strength: 'light' | 'medium' | 'heavy' | null
    status: 'idle' | 'queued' | 'processing' | 'done' | 'error'
    error: string
    adopted: 'original' | 'processed'
  }[]
}
```

`POST /api/postprocessing/<record_id>` accepts one of:

```json
{"action":"process","indices":[0,1],"strength":"light","force":false}
{"action":"preferences","automatic":true,"strength":"light"}
{"action":"adopt","index":0,"version":"processed","source_revision":"sha256"}
```

All mutations return fresh ProcessingState. Missing/forbidden records fail without revealing paths. Processed URL is an authenticated same-origin `/api/postprocessing/images/...` endpoint. Source changes invalidate previous processed results. GET reconciles available originals but automatic enqueue must also occur server-side on generation publication.

## Task 1: Backend Jobs and Versions

Files: new `backend/postprocessing/` app, migrations, API, services, worker management command and tests; focused integrations in settings/URLs and history synchronization.

- [x] Write failing tests for owner isolation, source immutability, idempotent enqueue, strength changes, adoption, source invalidation, stale workers and partial failure.
- [x] Run `.venv\Scripts\python.exe backend/manage.py test postprocessing`.
- [x] Implement persisted state with atomic job claim, bounded leases/retries, isolated input copies and validated atomic publication.
- [x] Integrate server-side automatic enqueue after history image publication; old records restore as originals.
- [x] Run backend tests and migration consistency check.

## Task 2: Workspace Versions

Files: new API/composable and workspace image-version components; `WorkspaceView.vue`, `PageEditor.vue`; focused tests.

- [x] Write Vitest tests for state restoration, record switching, partial failures and no late mutations.
- [x] Implement API types matching the contract, poll only the current record, clear stale state on record change.
- [x] Add original/processed/compare views, explicit adoption and per-page processing strength.
- [x] Add one batch toolbar with pending count, explicit force confirmation and automatic preference.
- [x] Preserve generation actions and page navigation; processing must not set generation busy flags.
- [x] Run frontend test and typecheck scripts.

## Task 3: Preview and Download

Files: download dialog/helper, `ResultView.vue`, `HistoryView.vue`, authenticated image URL utilities and tests.

- [x] Test default processed selection, originals/both output, missing result confirmation and no processing API calls from download.
- [x] Use adopted versions in preview/thumbnail; direct preview copy targets viewed image.
- [x] Add shared single/all download dialog with original/processed/both choices and explicit partial confirmation.
- [x] ZIP export only fetches available selected versions; separate folders for both, stable page names, HTTP/file validation and accurate failure reporting. Single files download directly; multi-file export uses ZIP consistently on desktop/mobile.
- [x] Remove download-time DeAI execution and BAT artifacts from active flows.

## Task 4: Deployment and Verification

- [x] Add worker service sharing database/image mounts and starting only after migrations; preserve existing Compose edits.
- [x] Apply additive migrations; start local worker hidden; verify synthetic real processing without provider calls.
- [x] Run backend regression tests, frontend `npm test`, `npm run typecheck`, `npm run test:typecheck`, `npm run build`.
- [x] Verify mock UI through browser on desktop and 390px mobile including version comparison, preview, download selection and navigation.
- [x] Check Docker configuration.
- [ ] Actual Docker build/worker integration: Docker Hub base-image connection timed out; no container runtime claim.
- [x] Review diff and record results, remaining risks and local entry URL.
