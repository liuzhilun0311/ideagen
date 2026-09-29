# 大纲页数参数 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为大纲创作增加“自动或 1-15 页”的选择，并让固定页数在前后端都严格生效。

**Architecture:** 使用现有 Pinia 生成器状态保存页数选择，通过 `OutlinePreferences` 传递到 JSON/multipart 大纲请求。后端集中规范化页数、将硬约束加入预览和实际提示词，并由 `OutlineService` 在解析模型输出后校验页数及页面类型。

**Tech Stack:** Vue 3、TypeScript、Pinia、Axios、Django、Python `unittest`。

## Global Constraints

- 页数包含封面和总结页。
- `1` 页只能是封面；`2` 页只能是封面和总结；`3-15` 页必须是封面、内容页、总结。
- `auto` 保持现有自动策略。
- 不改变文案生成接口和已有历史大纲。

---

### Task 1: 添加前端页数状态和参数控件

**Files:**
- Modify: `frontend/src/stores/generator.ts`
- Modify: `frontend/src/components/workspace/OutlineOptions.vue`
- Modify: `frontend/src/features/generationOptions.ts`

**Interfaces:**
- Produces `GeneratorState.outlinePageCount: 'auto' | number`.
- Produces `OutlinePreferences.page_count: 'auto' | number`.

- [ ] **Step 1: Write the failing frontend assertions**

在 `frontend/tests/studio/outline.test.ts` 增加断言，验证大纲请求的偏好对象包含 `page_count`，并在测试中设置 `store.outlinePageCount = 5`。

- [ ] **Step 2: Run the focused test**

Run: `cd frontend; npm run test -- --run tests/studio/outline.test.ts`

Expected: FAIL because the store and preferences object do not expose `page_count`.

- [ ] **Step 3: Add the persisted state and selector**

在 `GeneratorState` 中增加 `outlinePageCount`；默认值为 `'auto'`，从 `localStorage` 恢复时只接受 `'auto'` 或 `1-15` 整数；加入 `saveState` 和 `reset` 的保留逻辑。`OutlineOptions.vue` 增加“页数”下拉框，选项为“自动”和 1 至 15。

- [ ] **Step 4: Include the value in outline preferences**

扩展 `OutlinePreferences` 和 `outlinePreferences()`，输出 `page_count`，供请求和提示词共同使用。

- [ ] **Step 5: Run the focused frontend tests**

Run: `cd frontend; npm run test -- --run tests/studio/outline.test.ts`

Expected: PASS.

### Task 2: 贯通 JSON 和 multipart 大纲请求

**Files:**
- Modify: `frontend/src/api/outline.ts`
- Modify: `frontend/src/composables/useOutlineGeneration.ts`
- Modify: `frontend/src/api/types.ts` if `OutlineResponse` needs a page-count field.

**Interfaces:**
- `generateOutline()` sends `page_count` in both `FormData` and JSON.
- `useOutlineGeneration.start()` passes the same `OutlinePreferences` object to `generateOutline()`.

- [ ] **Step 1: Extend the API request test**

在 `frontend/tests/studio/outline.test.ts` 增加对 `generateOutline()` JSON 分支和 multipart 分支的请求体断言，确认 `page_count` 被发送。

- [ ] **Step 2: Run the focused test to verify failure**

Run: `cd frontend; npm run test -- --run tests/studio/outline.test.ts`

Expected: FAIL because the API helper currently serializes only existing fields.

- [ ] **Step 3: Serialize page_count in both request formats**

保留现有 `OutlinePreferences` 展开逻辑，确保包含 `page_count`；为 multipart 使用字符串化值，JSON 使用原始规范化值。

- [ ] **Step 4: Validate the generated request**

Run: `cd frontend; npm run test -- --run tests/studio/outline.test.ts`

Expected: PASS.

### Task 3: 后端页数规范化和提示词约束

**Files:**
- Modify: `backend/generation/outline_prompt.py`
- Modify: `backend/generation/views.py`
- Modify: `backend/generation/outline_inspection.py`
- Create: `backend/generation/page_count.py`
- Test: `backend/generation/test_page_count.py`

**Interfaces:**
- Create `normalize_page_count(value) -> str | int`.
- Create `page_count_instruction(page_count) -> str`.
- `preferences(data)` returns normalized `page_count`.

- [ ] **Step 1: Write backend unit tests**

覆盖 `auto`、`1`、`2`、`5`、`15`，以及 `0`、`16`、`1.5`、空字符串和未知字符串的拒绝。

- [ ] **Step 2: Run the tests to verify failure**

Run: `.venv\Scripts\python.exe backend\manage.py test generation.test_page_count`

Expected: FAIL because the normalizer does not exist.

- [ ] **Step 3: Implement the normalizer and prompt instruction**

固定页数返回整数；空值和 `auto` 返回 `'auto'`。提示词明确页面总数及封面/总结规则。

- [ ] **Step 4: Wire preview and actual request parsing**

让 `preferences(data)` 统一处理 `page_count`，并让 `build_outline_prompt()`追加同一条页数规则。这样实际请求和 `/api/outline/preview` 自动共享约束。

- [ ] **Step 5: Persist the normalized value**

让 `generate_outline()` 创建 `OutlineRun` 时把包含 `page_count` 的 options 存进 `preferences`。

- [ ] **Step 6: Run focused backend tests**

Run: `.venv\Scripts\python.exe backend\manage.py test generation.test_page_count generation.test_outline_inspection`

Expected: PASS.

### Task 4: 服务端严格校验模型返回页数

**Files:**
- Modify: `backend/generation/services/outline.py`
- Modify: `backend/generation/views.py`
- Test: `backend/generation/test_page_count.py`
- Test: `backend/generation/test_outline_inspection.py`

**Interfaces:**
- Add `validate_page_count(pages, page_count) -> None`.
- `OutlineService.generate_outline()` raises a user-facing validation error result when fixed-count output is invalid.

- [ ] **Step 1: Add failing parser-validation tests**

测试固定页数 1、2、5、15 的合法页面类型；测试页数不符、1 页非封面、2 页缺总结、3 页缺内容或缺总结均失败；自动模式允许现有结果。

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python.exe backend\manage.py test generation.test_page_count`

Expected: FAIL because service parsing currently accepts any number and type.

- [ ] **Step 3: Implement validation after `_parse_outline()`**

校验页数与页面类型，失败时返回 `success: False` 和明确错误；不要截断、补造或重排模型页面。

- [ ] **Step 4: Preserve inspectable failed runs**

确保 `generate_outline()` 仍将 `OutlineRun.status` 标记为 failed，并返回现有错误包装结构。

- [ ] **Step 5: Run backend generation tests**

Run: `.venv\Scripts\python.exe backend\manage.py test generation.test_page_count generation.test_outline_inspection generation.test_reference_roles`

Expected: PASS.

### Task 5: 前端固定页数响应保护和回归验证

**Files:**
- Modify: `frontend/src/composables/useOutlineGeneration.ts`
- Modify: `frontend/tests/studio/outline.test.ts`

**Interfaces:**
- Fixed page-count responses that do not match the requested count do not overwrite the current outline.

- [ ] **Step 1: Add the failing response-mismatch test**

设置 `outlinePageCount = 5`，让 mock 返回 4 页，断言 `start()` 返回 false、原有大纲保持不变并出现错误。

- [ ] **Step 2: Implement client-side guard**

在 `response.success` 后、`store.setOutline()` 前校验固定页数；错误信息使用“模型未按指定页数生成，请重试”。

- [ ] **Step 3: Run frontend tests and typecheck**

Run: `cd frontend; npm run test -- --run tests/studio/outline.test.ts; npm run typecheck`

Expected: PASS.

### Task 6: 全量验证和变更检查

**Files:**
- No new source files.

- [ ] **Step 1: Run backend focused suite**

Run: `.venv\Scripts\python.exe backend\manage.py test generation.test_page_count generation.test_outline_inspection generation.test_styles generation.test_reference_roles`

Expected: PASS.

- [ ] **Step 2: Run frontend focused and type checks**

Run: `cd frontend; npm run test -- --run tests/studio/outline.test.ts tests/studio/studio.test.ts; npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Check the diff**

Run: `git diff --check`

Expected: no output.
