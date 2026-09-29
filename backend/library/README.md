# Resource Library

The API contract is in
`docs/superpowers/plans/2026-09-10-copy-sort-models-prompts.md`.

- Orders and copy receipts are account scoped. An idempotency key is unique
  within an account and bound to resource, category, source and input revision.
  Exact retries return the original created ID/name with the current effective
  order and revision, provided source and copy remain accessible. The stored
  receipt remains unchanged.
- Model visibility matches the config list. Copying additionally requires
  administrator access to shared models, or an existing private configuration
  file while private mode is enabled. A shared fallback is never an owned source.
- Prompt visibility uses the existing unordered prompt assembler. List
  serialization supplies visible IDs to the ordering helper, avoiding recursion.
- Atomic file replacement and compensating restoration cover write failures,
  receipt insertion failures and SQL commit failures. A local thread lock, an OS
  file lock and a database writer gate serialize library requests, including
  rollback, across accounts and workers using the same storage.
- Filesystem replacement and SQL commit are not a distributed transaction:
  forced process termination between them can leave an unrecorded copy.
  Existing config/prompt edit endpoints and manual file edits do not acquire
  the library lock; simultaneous legacy edits remain a lost-update risk.
  Extending locking to those writers or migrating resource contents into SQL
  is outside this focused backend integration.

`0001_initial` is additive. It has not been applied to the workspace database.
The mutex row is lazily initialized inside the first writer transaction.

Tests use temporary configuration roots, synthetic credentials and mocked base
prompts; they never invoke a model:

```powershell
.venv\Scripts\python.exe backend/manage.py test library providers prompts
.venv\Scripts\python.exe backend/manage.py makemigrations library --check --dry-run
```
