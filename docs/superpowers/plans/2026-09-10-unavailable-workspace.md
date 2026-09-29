# Unavailable Workspace Recovery

**Goal:** Returning from works to creation must not trap a locally preserved draft on a deleted record.

**Architecture:** Keep text and configuration untouched on read failures. Stop automatic processing polling after definitive authentication/resource errors. Render an explicit recovery action in the workspace for 403/404, then detach obsolete record/task/image state only after the user clicks it. Transient failures never trigger detachment.

**Tech Stack:** Existing Vue, Pinia, Vitest.

- [x] Reproduce unavailable record after KeepAlive reactivation and terminal polling with failing tests.
- [x] Implement scoped recovery UI, preserve text/configuration, clear stale image state and persist the detached draft. Disable remote operations until recovery.
- [x] Verify transient errors retain all draft state and valid work still resumes unchanged.
- [x] Run frontend tests, both type checks, build and browser checks; verify local production entry.

No deletion, paid generation, backend data restoration, or configuration changes.

## Verification

- Before fix: 4 focused failures (missing recovery control and continued polling after 401/403/404).
- After fix: all 344 frontend tests passed across 27 files.
- Application and test type checks passed; Vite production build passed.
- Isolated browser fixture: missing work, works-to-creation navigation, explicit recovery, save, then repeated works-to-creation navigation. No repeated resource error; generation control available, text retained.
- Desktop screenshot reviewed. No physical-phone or paid-generation tests performed.
- Local port 12398 serves the exact new dist index and JS/CSS assets with HTTP 200.
