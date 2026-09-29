# Workspace Audit Fixes

**Goal:** Close the confirmed interaction, persistence, and regression gaps.

**Architecture:** Preserve the current Vue/Pinia and Django interfaces. Use an
atomic structure update with an optimistic outline check. Centralize selected
title resolution for publication, restoration, and export.

## Scope
- [x] Add transactional structure changes; reject stale or busy records; retain
  local state on failure and prevent duplicate submissions.
- [x] Normalize selected titles, restore both history paths, and use the selected
  title for preview, copy, and export. Keep alternate titles editable.
- [x] Remove unreachable audit UI and legacy download helpers after checking
  references. Retain backend diagnostic APIs for compatibility.
- [x] Update outdated assertions against approved behavior, add regression cases,
  and investigate model-copy test failures without weakening assertions.
- [x] Verify full frontend/backend tests, typecheck, migrations, production build,
  and desktop/mobile fixture screenshots without calling paid models.

## Verification
Run `pnpm test`, `pnpm run typecheck`, `pnpm run test:typecheck`, and
`pnpm run build` from `frontend`; run `manage.py test`, `manage.py check`,
`manage.py makemigrations --check --dry-run`, and `manage.py migrate --check`
with the workspace virtual environment. Use the existing isolated preview
fixtures for browser checks, not the user's live drafts.
