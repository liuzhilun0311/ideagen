# Independent Modules Implementation Plan

**Goal:** Preserve creation during independent module navigation and make copy generation directly discoverable.

**Architecture:** Existing route components remain cached; a nonpersistent session store exposes live busy state, replacement revision and notices. History loading never replaces an active operation.

**Tech Stack:** Existing Vue 3, Pinia, Vue Router, Vitest and Vite.

## Progress

- [x] Task 1: Retained creation, independent module routes, live ownership and completion notices.
- [x] Task 2: Top copy/image actions and an in-editor copy command; first-viewport visibility checked at all five widths.
- [x] Task 3: Guarded history replacement and independent stateful preview fixtures.
- [x] Task 4: Final review closed; 181 tests, both typechecks, build and browser checks passed. Evidence in `../verification/2026-09-09-independent-modules.md`.

Original implementation steps below remain as the detailed scope checklist.

## Constraints

Preserve original Docker/YAML changes. No real providers, account changes, or secrets. No new dependencies. Keep administrator-only users. One active creation at a time.

## Task 1: Session And Navigation

Files: `src/stores/studioSession.ts`, `src/App.vue`, `src/views/HomeView.vue`, `src/views/WorkspaceView.vue`, `src/composables/{useStudio,useDraftSave}.ts`, tests under `tests/studio/`.

- [ ] Add a nonpersistent session with `homeBusy`, `workspaceBusy`, `dirty`, `revision`, `notice`, getter `busy`, and `replaceDraft()` incrementing revision only when idle.
- [ ] Test busy ownership and replacement with independent Pinia instances before implementing.
- [ ] Cache WorkspaceView. Remove management-route exit blocks, retaining login/unload guards at the application level.
- [ ] Return creation nav to `/workspace` whenever outline pages exist, otherwise `/`.
- [ ] Track operation state synchronously; keep cancellation locks. Reload model options on idle reactivation, never while a request owns the draft.
- [ ] Reset editor selection and save baseline on explicit draft replacement.
- [ ] Announce completion while away without router pushes.

## Task 2: Visible Generation Actions

Files: `src/views/WorkspaceView.vue`, `src/components/workspace/GenerationPanel.vue`.

- [ ] Add parallel top actions with `studio.run('content')` and `studio.run('images')`; copy action selects the copy editor first.
- [ ] Use identical busy/model validation to the existing generation panel.
- [ ] Keep copy action within the copy editor and expose cancellation near top actions.
- [ ] Test responsive visibility at 390px and 1440px with real browser screenshots.

## Task 3: Works And Preview Isolation

Files: `src/views/HistoryView.vue`, optional `src/composables/useHistoryDraft.ts`, `tests/preview/{main,fixtures}.ts`, and focused tests.

- [ ] Guard history replacement before and after asynchronous retrieval. Reject if busy or revision changed; confirm replacing an existing draft; clone payload rather than alias API data.
- [ ] Protect deletion of the active record and avoid automatic history scans during live creation.
- [ ] Keep gallery browsing separate from the generator.
- [ ] Provide stateful preview prompts, providers, users and works with correct response shapes, explicit mock identity, and no real API fallthrough.
- [ ] Use cancellable delayed preview responses to exercise navigation while generating.

## Task 4: Verification

- [ ] `npm test`, `npm run typecheck`, `npm run test:typecheck`, `npm run build`, and `git diff --check`.
- [ ] Browser: start delayed generation, visit works/prompts/models/users, remain in chosen module on completion, return to creation with content intact.
- [ ] Browser: mobile menu works and primary copy action is visible without advanced settings.
- [ ] Independent review, resolve material findings, record remaining limits and commit only scoped changes.
