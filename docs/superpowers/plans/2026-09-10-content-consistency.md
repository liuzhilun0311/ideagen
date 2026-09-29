# Content Consistency Plan

**Goal:** Images and publishing copy use the same current page content, without silently replacing manually edited copy.

**Architecture:** Serialize ordered current pages for both generation paths. Persist the topic and page-text snapshot used for publishing copy inside its existing JSON data. Compare this source with the current draft to show a stale/unknown-source notice. Preserve old copy when regenerating an outline. Keep tagged-page and publishing JSON formats compatible.

**Scope:** Update bundled outline/image/copy prompts, including short image mode. Add factual consistency requirements; distinguish literal image text from visual directions. No paid generation or image/OCR review in this phase. Do not overwrite user-owned prompt files.

- [x] Add regression tests for shared source, stale copy, persistence and outline regeneration preserving copy.
- [x] Implement content source metadata and contextual warning.
- [x] Update and validate compatible default prompt templates.
- [x] Run frontend tests/type checks/build and backend regression tests; record limitations.

## Verification

- Frontend: 351 tests passed; application and test type checks passed.
- Backend: 121 tests run, 120 passed, 1 skipped for local permission conditions.
- All four bundled prompt templates format without placeholder/JSON brace errors.
- Browser fixture: generated copy, edited a page, switched to copy; stale notice appeared and previous copy remained intact. Desktop screenshot inspected.
- Vite build passed; local port 12398 serves the exact current dist index and health reports success.
- No real model calls, paid generation, OCR comparison, or physical-phone testing. These changes constrain generation and track source changes; they do not guarantee rendered image-text accuracy.
- Existing custom prompts remain unchanged. Older copy with no source metadata displays an unverified-source notice, not a false claim that it is current.
