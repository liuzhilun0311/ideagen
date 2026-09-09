# Independent Modules And Visible Copy Generation

User approved independent navigation on 2026-09-09 and requested a prominent copy-generation action.

## Behavior

- Creation, works, prompts, models, and admin-only users remain separate routes.
- Switching modules preserves the creation component, task ownership, selected page, edits, and save state.
- Background completion reports status without navigating away from the current module.
- Creation navigation returns to the current workspace, or the topic composer when no outline exists.
- Browsing works is read-only with respect to the current draft. Replacing it is prohibited while busy and requires confirmation when a draft exists. Deleting its record is prohibited until another draft is active.
- Logout and actual browser unload retain protections for running tasks and unsaved drafts.
- Configuration changes are refreshed when returning to idle creation. In-flight generation parameters are not changed by option refreshes.
- Generate copy and generate images are sibling primary actions above the workspace. Copy generation is also available within the copy editor. Mobile retains direct access without opening advanced settings.
- Preview fixtures provide independent management state, demonstrative admin access, and delayed generation without real provider calls.

## Architecture

Keep the existing Vue routes and component-owned runners. KeepAlive retains the workspace as well as the other modules. A small nonpersistent Pinia session store coordinates live busy state, draft revisions, and background notifications; it does not move model configuration or historical records into the generator.

Explicit draft replacement increments a revision to reset workspace selection and its confirmed-save baseline. History retrieval checks session ownership again after awaiting the API. Existing per-record preview does not hydrate the generator.

## Limits And Verification

This is not multi-workspace concurrent generation, server background queues, or a guarantee that generation survives browser closure. Existing authentication roles remain enforced.

Test session replacement guards, late history reads, background completion navigation, save ownership, visible copy actions, and option refresh behavior. Verify management routes and navigation during delayed mock generation in desktop/mobile browser views; run the existing unit suite, both typechecks, and production build.
