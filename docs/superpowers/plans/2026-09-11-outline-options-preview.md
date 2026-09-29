# Outline Options and Prompt Inspection

Approved design: creation only configures outlines. Remove outline-template
selection; add audience and tone alongside organization. Compose prompts on the
server without an extra model call. Preview and generation use one builder.

- [x] Add validated outline preferences and a pure prompt builder.
- [x] Persist authenticated, owner-only prompt snapshots before dispatch; distinguish
  prepared, generating, succeeded, failed and cancelled. Never store credentials.
- [x] Add preview and recent-record APIs. Include separate reference thumbnails.
- [x] Replace creation options with outline model, organization, audience and tone;
  expose readonly preview/copy and record inspection on creation and workspace.
- [x] Save preferences with works and reuse audience/tone for publishing copy.
- [x] Test builder equality, failed snapshots, owner isolation, frontend options,
  typecheck and production build. Do not make paid upstream calls.

## Verification

- Django generation tests: 73 passed.
- Frontend Vitest: 378 passed across 30 files.
- Frontend typecheck and production build: passed.
- Migration applied locally: generation.0001_initial.
- Browser smoke test (isolated development fixtures): creation only shows outline
  choices; audience/tone selections appear in the readonly preview dialog.
- No paid model requests were made. Preview-to-model equality and both pre-dispatch
  and post-dispatch failures were checked with mocked model clients.
- Existing requests predating this feature have no snapshots. The inspector lists
  the most recent 20 requests plus the current work's linked request, owner-only.
