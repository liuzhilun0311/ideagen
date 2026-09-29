# Image Style Presets Plan

**Goal:** Knowledge-image sets support comic, hand-drawn and other explicitly selected visual styles without changing factual content or publishing voice.

**Architecture:** Persist per-work image_style JSON (preset, notes, optional applied choice). Request-scoped style directives extend resolved image prompts, including custom ones, for generate/retry routes. The frontend provides an accessible selector before generation and in image settings. No automatic generation on selection.

**Presets:** auto, comic, sketch-note, watercolor, pencil, infographic, photography, collage, minimal.

**Constraints:** Existing accounts, credentials, custom prompt files and works preserved. Styles are art direction, not model guarantees. No real provider calls. Knowledge-comic illustration only, not sequential story panels. No arbitrary style-reference upload in this iteration.

- [ ] Add backend validation, persistent style field, prompt composition and route coverage.
- [ ] Add frontend selection, persistence/restore, immutable request propagation and changed-style handling.
- [ ] Rewrite default outline/image/copy prompts with compatible output contracts.
- [ ] Test defaults, permissions, malformed style, retries, save/restore, and no automatic generation.
- [ ] Apply additive migration; run regressions, type checks, build and browser smoke checks.
