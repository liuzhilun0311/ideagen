# Outline Infographic Options Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make outline generation fully support recommended content forms, information density, and single-page knowledge infographics from user input through prompts, validation, actual-adoption display, and downstream image generation.

**Architecture:** Keep the existing outline preference contract and extend it with backward-compatible `content_form` and `information_density` fields. A shared backend catalog normalizes and describes these values; the frontend exposes the same options in the creation and workspace settings. The backend resolves automatic values, writes the resolved values into `generation_preferences`, validates a dedicated `[信息图]` page type for single-page infographic outlines, and passes the resolved context into copy and image prompts.

**Tech Stack:** Vue 3, Pinia, TypeScript, Django/Python, existing prompt and generation services, Vitest, Django `SimpleTestCase`.

## Global Constraints

- Preserve existing user changes and unrelated work in the dirty repository.
- Keep old saved outlines and requests valid when the new fields are absent.
- Keep automatic recommendation reasons only for automatic options; user-selected values do not need AI-generated reasons.
- A one-page knowledge infographic is a single `[信息图]` page, not a forced `[封面]` page.
- Information density controls content amount and hierarchy, never a license to make text unreadably small.

### Task 1: Add Shared Option Catalogs

**Files:**
- Create: `backend/generation/outline_modes.py`
- Modify: `frontend/src/features/generationOptions.ts`
- Test: `backend/generation/test_outline_modes.py`
- Test: `frontend/tests/studio/outlineOptions.test.ts`

- [ ] Add canonical values, labels, normalizers, and prompt descriptions for content form and information density.
- [ ] Keep missing/unknown values on the automatic recommendation path.
- [ ] Export TypeScript unions and option arrays used by both settings components.
- [ ] Add tests for canonical values, aliases, labels, and defaults.

### Task 2: Thread New Preferences Through State and Requests

**Files:**
- Modify: `frontend/src/stores/generator.ts`
- Modify: `frontend/src/features/outlineRequest.ts`
- Modify: `frontend/src/composables/useHistoryDraft.ts`
- Modify: `frontend/src/composables/useGenerationRestore.ts`
- Modify: `frontend/src/composables/useOutlineGeneration.ts`
- Modify: `frontend/src/api/types.ts`
- Test: `frontend/tests/studio/outlineRequest.test.ts`
- Test: `frontend/tests/generation/restore.test.ts`

- [ ] Add persisted defaults for content form and information density.
- [ ] Restore them from generation preferences without breaking older records.
- [ ] Include them in outline requests and preserve the existing home tone override.
- [ ] Apply resolved backend values back to the store after generation.
- [ ] Add response typing for the new fields and the infographic page type.

### Task 3: Expose Settings in Creation and Workspace UI

**Files:**
- Modify: `frontend/src/components/home/GrowthTargetOptions.vue`
- Modify: `frontend/src/components/workspace/OutlineOptions.vue`
- Modify: `frontend/src/components/workspace/OutlineParameterSummary.vue`
- Modify: `frontend/src/components/workspace/PageList.vue`
- Modify: `frontend/src/components/history/OutlineModal.vue`
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/views/OutlineView.vue`
- Test: `frontend/tests/studio/outlineParameterSummary.test.ts`

- [ ] Add concise content form and information density controls with help text.
- [ ] Show automatic recommendation as “自动推荐” while retaining stable internal values.
- [ ] Add the new fields to the parameter/actual/reason table.
- [ ] Make adopted values and reasons legible for automatic and user-selected inputs.
- [ ] Render `[信息图]` as “信息图” everywhere page types are displayed.

### Task 4: Implement Backend Recommendation and Prompt Semantics

**Files:**
- Modify: `backend/generation/outline_prompt.py`
- Modify: `backend/generation/recommendations.py`
- Modify: `backend/generation/generation_context.py`
- Modify: `backend/generation/prompts/outline_prompt.txt`
- Modify: `backend/generation/views.py`
- Test: `backend/generation/test_recommendations.py`
- Test: `backend/generation/test_generation_context.py`
- Test: `backend/generation/test_outline_inspection.py`

- [ ] Normalize and include the new preferences in outline prompt input.
- [ ] Ask the model to recommend content form and density only when automatic.
- [ ] Require concise reasons for automatic content form and density.
- [ ] Preserve explicit user selections without requesting redundant reasons.
- [ ] Add one-page infographic rules covering hierarchy, modules, readability, and no forced cover/summary split.
- [ ] Include the resolved values in generation audit/effective preferences and downstream context.

### Task 5: Parse and Validate Single-Page Infographics

**Files:**
- Modify: `backend/generation/page_count.py`
- Modify: `backend/generation/services/outline.py`
- Modify: `backend/generation/outline_inspection.py`
- Modify: `frontend/src/api/types.ts`
- Test: `backend/generation/test_page_count.py`

- [ ] Parse `[信息图]` as the `infographic` page type.
- [ ] Validate `[信息图]` for one-page infographic mode.
- [ ] Keep legacy one-page cover behavior when no infographic form is selected.
- [ ] Return clear validation errors for mismatched page types.

### Task 6: Pass the Resolved Design Into Image and Copy Generation

**Files:**
- Modify: `backend/generation/image_prompt.py`
- Modify: `backend/generation/prompts/image_prompt.txt`
- Modify: `backend/generation/prompts/image_prompt_short.txt`
- Modify: `backend/generation/copy_prompt.py`
- Modify: `backend/generation/services/image.py`
- Test: `backend/generation/test_prompt_consistency.py`
- Test: `backend/generation/test_copy_prompt.py`

- [ ] Include content form, density, layout hierarchy, and text-accuracy priorities in image prompts.
- [ ] Ensure the selected or recommended single-page infographic treatment survives downstream generation.
- [ ] Make copy generation aware of dense infographic modules without forcing sales language.

### Task 7: Full Verification and Regression Review

**Files:**
- Modify: only files required by failing tests.

- [ ] Run backend targeted tests for modes, page count, recommendations, context, and prompt consistency.
- [ ] Run frontend targeted tests for requests, restore, summary, and option UI.
- [ ] Run the full frontend Vitest suite.
- [ ] Run TypeScript typecheck and Vite build.
- [ ] Run the full backend test suite available in the repository.
- [ ] Review the final diff for missed references to page types, persisted fields, and prompt contracts.
