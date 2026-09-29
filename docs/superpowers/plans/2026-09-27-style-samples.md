# Style Samples Implementation Plan

**Goal:** Publish distinct, reviewed 2K samples for 42 built-in styles.

**Architecture:** Use the existing page-prompt renderer and configured image
client. Retain raw images and a resumable local run record. Publish reviewed
assets through a shared stable-ID sample resolver used by both UI entry points.

**Tech Stack:** Django/Python, Pillow, Vue/TypeScript, Vitest, Playwright.

## Constraints
- User confirmed 2K, 42 images, serial execution, no automatic retries.
- Do not change user prompts, images, model credentials, or historical works.
- Stop on the first failed request; preserve completed files.
- Do not mark unreviewed outputs as approved.

## Tasks
- [x] Add a resumable sample-generation command and unit tests. Generate one
  sample through the existing prompt assembly and review it before continuing.
- [x] Generate remaining styles serially. Review all outputs, preserve raw
  files, and create approved display assets plus a provenance manifest.
- [x] Resolve previews by stable built-in ID. Preserve custom-reference priority,
  identify edited prompts, label samples truthfully, and handle missing images.
- [x] Update selector and management previews, then verify desktop/mobile zoom,
  file uniqueness/dimensions, tests, typechecking, and production build.
- [x] Record the model-specific acceptance results and any remaining failures.

Acceptance evidence: `docs/superpowers/verification/2026-09-27-style-samples.md`.
User authorized regeneration of failed samples. Two additional chat attempts and
one technology attempt produced the final two accepted samples. The exact old
built-in directions were migrated with revision history; user edits were preserved.
