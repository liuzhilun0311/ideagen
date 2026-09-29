# Generation Layers Implementation Plan

**Goal:** Separate outline organization, page layout, visual style and output parameters.

**Architecture:** Preserve the existing text-based page contract and style recommendation
object. Add optional parsed metadata, a shared parameter normalizer, and lightweight
selectors in existing screens. Old works remain editable.

**Tech Stack:** Django, Vue, Pinia, unittest, Vitest.

## Constraints

- Never rewrite printable facts to remove technical terms.
- User-selected image parameters override provider defaults on all generation routes.
- Do not use paid upstream calls in automated tests.
- Keep unrelated working-tree changes.

## Tasks

- [ ] Add `generation/parameters.py`, with `apply_image_parameters(service, values)`;
  validate resolution/aspect/quality/format before calling upstream. Normalize AUTO
  to 1K. Use it in generate, retry, retry-failed, regenerate and candidate routes.
- [ ] Add `generation/structure.py`, with organization catalog and text metadata
  extraction. Preserve `<page>` and existing style metadata. Return organization,
  page layout and visual focus without changing existing content contracts.
- [ ] Simplify both default image templates: current page only, no full-outline
  duplication, no fixed image specification. Inject explicit selected layout.
- [ ] Add organization selection to creation and outline adjustment; add page layout
  selection to the existing editor. Persist organization with outline metadata.
- [ ] Pass image parameters through candidate and retry clients, expose image
  parameter controls without requiring users to discover a collapsed group.
- [ ] Add unit tests for defaults, explicit overrides, invalid values, AUTO,
  metadata extraction and legacy pages; run
  `.venv/Scripts/python.exe backend/manage.py test generation -v 0`.
- [ ] Run frontend Vitest and production build, inspect resulting errors, fix
  regressions, and document any remaining verification gaps.

## Test Cases

```python
assert normalize_image_parameters({})["quality"] == "low"
assert normalize_image_parameters({"resolution": "AUTO"})["resolution"] == "1K"
assert normalize_image_parameters({"quality": "high"})["quality"] == "high"
```

Malformed nonempty values raise `ValueError`; they must never silently become
more expensive defaults. Old pages without layout use content-aware auto layout.
