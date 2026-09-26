# 图片分析与参考资产复用实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 IdeaGen 增加统一的图片多模态分析能力，并让内容、单页布局、图片风格分别接入参考素材库、提示词中心和现有创作工作台。

**Architecture:** 在后端新增 `reference_assets` Django app，保存用户私有的图片分析记录和参考素材；在 `generation` 中复用现有文本多模态客户端，返回经过后端校验的分析协议。前端新增可复用的图片分析面板和 API，通过首页、工作台、提示词中心三个上下文入口打开；应用结果使用明确的 merge/replace 语义，最终仍由现有提示词目录和生成参数层组装实际生成请求。

**Tech Stack:** Django 5.2 + SQLite + Django ORM；Vue 3 + TypeScript + Pinia；现有 Axios/fetch API 层；现有 Gemini/OpenAI-compatible 多模态文本客户端；Vitest 与 Django TestCase。

## Global Constraints

- 第一版复用现有文本服务商的多模态能力，不增加独立图片理解模型配置。
- 内容进入参考素材库；单页布局和图片风格进入现有图片提示词目录。
- 应用到已有创作默认使用 `merge`，只有用户明确选择时才使用 `replace`。
- 图片风格提示词不得写死分辨率、宽高比、质量和输出格式。
- 所有分析记录、参考素材和图片文件按用户隔离；历史作品保存实际使用过的分析快照。
- 分析失败不得创建半成品资产，也不得污染当前创作状态。
- 使用现有认证、结构化错误、提示词权限、版本和排序机制。
- 不回滚工作区中已有的未提交改动；每个任务只提交自己负责的文件。

---

### Task 1: 建立分析协议与后端应用骨架

**Files:**
- Create: `backend/reference_assets/__init__.py`
- Create: `backend/reference_assets/apps.py`
- Create: `backend/reference_assets/models.py`
- Create: `backend/reference_assets/migrations/__init__.py`
- Create: `backend/reference_assets/admin.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/config/urls.py`
- Test: `backend/reference_assets/tests.py`

**Interfaces:**
- Produces `ImageAnalysis`, `ReferenceAsset` Django models and app registration for later API tasks.
- `ImageAnalysis` fields: `id`, `owner`, `source_image_path`, `source_image_digest`, `content`, `layout`, `visual_style`, `rewritten_content`, `user_note`, `status`, `created_at`, `updated_at`.
- `ReferenceAsset` fields: `id`, `owner`, `analysis`, `title`, `image_path`, `content`, `rewritten_content`, `user_note`, `created_at`, `updated_at`.

- [ ] **Step 1: Write model tests for ownership and JSON defaults**

Create `backend/reference_assets/tests.py` with a `TestCase` that creates an `accounts.User`, then asserts a new `ImageAnalysis` and `ReferenceAsset` receive independent empty JSON defaults and are linked to the same owner.

```python
def test_analysis_and_asset_have_owner_scoped_defaults(self):
    analysis = ImageAnalysis.objects.create(owner=self.user)
    asset = ReferenceAsset.objects.create(owner=self.user, analysis=analysis)
    self.assertEqual(analysis.content, {})
    self.assertEqual(analysis.layout, {})
    self.assertEqual(analysis.visual_style, {})
    self.assertEqual(asset.owner_id, self.user.id)
    self.assertEqual(asset.analysis_id, analysis.id)
```

- [ ] **Step 2: Run the new model test before implementation**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py test reference_assets
```

Expected: FAIL because the app and models do not exist yet.

- [ ] **Step 3: Implement the app and models**

Register `reference_assets.apps.ReferenceAssetsConfig` in `INSTALLED_APPS`. Use UUID primary keys for both models, `ForeignKey("accounts.User", on_delete=models.CASCADE)`, `JSONField(default=dict)`, and `TextField` for generated text. Store optional image paths as nullable character fields. Create and register the concrete URL namespace in Task 3, after `backend/reference_assets/urls.py` exists.

- [ ] **Step 4: Create and apply the migration**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py makemigrations reference_assets
.venv\Scripts\python.exe backend\manage.py migrate
```

Expected: migration succeeds and creates the two user-owned tables.

- [ ] **Step 5: Run the model test**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py test reference_assets
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/reference_assets backend/config/settings.py backend/config/urls.py
git commit -m "feat: add image analysis asset models"
```

### Task 2: Add normalized analysis protocol and multimodal service

**Files:**
- Create: `backend/reference_assets/protocol.py`
- Create: `backend/reference_assets/services.py`
- Modify: `backend/generation/utils/text_client.py`
- Modify: `backend/generation/utils/genai_client.py`
- Modify: `backend/generation/utils/responses_client.py`
- Test: `backend/reference_assets/test_protocol.py`
- Test: `backend/reference_assets/test_services.py`

**Interfaces:**
- `normalize_analysis_payload(value: object) -> dict`
- `parse_analysis_response(text: str) -> dict`
- `build_analysis_prompt(context: dict | None = None) -> str`
- `analyze_image(image: bytes, user_id: str, context: dict | None = None, provider_name: str | None = None) -> dict`
- Returned normalized payload always contains `content`, `layout`, `visual_style`, and `rewritten_content`.

- [ ] **Step 1: Write failing protocol tests**

Cover:

1. Valid JSON preserves the three sections.
2. Markdown code fences are accepted.
3. Missing sections become empty dictionaries and empty strings.
4. Invalid JSON raises `ValueError` with a user-safe message.
5. Image style prompt text does not contain concrete image parameters such as `1K`, `3:4`, `low`, or `png`.

```python
def test_parse_code_fenced_response(self):
    result = parse_analysis_response('```json\n{"content": {"summary": "x"}}\n```')
    self.assertEqual(result["content"]["summary"], "x")
    self.assertEqual(result["layout"], {})
    self.assertEqual(result["visual_style"], {})
```

- [ ] **Step 2: Run protocol tests to verify failure**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py test reference_assets.test_protocol reference_assets.test_services
```

Expected: FAIL because the protocol and service functions are not implemented.

- [ ] **Step 3: Implement normalization and prompt construction**

Use the existing content JSON parsing conventions, but define an explicit schema:

```python
{
    "content": {
        "summary": "",
        "subjects": [],
        "text_structure": [],
        "visual_focus": "",
        "rewrite": "",
    },
    "layout": {
        "page_type": "content",
        "description": "",
        "regions": [],
        "hierarchy": "",
        "spacing": "",
        "prompt_text": "",
    },
    "visual_style": {
        "description": "",
        "attributes": [],
        "palette": [],
        "medium": "",
        "lighting": "",
        "composition": "",
        "prompt_text": "",
    },
    "rewritten_content": "",
}
```

Do not allow user-provided prompt text to remove the required JSON contract. Add instructions that OCR may be uncertain, content must be editable, and image parameters are controlled outside the prompt.

- [ ] **Step 4: Implement the multimodal service**

Load the user-authorized text provider through `providers.config.get_text_provider_config`, instantiate the same client factory used by outline/content generation, and call its image-capable text method. Keep provider selection explicit when supplied. Do not log image bytes or full sensitive provider payloads.

- [ ] **Step 5: Run protocol and service tests**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py test reference_assets.test_protocol reference_assets.test_services
```

Expected: PASS with mocked provider clients and no real model calls.

- [ ] **Step 6: Commit**

```powershell
git add backend/reference_assets backend/generation/utils/text_client.py backend/generation/utils/genai_client.py backend/generation/utils/responses_client.py
git commit -m "feat: add multimodal image analysis service"
```

### Task 3: Implement analysis and reference asset APIs

**Files:**
- Create: `backend/reference_assets/views.py`
- Create: `backend/reference_assets/urls.py`
- Modify: `backend/config/urls.py`
- Test: `backend/reference_assets/test_api.py`

**Interfaces:**
- `POST /api/image-analysis`
- `GET /api/image-analysis/<analysis_id>`
- `PUT /api/image-analysis/<analysis_id>`
- `POST /api/image-analysis/<analysis_id>/apply`
- `DELETE /api/image-analysis/<analysis_id>`
- `GET /api/reference-assets`
- `POST /api/reference-assets`
- `PUT /api/reference-assets/<asset_id>`
- `DELETE /api/reference-assets/<asset_id>`
- `POST /api/prompt-center/from-analysis`

- [ ] **Step 1: Write failing API tests**

Test with Django `Client` and bearer tokens:

1. Unauthenticated analysis returns `401`.
2. Multipart upload creates an analysis for the current user.
3. A second user cannot read, update, apply, or delete the first user’s analysis.
4. Invalid image type and oversized input return `400`.
5. Reference asset creation can preserve the source image and returns a user-scoped record.
6. Deleting a reference asset removes its stored image without deleting a generated history record.
7. Creating prompts from analysis only accepts `layout` and `visual_style`.

- [ ] **Step 2: Run API tests to verify failure**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py test reference_assets.test_api
```

Expected: FAIL because the routes and views are not implemented.

- [ ] **Step 3: Implement safe image storage helpers**

Add private helpers in `reference_assets/services.py` for:

- Validating MIME type using Pillow.
- Enforcing a concrete maximum upload size.
- Calculating SHA-256 digest.
- Writing under `settings.HISTORY_ROOT / owner_id / "_reference_assets"`.
- Rejecting path traversal through resolved-path containment.
- Deleting only files owned by the reference asset.

- [ ] **Step 4: Implement analysis endpoint**

Parse multipart image and optional `topic`, `page_content`, and `provider_name`; call `analyze_image`; persist the normalized analysis only after successful parsing; return the analysis JSON. Do not create a row when provider or parsing fails.

- [ ] **Step 5: Implement analysis CRUD and apply response**

Apply only validates ownership and returns normalized data for the requested `parts` and `mode`; it must not mutate history records. The front end will merge the returned data into its current draft. Reject unknown parts and modes with `400`.

- [ ] **Step 6: Implement reference asset CRUD**

Support saving selected content and rewritten content, optionally copying the source image. List and detail responses include only the current user’s assets. Delete the optional source image after deleting the database row.

- [ ] **Step 7: Implement prompt creation adapter**

Accept only `layout` and `visual_style`, map them to `image/layout` and `image/style`, and delegate validation/version/name/permission behavior to the existing prompt catalog services. Use the edited draft supplied by the user only after validating allowed placeholders and required fields.

- [ ] **Step 8: Run API tests**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py test reference_assets.test_api
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add backend/reference_assets backend/config/urls.py
git commit -m "feat: expose image analysis and reference asset APIs"
```

### Task 4: Add immutable analysis snapshots to history

**Files:**
- Modify: `backend/history/models.py`
- Modify: `backend/history/services.py`
- Modify: `backend/history/views.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/history.ts`
- Test: `backend/history/tests.py`

**Interfaces:**
- `HistoryRecord` receives an `analysis_snapshots` JSON field defaulting to `[]`.
- History update accepts an optional `analysis_snapshots` list and validates it as JSON.
- History detail and list responses preserve snapshots without resolving current assets.

- [ ] **Step 1: Write failing history snapshot tests**

Create a record with one applied analysis snapshot, delete the source analysis/asset, then assert history detail still returns the snapshot. Assert malformed snapshot payloads are rejected with `400`.

- [ ] **Step 2: Run the focused history tests**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py test history
```

Expected: the new snapshot test fails before the field and update path exist.

- [ ] **Step 3: Add the migration and service field handling**

Add `analysis_snapshots = models.JSONField(default=list, blank=True)` and migration. Include it in `_to_detail`, create/update paths, and any serializer/type definitions. Validate each snapshot has `content`, `layout`, and `visual_style` objects before saving.

- [ ] **Step 4: Run history tests**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py makemigrations history
.venv\Scripts\python.exe backend\manage.py migrate
.venv\Scripts\python.exe backend\manage.py test history
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/history frontend/src/api/types.ts frontend/src/api/history.ts
git commit -m "feat: persist image analysis snapshots in history"
```

### Task 5: Add frontend analysis API and reusable state

**Files:**
- Create: `frontend/src/api/imageAnalysis.ts`
- Create: `frontend/src/features/imageAnalysis.ts`
- Create: `frontend/src/components/reference/ImageAnalysisPanel.vue`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/stores/generator.ts`
- Modify: `frontend/src/stores/studioSession.ts`
- Test: `frontend/tests/studio/imageAnalysis.test.ts`

**Interfaces:**
- `analyzeImage(file: File, context?: ImageAnalysisContext, signal?: AbortSignal): Promise<ImageAnalysisResponse>`
- `getImageAnalysis(id: string): Promise<ImageAnalysisResponse>`
- `updateImageAnalysis(id: string, patch: ImageAnalysisPatch): Promise<ImageAnalysisResponse>`
- `applyImageAnalysis(id: string, input: ApplyImageAnalysisInput): Promise<AppliedImageAnalysis>`
- `createReferenceAsset(input: CreateReferenceAssetInput): Promise<ReferenceAsset>`
- `createPromptsFromAnalysis(input: CreatePromptFromAnalysisInput): Promise<PromptEntry[]>`
- `useImageAnalysisDraft()` owns temporary panel state and never persists a live upload to `localStorage`.

- [ ] **Step 1: Write failing frontend state tests**

Test:

1. Empty analysis state has independent content/layout/style objects.
2. Merge application appends content and style notes without removing existing values.
3. Replace application changes only selected parts.
4. Cancelling analysis clears busy state but preserves the existing generator draft.
5. File objects are not serialized by the generator store.

- [ ] **Step 2: Run the focused frontend tests**

Run:

```powershell
cd frontend
npm run test -- tests/studio/imageAnalysis.test.ts
```

Expected: FAIL because the API/state modules do not exist.

- [ ] **Step 3: Implement typed API functions**

Use Axios for CRUD and `fetch`/`FormData` for multipart analysis, with the existing `API_BASE_URL`, auth interceptor, structured error normalization, and abort signal behavior.

- [ ] **Step 4: Implement merge/replace helpers**

Define pure functions in `frontend/src/features/imageAnalysis.ts`:

```ts
export function mergeAnalysisIntoDraft(
  draft: GeneratorState,
  analysis: ImageAnalysis,
  parts: AnalysisPart[],
): GeneratorState

export function replaceAnalysisIntoDraft(
  draft: GeneratorState,
  analysis: ImageAnalysis,
  parts: AnalysisPart[],
): GeneratorState
```

Keep content, layout, and visual style separate. Preserve the original analysis snapshot for later history saving.

- [ ] **Step 5: Implement the reusable panel**

The panel accepts a `context` prop (`home`, `workspace`, or `prompt-center`) and emits:

```ts
analyzed
apply
save-reference
save-prompts
close
```

Render independent sections with edit controls, merge/replace controls, loading/error states, and no horizontal overflow on mobile.

- [ ] **Step 6: Run focused frontend tests**

Run:

```powershell
cd frontend
npm run test -- tests/studio/imageAnalysis.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/api frontend/src/features/imageAnalysis.ts frontend/src/components/reference/ImageAnalysisPanel.vue frontend/src/stores/generator.ts frontend/src/stores/studioSession.ts frontend/tests/studio/imageAnalysis.test.ts
git commit -m "feat: add reusable image analysis frontend state"
```

### Task 6: Integrate the home creation entry

**Files:**
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/components/home/ComposerInput.vue`
- Modify: `frontend/src/stores/generator.ts`
- Test: `frontend/tests/studio/homeImageAnalysis.test.ts`

**Interfaces:**
- Home opens `ImageAnalysisPanel` with `context="home"`.
- Applying content appends to `referenceContent`.
- Applying layout/style stores pending creation guidance in generator state.
- Saving content creates a reference asset and may retain the original image.

- [ ] **Step 1: Write failing home integration tests**

Assert that:

1. Opening the panel does not clear topic/reference content.
2. Applying content appends with a visible separator.
3. Applying layout/style changes only the pending creation guidance.
4. Saving selected content calls the reference asset API.

- [ ] **Step 2: Run the tests**

Run:

```powershell
cd frontend
npm run test -- tests/studio/homeImageAnalysis.test.ts
```

Expected: FAIL before the home entry exists.

- [ ] **Step 3: Add the home entry and state wiring**

Add an icon+text action near the existing reference-image controls. Keep the primary “generate outline” action unchanged. Pass current topic and reference content as analysis context, then use the shared panel events to update the generator store.

- [ ] **Step 4: Run home integration tests**

Run:

```powershell
cd frontend
npm run test -- tests/studio/homeImageAnalysis.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/views/HomeView.vue frontend/src/components/home/ComposerInput.vue frontend/src/stores/generator.ts frontend/tests/studio/homeImageAnalysis.test.ts
git commit -m "feat: integrate image analysis into creation home"
```

### Task 7: Integrate the workspace current-page entry and history snapshot

**Files:**
- Modify: `frontend/src/views/WorkspaceView.vue`
- Modify: `frontend/src/components/workspace/PageEditor.vue`
- Modify: `frontend/src/composables/useDraftSave.ts`
- Modify: `frontend/src/stores/generator.ts`
- Test: `frontend/tests/studio/workspaceImageAnalysis.test.ts`
- Test: `frontend/tests/studio/saveAnalysisSnapshot.test.ts`

**Interfaces:**
- Workspace opens the panel with `context="workspace"` and the selected page as context.
- Applied parts merge into the selected page/current style.
- `useDraftSave().snapshot()` includes immutable `analysis_snapshots`.
- Existing preview/save/generation locking remains authoritative.

- [ ] **Step 1: Write failing workspace tests**

Cover:

1. Analysis uses the selected page, not page zero.
2. Merge content does not replace existing page content.
3. Replace layout affects only the selected page.
4. Saving includes the normalized analysis snapshot.
5. Changing the selected page does not mutate the previous page’s applied analysis.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
cd frontend
npm run test -- tests/studio/workspaceImageAnalysis.test.ts tests/studio/saveAnalysisSnapshot.test.ts
```

Expected: FAIL before workspace integration.

- [ ] **Step 3: Add workspace toolbar and panel**

Add the analysis action to the existing tools area. Disable it while the workspace is busy, the record is unavailable, or the current page does not exist. Use the existing dialog/mobile tools pattern.

- [ ] **Step 4: Add snapshot persistence**

When an analysis is applied, append a normalized snapshot containing the source analysis ID, selected parts, mode, and resulting sections. `useDraftSave` sends it through the existing history update payload.

- [ ] **Step 5: Run workspace tests**

Run:

```powershell
cd frontend
npm run test -- tests/studio/workspaceImageAnalysis.test.ts tests/studio/saveAnalysisSnapshot.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/views/WorkspaceView.vue frontend/src/components/workspace/PageEditor.vue frontend/src/composables/useDraftSave.ts frontend/src/stores/generator.ts frontend/tests/studio/workspaceImageAnalysis.test.ts frontend/tests/studio/saveAnalysisSnapshot.test.ts
git commit -m "feat: add workspace image analysis reuse"
```

### Task 8: Integrate prompt center and reference asset management

**Files:**
- Modify: `frontend/src/views/PromptManageView.vue`
- Create: `frontend/src/views/ReferenceAssetsView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/api/referenceAssets.ts`
- Test: `frontend/tests/studio/promptImageAnalysis.test.ts`
- Test: `frontend/tests/history/referenceAssets.test.ts`

**Interfaces:**
- Prompt center opens analysis with `context="prompt-center"` and only exposes layout/style prompt saving.
- `ReferenceAssetsView` lists, edits, previews, and deletes user-owned reference assets.
- New route: `/reference-assets`.
- Navigation label: `参考素材`.

- [ ] **Step 1: Write failing prompt-center and asset-library tests**

Assert that:

1. Prompt center cannot save `content` as a prompt.
2. Layout and style drafts map to the correct prompt categories.
3. Reference asset list renders saved assets and supports delete.
4. Navigation and route are protected by authentication.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
cd frontend
npm run test -- tests/studio/promptImageAnalysis.test.ts tests/history/referenceAssets.test.ts
```

Expected: FAIL before the route and components exist.

- [ ] **Step 3: Add the reference asset API**

Implement typed list/create/update/delete functions with the existing auth client and image URL helper. Render private asset image URLs through authenticated fetch or token query URLs according to the existing image-serving conventions.

- [ ] **Step 4: Add prompt-center integration**

Place the entry beside existing prompt creation actions. After analysis, show only layout/style save controls and reuse the prompt center’s existing save/reorder/permission refresh flow.

- [ ] **Step 5: Add the reference asset library route**

Add a protected route and navigation item. The view must support empty, loading, error, preview, edit, and delete states. Keep the first version focused on user-owned assets and avoid introducing sharing controls.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
cd frontend
npm run test -- tests/studio/promptImageAnalysis.test.ts tests/history/referenceAssets.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/views/PromptManageView.vue frontend/src/views/ReferenceAssetsView.vue frontend/src/router/index.ts frontend/src/App.vue frontend/src/api/referenceAssets.ts frontend/tests/studio/promptImageAnalysis.test.ts frontend/tests/history/referenceAssets.test.ts
git commit -m "feat: add prompt and reference asset image analysis entries"
```

### Task 9: Add backend/ frontend contract coverage and compatibility checks

**Files:**
- Modify: `backend/reference_assets/test_api.py`
- Modify: `backend/generation/tests.py`
- Modify: `backend/history/tests.py`
- Modify: `frontend/tests/setup.ts`
- Create: `frontend/tests/studio/imageAnalysisContract.test.ts`
- Create: `tests/smoke_image_analysis.py`

**Interfaces:**
- No new production interfaces; this task verifies the complete contract against existing generation, prompt, history, auth, and postprocessing boundaries.

- [ ] **Step 1: Add contract tests**

Cover the complete sequence:

```text
login
-> analyze multipart image
-> apply layout/style
-> save reference asset
-> create prompt entries
-> save history snapshot
-> delete analysis/asset
-> read history snapshot
```

Use mocked text providers and synthetic PNG bytes; do not make real paid AI calls.

- [ ] **Step 2: Run backend focused suites**

Run:

```powershell
.venv\Scripts\python.exe backend\manage.py test accounts generation prompts history providers postprocessing reference_assets
```

Expected: PASS.

- [ ] **Step 3: Run frontend focused suites**

Run:

```powershell
cd frontend
npm run test -- tests/studio tests/history tests/generation tests/postprocessing
```

Expected: PASS.

- [ ] **Step 4: Run type checking and production build**

Run:

```powershell
cd frontend
npm run typecheck
npm run test:typecheck
npm run build
```

Expected: all commands exit with code 0 and `frontend/dist` is generated.

- [ ] **Step 5: Run the smoke script against the local backend**

Start the project using the existing launcher or a clean test server, then run:

```powershell
.venv\Scripts\python.exe tests\smoke_image_analysis.py
```

Expected: authentication, analysis, asset, prompt, and history snapshot checks pass without external AI calls.

- [ ] **Step 6: Commit**

```powershell
git add backend frontend tests/smoke_image_analysis.py
git commit -m "test: verify image analysis asset integration"
```

### Task 10: Visual and operational verification

**Files:**
- Modify: `docs/superpowers/verification/2026-09-26-image-analysis-reference-assets.md`
- Modify: `项目说明文档.md` only if the existing project document is kept in sync by the implementation
- Modify: `README.md` only if the startup or route documentation changes

- [ ] **Step 1: Start the dev server without changing the existing launcher contract**

Use the existing `start_web_server.ps1` behavior and verify the actual ready port before browser checks.

- [ ] **Step 2: Verify desktop and mobile layouts**

Check at 375px, 768px, 1024px, and 1440px:

- analysis panel has no page-level horizontal scroll;
- three result sections remain distinguishable;
- loading and error states do not shift the main layout;
- prompt center does not display original images;
- reference asset library displays image preview and edit controls;
- workspace application does not hide save/preview controls.

- [ ] **Step 3: Verify the key user journey**

Manually complete:

```text
home analyze -> apply content/layout/style -> save content asset
workspace analyze -> merge style -> save -> reopen history
prompt center analyze -> save layout/style prompts
reference assets -> edit/delete
```

- [ ] **Step 4: Record verification evidence**

Create the verification note with commands, browser route, viewport sizes, test results, and any remaining limitations. Do not claim completion if a command or visual check failed.

- [ ] **Step 5: Commit**

```powershell
git add docs/superpowers/verification docs/项目说明文档.md README.md
git commit -m "docs: verify image analysis asset workflow"
```
