# Content Structure Implementation Plan

Goal: one content-structure contract across outline, image and copy; read-only
recommendation details accessible from both workspaces.

Architecture: reuse the authorized outline.organization catalog and persisted
generation_preferences. Structural rewrites use the existing outline endpoint
and a temporary response, not a mutation of the active draft. Adoption first
saves the original work, then starts a new version with no stale images.
Explicit copy structure overrides the default follow-outline behavior.

- [x] Extend the organization catalog and compile shared phase-specific rules;
  normalize recommendation labels and resolved automatic organization.
- [x] Add a shared workspace structure selector, preview/confirm workflow,
  and recommendation dialogs on image and copy pages.
- [x] Test cancellation, failure, preservation of source work, automatic
  initialization, prompt rules, and read-only recommendation viewing.
- [x] Run backend/frontend tests, typecheck, production build, and browser flow.

## Verification

Backend: 323 tests, no failures, one skip.
Frontend: 47 files, 479 tests passed; test/app typecheck passed.
Vite build passed (existing large-chunk warning); localhost:12399 serves
index-CPoinJWD.js with HTTP 200.
Browser mock workflow: generate structure preview, confirm a new draft, see the
same structure on the copy page, open recommendation reasons. Mobile modal at
390px has no horizontal overflow; viewport restored. No paid upstream calls.

New versions are local drafts until saved. The original must be saved successfully
before adoption. Cancellation aborts local preview handling; this does not guarantee
that an already-sent provider request stops or avoids billing. Arbitrary model
structure descriptions remain descriptions; only authorized organization options
become executable structure settings.

Constraints: preserve existing manual edits and custom catalog entries; no
paid generation during verification; no destructive migration of existing work.
