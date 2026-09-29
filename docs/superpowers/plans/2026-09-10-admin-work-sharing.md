# Admin Work Sharing Implementation Plan

> **For agentic workers:** Use subagent-driven task execution with disjoint backend/frontend ownership and main-agent integration review.

**Goal:** Administrators share their own works with selected accounts for read-only use.

**Architecture:** HistoryRecord recipient grants and central read/write permissions protect every resource route. The works page separates shared records from the existing list and uses independent read-only preview state.

**Tech Stack:** Existing Django/SQLite, Vue/Pinia, TypeScript/Vitest.

## Global Constraints

Follow the approved `docs/superpowers/specs/2026-09-10-admin-work-sharing-design.md`.
Preserve dirty changes and real data. No paid model calls, live grant changes, or exposed credentials.
Shared recipients may read/download, never edit/generate/process/reshare.

## Task 1: Backend Grants And Permissions

Files: backend/history/{models,permissions,sharing,services,views,urls}.py,
history/migrations and test_sharing.py; targeted generation/views.py and
postprocessing/services.py/views.py authorization.

- [x] Write backend tests for grant/revoke and recipient read/write isolation; run `manage.py test history.test_sharing` and confirm missing features fail.
- [x] Add `shared_users = models.ManyToManyField('accounts.User', blank=True, related_name='shared_history_records')`.
- [x] Implement permission helpers over authenticated user and record, distinguishing read, write, and owner-admin sharing. Never use the read helper to authorize mutations.
- [x] Add GET/PUT `/api/history/<id>/sharing`: GET `{success, user_ids: string[]}`; PUT `{user_ids: string[]}`; response same. Require administrator ownership; invalid users reject entire change.
- [x] Serialize `owner:{id,username}`, `can_edit:boolean`, `can_share:boolean`, `is_shared:boolean`, `shared_count:number` (count only for sharing owner). Existing record fields remain.
- [x] List and stats accept `source=shared` (default existing scope). List additionally accepts keyword and status with consistent pagination. Search accepts source/status. Shared source excludes own records and owner-demoted records.
- [x] Authorize details, existence, originals/thumbnails, processed state/images and ZIP downloads using read permissions. Require file membership in granted record.
- [x] Deny recipient history writes, generation/retry, processing writes, and synchronization writes. Use private no-store headers for protected reads.
- [x] Run backend history/generation/postprocessing regressions; prepare additive migration without applying until integration.

## Task 2: Frontend Controls And Isolated Preview

Files: frontend/src/api/history.ts, api/types.ts, views/HistoryView.vue,
components/history/{GalleryCard,ImageGalleryModal,WorkSharingDialog}.vue,
focused tests/history/*.test.ts.

- [x] Add typed API wrappers for above contract. Extend getHistoryList `(page,pageSize,status?,source?,keyword?)`, getHistoryStats `(source?)`.
- [x] Add source selector "作品" / "共享给我" independent of existing status tabs. Preserve source, keyword and page when closing preview.
- [x] Add owner-only sharing control and indicator; recipient cards have preview/download only.
- [x] Implement sharing modal from listUsers with search and checkboxes; persist selections only on successful server response. Lock repeat save and fence stale responses.
- [x] Keep preview independent of generator state. Include publishing text, prefer processed images, remove edit action for recipients. Download version dialog remains reusable; no processing action for read-only records.
- [x] Clear state on account changes and refresh permissions on reactivation. Handle revoked/deleted records visibly without modifying in-progress draft.
- [x] Add UI tests for shared source query, read-only controls, modal save failure, account changes and return state; run tests before and after implementation.

## Task 3: Preview And Integration Verification

Files: frontend/tests/preview/fixtures.ts and preview sharing tests;
docs/superpowers/verification/2026-09-10-admin-work-sharing.md.

- [x] Extend isolated preview fixture grants, capabilities, recipient identity, list filtering and deny unauthorized mutations. No real config access.
- [x] Review both permission boundaries and UI integration; test source file membership and cancellation of stale preview requests.
- [x] Run `npm test`, `npm run typecheck`, `npm run test:typecheck`, `npm run build`.
- [x] Run `.venv/Scripts/python.exe backend/manage.py test history.test_sharing history.tests generation postprocessing library providers prompts` (explicit labels avoid the root history data directory).
- [x] Run migration consistency check, apply additive migration, verify served production bundle.
- [x] Browser verify administrator sharing and recipient preview/download availability at desktop/mobile widths using isolated fixtures; verify revoke denial, return state and no horizontal overflow.
- [x] Record actual evidence and limitations. Do not claim physical touch or cloud deployment testing.
