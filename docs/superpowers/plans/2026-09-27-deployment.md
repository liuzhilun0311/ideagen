# Deployment Implementation Plan

**Goal:** Reproducible local and single-host Docker deployment, Chinese operating
instructions, secret-free source packaging and conservative workspace cleanup.

**Architecture:** Keep Django, SQLite, Vue and the existing image-processing
worker. Build frontend using the existing pnpm lockfile. Share persistent host
directories between web and worker; require explicit production credentials.

**Constraints:** Preserve all business data, user configuration, backups, source,
tests, published samples and working local dependencies. No database replacement.

## Tasks
- [x] Audit requirements, build inputs, persistent paths and initialization.
- [x] Add root requirements entrypoint; repair Docker/Compose and secret-free
  packaging with regression tests.
- [x] Write Windows local, Linux conventional and Docker deployment instructions,
  including HTTPS proxy/SSE, backup, restore, updates and troubleshooting.
- [ ] Remove only verified workspace-owned temporary caches/screenshots; record
  paths and sizes, retaining current dist and installed dependencies.
- [ ] Run dependency, unit, Compose, build and local readiness checks. Attempt
  real Docker build only when the daemon is available; report limitations.

Local verification passed. Docker Desktop startup timed out and image build
failed to connect to its Linux engine. Cache removal was blocked by the execution
environment. Neither operation is claimed complete; see deployment verification.
