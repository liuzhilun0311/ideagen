# Model and Prompt Copy/Sort Implementation Plan

**Goal:** Create editable copies directly below their source and persist account-scoped list ordering.

**Architecture:** Shared database-backed ordering records store revisioned resource IDs. A resource-library API copies authorized source data server-side and updates order; UI uses common pointer/keyboard reorder controls.

**Tech Stack:** Existing Django/SQLite, Vue/Pinia, TypeScript/Vitest. No new runtime library.

## Constraints

Follow `docs/superpowers/specs/2026-09-10-copy-sort-models-prompts-design.md`.
Preserve dirty worktree and real configurations. Tests use temporary files and fake credentials. Never call providers.

## API Contract

New endpoints:

- `GET /api/library/<resource>/<kind>` where resource is `models` or `prompts`; kinds text/image for models and outline/content/image for prompts.
- Response `{success:true, revision:number, order:string[]}` listing all visible stable IDs in effective order.
- `POST /api/library/<resource>/<kind>/reorder` with `{revision, order}`; same response; exact visible set required, reject stale revision with 409.
- `POST /api/library/<resource>/<kind>/copy` with `{source:string, revision:number, request_id:string}`.
- Copy response `{success:true, revision, order, created:{id:string,name:string}}`; idempotency key avoids duplicate on retry. Models created.name is internal provider key; prompt created.name is display name.
- Model ID is existing provider map key.
- Prompt ID is JSON.stringify([is_base ? "base" : (owner_id || ""), name]); Python json.dumps(..., ensure_ascii=False, separators=(',', ':')).
- List order GET never exposes credentials or content. Copy reads from authorized backend source.
- Creation requests bind revision, account, resource, kind and source. Copy is atomic with order where possible; file write failures must not leave a falsely successful response.

## Task 1: Backend Resource Library

Files: new `backend/library/` models/services/views/urls/migrations/tests; config settings/urls; focused provider and prompt serialization integrations.

- [x] Add tests covering revision conflicts, owner scope, empty lists, duplicate IDs, copy naming, default/foreign prompt copy, stable model keys, key non-disclosure, disabled copies and empty sharing.
- [x] Implement revisioned account resource order and copy requests with idempotency.
- [x] Integrate effective order into existing getConfig/getPrompts responses without recursive service calls.
- [x] Verify `.venv\Scripts\python.exe backend/manage.py test library providers prompts`.

## Task 2: Shared UI Interaction and Model Integration

Files: new `frontend/src/api/library.ts`, `composables/useLibraryOrder.ts`, `components/common/ReorderControls.vue`; model SettingsView/ProviderTable/useProviderForm; tests.

- [x] Expose `libraryItemId(item)` for prompt IDs and library API methods matching contract.
- [x] Add pointer drag handle with touch-action:none only on handle; up/down buttons accessible with labels. Detect target by row DOM data attribute, preserve all other controls.
- [x] Disable repeat copy/reorder while pending. Optimistically reorder then rollback on failure. Ignore responses after account/category change.
- [x] Copy model via server, refresh and open created row in edit modal; report separately if created but refresh fails.
- [x] Test pointer move, button move, ownership, failed-save rollback and copy refresh.

## Task 3: Prompt Integration

Files: PromptManageView and focused tests.

- [x] Use shared ordering and stable IDs including owner identity.
- [x] Offer copy for all visible entries, including system default. Successful copy opens edit and is directly below source.
- [x] Allow server-backed same-kind sorting and preserve expanded/editor state.
- [x] Prevent late response changing active category or signed-in user.

## Task 4: Integration and Verification

- [x] Add dev-preview fixture API for mock copy/reorder; never contact live provider config from previews.
- [x] Run additive migrations and confirm production bundle serves new UI.
- [x] Run backend tests, frontend tests, app/test typechecks and build.
- [x] Use browser to test copy placement and editing, drag/up/down, reload behavior, desktop/mobile overflow and touch handles. Persistence verified through backend tests; mobile checks use a resized browser, not physical touch hardware.
- [x] Record actual verification and remaining limitations in `docs/superpowers/verification/2026-09-10-copy-sort-models-prompts.md`.
