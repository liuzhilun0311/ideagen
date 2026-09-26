# 提示词目录、样图与多平台生成一致性实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复单页布局样图链路，整理布局与图片风格目录，并让发布平台、获客目标及其他生成选项在大纲、文案、图片三个阶段保持可追溯的一致性。

**Architecture:** 保持“布局负责排版、风格负责视觉、平台与目标负责增长适配”的边界。后端新增统一的生成上下文与提示词审计记录，前端使用同一份目录元数据展示样图、分类和最终生效设置；通过兼容 ID 保留历史记录和旧提示词模板的可用性。

**Tech Stack:** Django/Python、Vue 3、TypeScript、Pinia、Vitest、Django TestCase、Vite。

## Global Constraints

- 布局不能包含摄影、漫画、手绘等视觉媒介描述；风格不能承担封面、清单、对比等排版职责。
- 发布平台和获客目标必须作为规则进入大纲、文案和图片生成上下文，但不得渲染为图片可见文字。
- 历史布局、风格 ID 和旧提示词模板必须保持兼容。
- 样图缺失不得阻塞生成，但必须显示明确缺失状态。
- 手动选择必须优先于自动推荐。
- 只使用本地内置样图或用户参考图，不依赖临时外链。

---

### Task 1: 建立布局样图单一数据契约

**Files:**
- Modify: `backend/prompts/catalog_defaults.py`
- Modify: `backend/prompts/catalog.py`
- Modify: `frontend/src/features/promptCatalog.ts`
- Modify: `frontend/src/components/workspace/LayoutSelect.vue`
- Create: `backend/prompts/test_layout_previews.py`
- Test: `backend/prompts/test_catalog.py`

**Interfaces:**
- `builtin_entries(current_base=False)` 为每个内置 `image.layout` 提供 `metadata.preview`、`metadata.preview_alt`、`metadata.summary`。
- `layoutPreviewUrl(metadata)` 只返回经过本地目录校验的布局样图地址。
- 新增 `validate_builtin_layout_previews()`，返回缺失样图标识列表；测试和启动/目录读取路径可调用。

- [ ] **Step 1: 写失败测试，覆盖目录样图契约**

```python
from pathlib import Path
from django.test import SimpleTestCase
from prompts.catalog_defaults import builtin_entries


class LayoutPreviewContractTests(SimpleTestCase):
    def test_every_builtin_layout_has_preview_metadata_and_local_asset(self):
        root = Path(__file__).resolve().parents[2] / "frontend" / "public" / "assets" / "layouts"
        layouts = [
            item for item in builtin_entries(current_base=False)
            if item["module"] == "image" and item["category"] == "layout"
            and item["legacy_value"] != "自动"
        ]
        self.assertTrue(layouts)
        for item in layouts:
            preview = item["metadata"].get("preview")
            self.assertTrue(preview, item["id"])
            self.assertTrue(item["metadata"].get("preview_alt"), item["id"])
            self.assertTrue((root / f"{preview}.png").is_file(), item["id"])
```

- [ ] **Step 2: 运行测试确认当前契约缺失或失败**

Run: `..\.venv\Scripts\python.exe manage.py test prompts.test_layout_previews -v 2` from `F:\ai_tools_projects\IdeaGen\backend`

Expected: FAIL for at least one new layout metadata or asset mapping.

- [ ] **Step 3: 实现统一元数据和校验函数**

在 `backend/prompts/catalog_defaults.py` 的布局元数据中补充 `preview_alt`，在 `backend/prompts/catalog.py` 增加：

```python
def validate_builtin_layout_previews():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "generation" / ".." / ".." / "frontend" / "public" / "assets" / "layouts"
    missing = []
    for item in builtin_entries(current_base=False):
        if item["module"] != "image" or item["category"] != "layout" or item["legacy_value"] == "自动":
            continue
        preview = (item.get("metadata") or {}).get("preview")
        if not preview or not (root / f"{preview}.png").is_file():
            missing.append(item["id"])
    return missing
```

目录序列化时保留 `preview_alt`，前端 `layoutPreviewUrl` 仅构造 `/assets/layouts/<preview>.png`，并由 `LayoutSelect.vue` 根据加载错误显示“样图文件不存在”。

- [ ] **Step 4: 运行测试确认通过**

Run: `..\.venv\Scripts\python.exe manage.py test prompts.test_layout_previews prompts.test_catalog -v 2`

Expected: PASS.

- [ ] **Step 5: 运行前端目录测试**

Run: `pnpm test --run tests/studio/catalogPreview.test.ts` from `F:\ai_tools_projects\IdeaGen\frontend`

Expected: PASS.

### Task 2: 重整布局和图片风格目录元数据

**Files:**
- Modify: `backend/prompts/catalog_defaults.py`
- Modify: `backend/generation/style_catalog.json`
- Modify: `frontend/src/features/promptCatalog.ts`
- Modify: `frontend/src/features/styles/catalog.ts`
- Modify: `frontend/src/components/workspace/LayoutSelect.vue`
- Modify: `frontend/src/components/workspace/StyleSelect.vue`
- Test: `backend/prompts/test_scene_descriptions.py`
- Test: `frontend/tests/studio/catalogPreview.test.ts`

**Interfaces:**
- 布局 metadata 增加 `layout_group`，取值为 `role`、`information`、`growth`、`media`。
- 风格 metadata 保留 `group`，新增可选 `media`、`mood`、`business_use`，不改变现有 `id`。
- 前端显示名称、摘要、适用场景和样图，推荐仍通过平台/目标元数据完成。

- [ ] **Step 1: 写失败测试，覆盖分层和旧 ID 兼容**

```python
from django.test import SimpleTestCase
from prompts.catalog_defaults import builtin_entries


class CatalogGroupingTests(SimpleTestCase):
    def test_layouts_have_one_structural_group_without_changing_legacy_ids(self):
        layouts = [
            item for item in builtin_entries(current_base=False)
            if item["module"] == "image" and item["category"] == "layout"
            and item["legacy_value"] != "自动"
        ]
        allowed = {"role", "information", "growth", "media"}
        self.assertTrue(all(item["metadata"].get("layout_group") in allowed for item in layouts))
        self.assertIn("image.layout.hook-cover", {item["id"] for item in layouts})
        self.assertIn("image.layout.cover", {item["id"] for item in layouts})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `..\.venv\Scripts\python.exe manage.py test prompts.test_scene_descriptions -v 2`

Expected: FAIL because new grouping metadata is not present.

- [ ] **Step 3: 增加结构分组和风格维度元数据**

为基础布局、新增长布局补充 `layout_group`；为风格目录补充 `media`、`mood`、`business_use`，保持 `id`、`legacy_value`、`preview` 和现有名称兼容。前端目录卡片增加分组筛选和适用摘要，但不把分组名称写入生成提示词。

- [ ] **Step 4: 运行后端和前端目录测试**

Run:

```powershell
..\.venv\Scripts\python.exe manage.py test prompts.test_scene_descriptions generation.test_styles -v 2
pnpm test --run tests/studio/catalogPreview.test.ts tests/studio/imageStyle.test.ts
```

Expected: PASS.

### Task 3: 统一生成上下文和增长规则

**Files:**
- Create: `backend/generation/generation_context.py`
- Modify: `backend/generation/outline_prompt.py`
- Modify: `backend/generation/copy_prompt.py`
- Modify: `backend/generation/styles.py`
- Modify: `backend/generation/views.py`
- Modify: `backend/generation/prompts/image_prompt.txt`
- Test: `backend/generation/test_generation_context.py`
- Test: `backend/generation/test_prompt_consistency.py`

**Interfaces:**
- `build_generation_context(topic, outline, generation_preferences, copy_preferences, image_style, page=None) -> dict`
- `growth_prompt_rules(platform, goal, phase) -> str`, where `phase` is `outline`, `copy`, or `image`.
- `audit_context(context) -> list[dict]`, each item includes `phase`, `field`, `value`, and `applied`.

- [ ] **Step 1: 写失败测试，确认平台/目标进入三个阶段**

```python
from django.test import SimpleTestCase
from generation.generation_context import build_generation_context


class GenerationContextTests(SimpleTestCase):
    def test_context_keeps_platform_and_goal_for_all_generation_phases(self):
        context = build_generation_context(
            topic="AI 工具获客",
            outline="单页布局：强钩子封面\n上图文字：提高效率",
            generation_preferences={"platform": "douyin", "goal": "follow"},
            copy_preferences={"style": "简洁干货"},
            image_style={"preset": "infographic", "notes": ""},
        )
        self.assertEqual(context["growth"], {"platform": "douyin", "goal": "follow"})
        self.assertIn("douyin", context["prompt_rules"]["outline"])
        self.assertIn("douyin", context["prompt_rules"]["copy"])
        self.assertIn("douyin", context["prompt_rules"]["image"])
```

- [ ] **Step 2: 运行测试确认模块不存在**

Run: `..\.venv\Scripts\python.exe manage.py test generation.test_generation_context -v 2`

Expected: FAIL with import or missing function error.

- [ ] **Step 3: 实现统一上下文和阶段规则**

`generation_context.py` 负责规范化已有选项、保留用户选择和最终选择、生成三个阶段的增长规则，并输出审计条目。规则内容必须明确：

- 大纲：平台内容结构、页序和 CTA 方向。
- 文案：开头节奏、段落密度、语气和行动号召。
- 图片：首屏重点、信息密度、安全区、主体位置和 CTA 视觉优先级。

规则中禁止要求图片渲染平台名、获客目标名或内部参数。

- [ ] **Step 4: 接入大纲、文案和图片提示词**

大纲提示词继续保留现有规则并改为读取上下文；`build_copy_prompt` 加入 copy 阶段规则；`style_prompt`/`format_image_prompt` 加入 image 阶段规则。保留旧模板格式化兼容，模板不支持新字段时追加规则文本而不是抛出错误。

- [ ] **Step 5: 运行提示词一致性测试**

Run:

```powershell
..\.venv\Scripts\python.exe manage.py test generation.test_generation_context generation.test_prompt_consistency generation.test_platform_recommendations -v 2
```

Expected: PASS.

### Task 4: 保存最终生效设置和提示词审计

**Files:**
- Modify: `backend/history/models.py`
- Create: `backend/history/migrations/0005_generation_audit.py`
- Modify: `backend/history/services.py`
- Modify: `backend/generation/views.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/components/workspace/GenerationPanel.vue`
- Create: `frontend/src/components/workspace/PromptAuditSummary.vue`
- Test: `backend/history/test_generation_audit.py`
- Test: `frontend/tests/studio/promptAudit.test.ts`

**Interfaces:**
- `HistoryRecord.generation_audit` is a JSON object containing `context`, `effective`, and `prompts`.
- `prompts` entries contain `phase`, `prompt_name`, `used_fields`, `rules`, and `created_at`.
- `PromptAuditSummary` receives the audit object and renders selected values plus phase coverage.

- [ ] **Step 1: 写失败测试，覆盖历史记录审计字段**

```python
from django.test import TestCase
from history.models import HistoryRecord


class GenerationAuditTests(TestCase):
    def test_history_record_accepts_generation_audit(self):
        record = HistoryRecord.objects.create(
            user_id="audit-user",
            topic="测试主题",
            outline={"pages": []},
            generation_audit={"effective": {"platform": "douyin"}},
        )
        record.refresh_from_db()
        self.assertEqual(record.generation_audit["effective"]["platform"], "douyin")
```

- [ ] **Step 2: 运行测试确认字段不存在**

Run: `..\.venv\Scripts\python.exe manage.py test history.test_generation_audit -v 2`

Expected: FAIL because `generation_audit` is not yet a model field.

- [ ] **Step 3: 增加 JSON 字段和迁移**

为 `HistoryRecord` 增加 `generation_audit = models.JSONField(default=dict, blank=True)`，创建迁移并通过历史服务的创建、更新和序列化接口返回。

- [ ] **Step 4: 在生成流程写入审计信息**

大纲生成完成时记录最终大纲设置和增长推荐；文案生成时追加 copy 阶段使用的字段；图片生成和重试时追加 image 阶段的布局、风格、参考图和增长规则。更新必须按记录 ID 合并 JSON，不能覆盖其他阶段审计。

- [ ] **Step 5: 增加前端审计摘要**

在工作区生成设置区域增加“本次生效设置”摘要，至少显示平台、获客目标、最终布局、最终风格以及是否自动推荐。提供查看完整提示词审计的入口，但不默认展开大段提示词文本。

- [ ] **Step 6: 运行历史和前端测试**

Run:

```powershell
..\.venv\Scripts\python.exe manage.py test history generation -v 1
pnpm test --run tests/studio/promptAudit.test.ts tests/studio/workspace.test.ts
```

Expected: 新增测试和相关既有测试通过；若存在既有基线失败，记录具体失败用例，不回滚无关改动。

### Task 5: 完成前端样图状态和目录交互

**Files:**
- Modify: `frontend/src/components/workspace/LayoutSelect.vue`
- Modify: `frontend/src/components/workspace/StyleSelect.vue`
- Modify: `frontend/src/features/promptCatalog.ts`
- Modify: `frontend/src/features/styles/catalog.ts`
- Test: `frontend/tests/studio/catalogPreview.test.ts`
- Test: `frontend/tests/studio/imageStyle.test.ts`

**Interfaces:**
- 布局和风格卡片必须区分 `builtin`、`custom`、`missing` 样图来源。
- 缺失图片显示“暂无样图”与可理解的原因，不显示空白区域。
- 有效图片支持点击放大预览。

- [ ] **Step 1: 写失败测试，覆盖布局与风格样图状态**

```ts
import { describe, expect, it } from 'vitest'
import { layoutPreviewLabel, layoutPreviewUrl } from '../../src/features/promptCatalog'
import { stylePreviewLabel, stylePreviewUrl } from '../../src/features/styles/catalog'

describe('catalog preview states', () => {
  it('returns a local preview URL for a valid layout preview', () => {
    expect(layoutPreviewUrl({ preview: 'hook-cover' })).toBe('/assets/layouts/hook-cover.png')
  })

  it('marks a style without preview as missing', () => {
    expect(stylePreviewUrl({}).source).toBe('missing')
    expect(stylePreviewLabel({ name: '自定义风格', metadata: {} })).toBe('暂无样图')
  })
})
```

- [ ] **Step 2: 运行前端测试确认现状**

Run: `pnpm test --run tests/studio/catalogPreview.test.ts tests/studio/imageStyle.test.ts`

Expected: 至少新增状态断言失败。

- [ ] **Step 3: 实现统一样图状态**

布局和风格均使用明确的 preview state；图片加载失败后不再只隐藏 `img`，而是显示缺失状态。放大预览只在图片有效时启用。

- [ ] **Step 4: 运行前端测试和类型检查**

Run:

```powershell
pnpm test --run tests/studio/catalogPreview.test.ts tests/studio/imageStyle.test.ts
pnpm run typecheck
```

Expected: PASS.

### Task 6: 端到端回归与交付检查

**Files:**
- Modify: `docs/superpowers/verification/2026-09-26-prompt-catalog-consistency.md`

- [ ] **Step 1: 运行后端定向测试**

Run:

```powershell
..\.venv\Scripts\python.exe manage.py test prompts generation history -v 1
```

Expected: 记录通过数量和仍存在的基线失败；不能把未验证的结果写成通过。

- [ ] **Step 2: 运行前端定向测试、类型检查和构建**

Run:

```powershell
pnpm test --run tests/studio/catalogPreview.test.ts tests/studio/imageStyle.test.ts tests/studio/promptAudit.test.ts tests/studio/platformRecommendations.test.ts
pnpm run typecheck
pnpm run build
```

Expected: 定向测试、类型检查和构建通过。

- [ ] **Step 3: 检查样图文件和工作区差异**

Run:

```powershell
git diff --check
Get-ChildItem frontend/public/assets/layouts -File
git status --short
```

Expected: 所有布局样图存在；没有新增空文件或空样图路径；只保留本次相关变更和用户已有改动。

- [ ] **Step 4: 更新验证报告**

在验证文档中记录：

- 布局和风格目录总数。
- 样图完整性结果。
- 平台和目标在三个阶段提示词中的覆盖结果。
- 手动选择覆盖自动推荐的测试结果。
- 后端和前端测试的准确通过/失败情况。
