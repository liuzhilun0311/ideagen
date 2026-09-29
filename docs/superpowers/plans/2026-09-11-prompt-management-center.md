# Prompt Management Center Implementation Plan

**Goal:** Manage the real base and selectable prompt instructions with durable IDs,
permissions, revisions, ordering and backward-compatible generation.
**Architecture:** Database catalog with seeded builtins; authenticated API exposes
management capabilities and usable entries. Generation resolves a user-scoped catalog
snapshot. Frontend management and selectors consume the same catalog.
**Tech Stack:** Django, SQLite, Vue, Pinia, Vitest.

## Shared Contract

Modules: `outline`, `image`, `content`.
Categories: `base`; outline `organization`, `audience`, `tone`;
image `layout`, `style`; content `style`, `structure`, `length`.
Entries expose `id,module,category,name,description,content,metadata,legacy_value,
owner_id,owner_name,builtin,enabled,visibility,allowed_users,revision,can_edit,can_use`.
Custom IDs are UUID strings, builtin IDs are deterministic.
`visibility`: private, selected, public. Only admins can publish public.

GET `/api/prompt-center?manage=1` returns `{success,entries,categories}`.
Without manage only usable entries are returned.
POST `/api/prompt-center/save` takes entry editable fields plus id/revision for edits.
POST `/api/prompt-center/copy` takes id, returns entry.
GET `/api/prompt-center/<id>/versions` returns versions.
POST `/api/prompt-center/restore` takes id,revision,version; missing version restores builtin default.
POST `/api/prompt-center/reorder` takes module,category,ids,revision; returns revision.
GET catalog also returns `orders` by `module.category`, each with revision and ids.
GET `/api/prompt-center/users` returns minimal `{id,username}` users.

Backend runtime: `prompts.catalog_runtime.prompt_scope(user_id)` resolves/fixes catalog
for one request. `option(module,category,value)` returns authorized enabled entry,
accepts stable id or builtin legacy alias; explicit unavailable selections raise ValueError.
`base(module)` returns current base text. `options(module,category)` lists usable entries.
Generation boundaries must scope preview and actual generation, and freeze rendered
instructions before starting worker threads. Do not silently replace revoked custom IDs.

## Tasks

- [ ] Database models, idempotent builtin seed, revisions and permission tests.
- [ ] Catalog API: validation, sharing, copy, history, restore and optimistic ordering.
- [ ] Three generation composers consume catalog snapshots and preserve protocols.
- [ ] Frontend management screen, editor, authorization, history and legacy entry.
- [ ] Frontend dynamic selectors, unknown-value handling, defaults and restoration.
- [ ] Integration tests, migration backup, production build and desktop/mobile checks.

No paid model requests. Preserve unrelated dirty worktree files and legacy templates.
Use disjoint worker write scopes and review integrated changes before claiming completion.
