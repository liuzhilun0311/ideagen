# Workspace Audit Verification

Date: 2026-09-27

## Changes
- Structure edits commit the new outline and detach old task/image associations
  together. Failures preserve local images and pages. Repeated submissions are
  blocked, and stale outlines or active candidate/processing jobs are rejected.
- Selected-title resolution is shared by publication copy and exports. Both
  history restoration paths preserve selection. Preview marks the chosen title.
- Title radio buttons have accessible names and remain aligned with their text
  fields and individual copy buttons.
- Mobile page settings now contain actual controls. Generation can be stopped
  after switching between image and copy workspaces.
- Removed unused frontend audit/consistency panels and legacy download helpers.
  Backend compatibility endpoints remain.
- Image base-template validation now accepts the supported growth_rules variable.
- Applied the pending medium-default migration after a SQLite backup. Existing
  saved preferences remain unchanged.

## Results
- Frontend: 41 test files, 440 tests passed.
- Backend: 267 tests run, 266 passed, 1 skipped.
- Production and test TypeScript checks passed.
- Vite production build passed; a 502.40 kB main-bundle size warning remains.
- No missing model migrations; applied migration check passed.
- Git diff whitespace check passed (existing CRLF conversion notices remain).
- Isolated browser fixture checks passed at 1440px and 390px: title alignment,
  selected radio, horizontal overflow, and mobile settings controls.
- Screenshots inspected in frontend/test-results/workspace-audit.
- The existing server at http://127.0.0.1:12399 returned the new built asset
  index-Bpzh6CRk.js and passed the launcher readiness check.

## Limits
- Browser checks used synthetic, ephemeral fixtures, not the user's live draft.
- No paid model requests were issued. Model output quality, upstream service
  availability, and semantic agreement of newly generated images/copy were not
  verified by this regression pass.
- Backup: data/db-before-medium-default-20260927-124957.sqlite3.
