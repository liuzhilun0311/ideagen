# Copy Options and Preview Implementation Plan

Goal: replace the copy template selector with style, structure and length, with a readonly prompt preview.
Architecture: one backend composer shared by preview and generation; per-work preferences in outline JSON.
Tech stack: Django, Vue, Pinia, Vitest.

- [x] Add backend composer and authenticated preview; test defaults, overrides, validation and equality.
- [x] Add typed options, work persistence/restoration, freeze generation input, remove legacy selector.
- [x] Add lazy mounted preview dialog using current content and options, no model call.
- [x] Run generation tests, frontend tests/typecheck/build and inspect desktop/mobile preview.

Constraints: retain legacy template data, ignore legacy template selection for this endpoint,
preserve factual constraints and JSON output, never pay for a generation during verification.

Verification 2026-09-11: generation 79 tests passed; frontend 380 tests passed;
vue-tsc and production Vite build passed. Browser fixture preview checked at desktop
and 390x844: chosen style/structure visible, prompt and copy control readable.
Browser fixture uses a labeled mock response; backend equality is covered separately.
No paid upstream requests were made.
