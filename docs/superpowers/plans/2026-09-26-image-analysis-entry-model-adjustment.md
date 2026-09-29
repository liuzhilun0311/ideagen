# Image Analysis Entry And Model Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep image analysis only in Prompt Management's image generation module and let users choose the configured text/multimodal model.

**Architecture:** Remove the existing Home and Workspace presentation and application bindings. Extend the shared image-analysis API and panel with an optional provider name, then load the configured text model list in `PromptManageView` and pass the selected model into the analysis request.

**Tech Stack:** Vue 3, TypeScript, Axios, existing Django image-analysis endpoint.

## Global Constraints

- Use existing configured text-generation providers; do not add a separate model registry.
- Preserve the existing default behavior by selecting the active text provider when no prior selection exists.
- Keep Prompt Management's image-generation tab as the only visible entry point.

---

### Task 1: Restrict the UI entry point

**Files:**
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/views/WorkspaceView.vue`

**Interfaces:**
- Remove the analysis button, dialog, imports, and handlers from both creation views.
- Leave existing creation and workspace generation flows unchanged.

- [x] Remove the Home view analysis button/dialog and its unused imports and handlers.
- [x] Remove the Workspace view analysis button/dialog and its unused imports and handlers.
- [x] Run `npm run typecheck` and confirm no unused symbols or template errors remain.

### Task 2: Add model selection to Prompt Management analysis

**Files:**
- Modify: `frontend/src/api/imageAnalysis.ts`
- Modify: `frontend/src/components/reference/ImageAnalysisPanel.vue`
- Modify: `frontend/src/views/PromptManageView.vue`
- Test: `frontend/tests/studio/imageAnalysis.test.ts`

**Interfaces:**
- `analyzeImage` accepts `providerName?: string` in its context and sends `provider_name`.
- `ImageAnalysisPanel` accepts `models` and `model` props and emits `update:model`.
- `PromptManageView` obtains `textModels` from `useCreationOptions`, initializes the selected model from the active store value, and passes it to the panel.

- [x] Add the optional provider field to the API request.
- [x] Render a model select in the Prompt Management panel and use the selected model for analysis.
- [x] Reuse the focused image-analysis test suite for regression coverage.
- [x] Run the focused test, typecheck, and production build.
