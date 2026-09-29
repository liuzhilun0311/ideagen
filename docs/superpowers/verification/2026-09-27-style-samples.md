# Style Sample Acceptance - 2026-09-27

## Scope

42 built-in styles now have distinct, reviewed model-generated samples.
Model: `gpt-image-2.5-flare`; requested size: 2K; returned dimensions:
1536 x 2048; quality: low; original format: PNG. Display originals are lossless
WebP and separate 576 x 768 thumbnails.

All samples use the same synthetic plant-care subject and the application's
actual prompt renderer and configured image client. Requests ran serially,
with no automatic retries. No historical work images were regenerated.

## Review

- Initial run: 42 outputs, 40 accepted.
- Initial chat-proof: rejected for missing dialogue structure.
- Initial tech-brand: rejected for insufficient technology grid/modules.
- User explicitly authorized regeneration.
- Second run: technology accepted with visible grid, aligned panels, icons
  and connections; chat rejected because same-side bubbles remained list-like.
- Third run: chat accepted with left-right-left tailed messages and preserved text.
  Its illustration is larger than requested, so this is a recognizable style
  example, not proof of exact percentage compliance.
- Total: 45 successful requests; 42 published images; 3 rejected outputs retained
  for traceability. No further paid requests were issued.

Run records and raw outputs: `output/style-samples-20260927`, corresponding
`-r2` and `-r3` directories. Each includes prompts, image hashes and reviews.
Published provenance: `frontend/src/features/styles/samples.json`.
No credentials or complete upstream errors are stored in these records.

Only two exact shipped built-in directions were upgraded through migration
`prompts.0002_calibrate_style_directions`. Their revision history was preserved.
Database backup: `data/backups/before-style-calibration-20260927.sqlite3`.
Read-only before/after comparison confirmed only these two content values
changed; administrator edits, including the existing minimal style, were retained.

## Verification

- Frontend Vitest: 42 files, 446 tests passed.
- Frontend production typecheck and test typecheck: passed.
- Backend full suite: 276 tests, no failures, 1 skipped.
- Asset tests: all styles accounted for; unique image hashes; valid WebP sizes;
  sample directions equal current shipped directions.
- `makemigrations --check --dry-run`: no changes detected.
- `pnpm build`: passed. Existing large-bundle and pnpm settings warnings remain.
- Playwright/Edge: all 42 originals decoded from production port 12399;
  both preview fixture entry points displayed all samples at 1440 and 390 widths;
  zoom used 1536-pixel originals; no page errors.
- All 84 original/thumbnail URLs returned HTTP 200 and image/webp.
- Windows WebP MIME fallback fixed and covered by a regression test.
- `start_web_server.ps1 -CheckOnly -NoBrowser`: ready on port 12399.

Screenshots: `frontend/test-results/style-samples/`.
Interaction checks used synthetic preview fixtures, not the user's saved works.

## Limits

This validates one model, one shared subject and one aspect ratio. It does not
certify every model, prompt edit, platform composition or future generation.
Synthetic photography, chat and documentary examples are not customer evidence.
Custom references retain priority; edited built-in prompts display a reference
label instead of claiming the original sample tests their modified prompt.
