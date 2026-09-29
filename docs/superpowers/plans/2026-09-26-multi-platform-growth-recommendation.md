# 多平台获客内容推荐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有大纲、图片风格和页面布局能力之上，增加面向小红书、抖音、公众号的多平台获客推荐，并保证用户选择优先、历史数据兼容、样图可理解、文案与图片可校验。

**Architecture:** 使用一个轻量的“发布平台 + 获客目标”生成偏好对象贯穿大纲生成、推荐协议和前端恢复流程；布局与风格继续使用现有目录，但补充平台、目标、比例、文字密度和样图元数据。推荐由模型建议和本地确定性规则共同提供，所有结果先经过目录校验，再由前端按字段应用。文案与图片一致性检查作为独立的结果诊断能力，不修改用户正文。

**Tech Stack:** Django/Python、Django JSONField、Vue 3、Pinia、TypeScript、Vitest、Python unittest/Django TestCase、pnpm。

## Global Constraints

- 默认平台和获客目标必须是“自动推荐”，空值等价于自动推荐。
- 用户明确选择的布局、风格、比例和模型始终优先于自动推荐。
- 新字段允许为空，旧记录读取不到平台和目标时继续使用自动推荐。
- 不拆分为三套完全独立的小红书、抖音、公众号生成系统。
- 不自动改写用户正文中的事实、数据、产品信息或结论。
- 推荐值必须通过当前启用目录校验；无效推荐必须回退到可用通用条目。
- 样图缺失必须显示明确占位，不得静默显示空白区域。
- 所有新增代码保持 ASCII 标识符；用户可见中文沿用项目现有文案。
- 每个任务完成后运行该任务列出的测试，再提交独立 commit。

---

## 文件地图

| 文件 | 责任 |
| --- | --- |
| `backend/generation/platform_recommendations.py` | 平台、获客目标枚举、元数据匹配和确定性兜底 |
| `backend/generation/recommendations.py` | 扩展模型推荐提示词与推荐协议解析 |
| `backend/generation/outline_prompt.py` | 把平台和获客目标注入大纲提示词 |
| `backend/generation/services/outline.py` | 校验并返回标准化平台推荐 |
| `backend/generation/styles.py` | 读取样式元数据并参与平台/目标推荐 |
| `backend/generation/structure.py` | 扩展可用页面布局说明和页面布局解析 |
| `backend/generation/style_catalog.json` | 增加营销场景图片风格和元数据 |
| `backend/prompts/catalog_defaults.py` | 增加获客型页面布局默认目录 |
| `backend/prompts/catalog.py` | 允许目录保存平台、目标、密度和样图元数据 |
| `backend/generation/test_platform_recommendations.py` | 平台推荐和兜底测试 |
| `backend/generation/test_recommendations.py` | 推荐协议解析和优先级测试 |
| `backend/generation/test_outline_prompt.py` | 大纲提示词平台约束测试 |
| `backend/generation/test_consistency.py` | 文案与图片一致性检查测试 |
| `frontend/src/features/generationOptions.ts` | 前端平台、目标类型和请求偏好 |
| `frontend/src/stores/generator.ts` | 平台、目标状态和本地持久化 |
| `frontend/src/api/outline.ts` | 大纲请求/响应类型 |
| `frontend/src/composables/useOutlineGeneration.ts` | 应用推荐和用户选择优先逻辑 |
| `frontend/src/composables/useGenerationRestore.ts` | 历史记录恢复平台和目标 |
| `frontend/src/composables/useHistoryDraft.ts` | 历史草稿恢复平台和目标 |
| `frontend/src/components/workspace/OutlineOptions.vue` | 平台和获客目标选择器 |
| `frontend/src/components/workspace/RecommendationSummary.vue` | 推荐组合和理由展示 |
| `frontend/src/components/workspace/StyleSelect.vue` | 风格样图、缺图占位和放大预览 |
| `frontend/src/components/workspace/LayoutSelect.vue` | 页面布局卡片、总结和放大预览 |
| `frontend/src/api/consistency.ts` | 一致性检查 API |
| `frontend/src/views/WorkspaceView.vue` | 结果页展示一致性诊断 |
| `frontend/tests/studio/platformRecommendations.test.ts` | 前端平台/目标状态和推荐应用测试 |
| `frontend/tests/studio/catalogPreview.test.ts` | 布局/风格样图展示测试 |

## Task 1: 建立平台与获客目标数据契约

**Files:**
- Create: `backend/generation/platform_recommendations.py`
- Modify: `backend/generation/outline_prompt.py`
- Modify: `frontend/src/features/generationOptions.ts`
- Modify: `frontend/src/api/outline.ts`
- Test: `backend/generation/test_platform_recommendations.py`
- Test: `frontend/tests/studio/platformRecommendations.test.ts`

**Interfaces:**
- Backend `normalize_growth_preferences(data: dict) -> dict` 返回：
  `{"platform": str, "goal": str, "audience": str, "audience_detail": str, "tone": str, "page_count": "auto"|int, "organization": str}`。
- Backend `fallback_growth_recommendation(topic: str, platform: str, goal: str) -> dict` 返回标准推荐对象。
- Frontend `GrowthPlatform = 'auto' | 'xiaohongshu' | 'douyin' | 'wechat' | 'multi'`。
- Frontend `GrowthGoal = 'auto' | 'follow' | 'product' | 'inquiry' | 'conversion' | 'brand' | 'engagement'`。
- Frontend `OutlinePreferences` 增加 `platform: GrowthPlatform` 与 `goal: GrowthGoal`。

- [ ] **Step 1: 写失败测试，锁定枚举和默认值**

```python
def test_empty_preferences_default_to_auto(self):
    self.assertEqual(
        normalize_growth_preferences({})["platform"],
        "auto",
    )
    self.assertEqual(
        normalize_growth_preferences({})["goal"],
        "auto",
    )

def test_unknown_platform_is_rejected(self):
    with self.assertRaises(ValueError):
        normalize_growth_preferences({"platform": "unknown"})
```

```ts
it('serializes growth preferences with automatic defaults', () => {
  expect(outlinePreferences({
    outlineOrganization: '自动',
    outlineAudience: '自动判断',
    outlineAudienceDetail: '',
    outlineTone: '自动匹配',
    outlinePageCount: 'auto',
    outlinePlatform: 'auto',
    outlineGoal: 'auto',
  }).platform).toBe('auto')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python manage.py test generation.test_platform_recommendations -v 2`

Expected: FAIL because the normalizer and new preference fields do not exist.

Run: `pnpm --dir frontend test -- platformRecommendations.test.ts`

Expected: FAIL because the frontend preference type and serializer do not expose platform.

- [ ] **Step 3: 实现标准化函数和前端类型**

在 `platform_recommendations.py` 定义固定集合：

```python
PLATFORMS = {"auto", "xiaohongshu", "douyin", "wechat", "multi"}
GOALS = {"auto", "follow", "product", "inquiry", "conversion", "brand", "engagement"}
```

`normalize_growth_preferences` 对空值使用 `auto`，对未知值抛出 `ValueError`，并复用现有大纲偏好标准化逻辑。

在 `generationOptions.ts` 增加平台、目标类型、显示名称映射和 `outlinePreferences` 字段。

- [ ] **Step 4: 把平台和目标注入大纲提示词**

在 `outline_prompt.py` 的 `preferences()` 中读取标准化字段，在 `build_outline_prompt()` 中增加：

```text
发布平台：{platform_name}；获客目标：{goal_name}。
自动推荐时结合主题、受众和内容类型判断；用户指定的平台和目标优先。
不要为了平台适配虚构产品、数据、案例或承诺。
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python manage.py test generation.test_platform_recommendations -v 2`

Expected: PASS.

Run: `pnpm --dir frontend test -- platformRecommendations.test.ts`

Expected: PASS.

- [ ] **Step 6: 提交**

```bash
git add backend/generation/platform_recommendations.py backend/generation/outline_prompt.py frontend/src/features/generationOptions.ts frontend/src/api/outline.ts backend/generation/test_platform_recommendations.py frontend/tests/studio/platformRecommendations.test.ts
git commit -m "feat: add growth platform preference contract"
```

## Task 2: 扩展布局和风格目录元数据

**Files:**
- Modify: `backend/prompts/catalog.py`
- Modify: `backend/prompts/catalog_defaults.py`
- Modify: `backend/generation/structure.py`
- Modify: `backend/generation/style_catalog.json`
- Modify: `frontend/src/features/promptCatalog.ts`
- Modify: `frontend/src/features/styles/catalog.ts`
- Create: `frontend/src/components/workspace/LayoutSelect.vue`
- Test: `backend/prompts/test_catalog_validation.py`
- Test: `frontend/tests/studio/catalogPreview.test.ts`

**Interfaces:**
- 目录元数据字段：`platforms: string[]`、`goals: string[]`、`aspect_ratios: string[]`、`text_density: "low"|"medium"|"high"`、`summary: string`、`preview: string`。
- `LayoutSelect` props：`modelValue: string`、`recommendation?: string`、`disabled?: boolean`；事件：`update:modelValue`。
- `styleCatalog` 项继续通过 `metadata` 暴露预览和场景信息。

- [ ] **Step 1: 写失败测试验证元数据白名单和新增目录**

```python
def test_growth_metadata_is_allowed(self):
    entry = normalize_entry({
        "id": "pain-solution",
        "name": "痛点—方案",
        "content": "先呈现问题，再给出解决路径。",
        "metadata": {
            "platforms": ["xiaohongshu"],
            "goals": ["product"],
            "aspect_ratios": ["3:4"],
            "text_density": "medium",
            "summary": "适合问题到方案的转化内容",
            "preview": "pain-solution.png",
        },
    })
    self.assertEqual(entry["metadata"]["platforms"], ["xiaohongshu"])
```

```ts
it('renders a layout preview or an explicit missing-preview state', () => {
  const text = renderLayoutCard({ id: 'pain-solution', name: '痛点—方案', preview: 'pain-solution' })
  expect(text).toContain('痛点—方案')
  expect(text).toMatch(/img|暂无样图/)
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python manage.py test prompts.test_catalog_validation -v 2`

Expected: FAIL because the metadata whitelist and new entries are absent.

Run: `pnpm --dir frontend test -- catalogPreview.test.ts`

Expected: FAIL because `LayoutSelect` does not exist.

- [ ] **Step 3: 扩展目录校验**

在 `backend/prompts/catalog.py` 的 metadata permitted 集合中加入 `platforms`、`goals`、`aspect_ratios`、`text_density`、`summary`。校验数组元素必须为字符串，`text_density` 只能是 `low`、`medium`、`high`，比例必须来自现有参数集合或新目录明确支持的比例。

- [ ] **Step 4: 增加获客型布局和风格**

在 `catalog_defaults.py` 增加 15 个布局，使用稳定 ID：

`hook-cover`、`pain-solution`、`myth-fact`、`before-after`、`case-study`、`product-benefits`、`proof`、`faq`、`data-conclusion`、`quote`、`chapter-divider`、`cta`、`talking-subtitle`、`product-demo`、`comment-proof`。

在 `style_catalog.json` 增加 12 个风格，使用稳定 ID：

`brand-commercial`、`editorial-premium`、`ugc-lifestyle`、`product-detail`、`sales-poster`、`talking-cover`、`chat-proof`、`product-3d`、`tech-brand`、`high-contrast-promo`、`knowledge-card`、`case-documentary`。

每个新增条目都提供平台、目标、比例、密度、总结和样图文件名；样图暂时缺失时仍保留 `preview` 字段，并由前端显示占位。

- [ ] **Step 5: 增加布局选择组件**

`LayoutSelect.vue` 使用目录条目渲染可搜索卡片，卡片内容包括名称、总结、适用平台、适用目标和样图。点击样图打开原图预览；图片加载失败时切换到“暂无样图”占位。选择卡片只触发 `update:modelValue`，不改动风格或宽高比。

- [ ] **Step 6: 更新前端目录回退**

在 `promptCatalog.ts` 回退布局列表加入新增布局；在 `styles/catalog.ts` 映射新增 metadata，保留用户自定义 `reference_asset_id` 的预览优先级。

- [ ] **Step 7: 运行测试确认通过**

Run: `python manage.py test prompts.test_catalog_validation generation.test_catalog_integration -v 2`

Expected: PASS.

Run: `pnpm --dir frontend test -- catalogPreview.test.ts`

Expected: PASS.

- [ ] **Step 8: 提交**

```bash
git add backend/prompts/catalog.py backend/prompts/catalog_defaults.py backend/generation/structure.py backend/generation/style_catalog.json frontend/src/features/promptCatalog.ts frontend/src/features/styles/catalog.ts frontend/src/components/workspace/LayoutSelect.vue backend/prompts/test_catalog_validation.py frontend/tests/studio/catalogPreview.test.ts
git commit -m "feat: expand growth layout and style catalogs"
```

## Task 3: 实现平台感知推荐和模型协议

**Files:**
- Modify: `backend/generation/platform_recommendations.py`
- Modify: `backend/generation/recommendations.py`
- Modify: `backend/generation/styles.py`
- Modify: `backend/generation/structure.py`
- Modify: `backend/generation/services/outline.py`
- Test: `backend/generation/test_platform_recommendations.py`
- Test: `backend/generation/test_recommendations.py`

**Interfaces:**
- `recommend_growth(topic: str, platform: str, goal: str, available_layouts: list, available_styles: list) -> dict`
- `normalize_growth_recommendation(value: dict, available_layouts: list, available_styles: list) -> dict | None`
- 标准推荐对象字段：`platform`、`goal`、`layout`、`image_style`、`aspect_ratio`、`content_structure`、`reason`。

- [ ] **Step 1: 写失败测试覆盖平台组合和用户优先级**

```python
def test_douyin_inquiry_prefers_vertical_hook_and_cta(self):
    result = recommend_growth("课程咨询", "douyin", "inquiry", LAYOUTS, STYLES)
    self.assertEqual(result["aspect_ratio"], "9:16")
    self.assertIn(result["layout"], {"hook-cover", "talking-subtitle", "cta"})
    self.assertIn("私信", result["reason"])

def test_invalid_model_ids_are_removed(self):
    result = normalize_growth_recommendation(
        {"layout": "missing", "image_style": "missing", "platform": "wechat", "goal": "brand"},
        LAYOUTS,
        STYLES,
    )
    self.assertIsNone(result)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python manage.py test generation.test_platform_recommendations generation.test_recommendations -v 2`

Expected: FAIL because the platform matcher and expanded protocol do not exist.

- [ ] **Step 3: 实现确定性推荐**

在 `platform_recommendations.py` 中使用目录 metadata 计算匹配分：

```python
score = (
    4 * int(platform in item["platforms"] or "multi" in item["platforms"]) +
    4 * int(goal in item["goals"] or "auto" in item["goals"]) +
    2 * int(aspect_ratio in item["aspect_ratios"]) +
    1 * int(topic_keyword_matches(item, topic))
)
```

平台默认比例：小红书 `3:4`，抖音 `9:16`，公众号 `4:3`，通用多平台 `3:4`。没有命中时选择现有通用布局和 `infographic` 风格。

- [ ] **Step 4: 扩展模型提示和解析**

修改 `recommendations.py`，要求模型输出：

```json
{
  "platform": "xiaohongshu",
  "goal": "product",
  "image_style": "ugc-lifestyle",
  "image_layout": "pain-solution",
  "copy_style": "亲切易懂",
  "copy_structure": "hook_problem_solution_proof_cta",
  "copy_length": "适中",
  "emoji_level": "克制",
  "aspect_ratio": "3:4",
  "reason": "..."
}
```

解析时把 `image_layout` 归一化为 `layout`，校验平台、目标、布局、风格和比例；无效字段从对象中删除，不让非法 ID 进入前端。

- [ ] **Step 5: 合并样式与整套推荐**

在 `services/outline.py` 解析模型结果后调用 `normalize_growth_recommendation`；缺失或无效时调用 `recommend_growth`。保留已有 `style_recommendation` 和 `generation_recommendation` 字段，新增 `growth_recommendation`，避免破坏旧客户端。

在 `structure.py` 和 `styles.py` 的提示词中引用平台目标上下文，但明确平台和目标不改变正文事实。

- [ ] **Step 6: 运行测试确认通过**

Run: `python manage.py test generation.test_platform_recommendations generation.test_recommendations generation.test_outline_prompt generation.test_styles generation.test_layers -v 2`

Expected: PASS.

- [ ] **Step 7: 提交**

```bash
git add backend/generation/platform_recommendations.py backend/generation/recommendations.py backend/generation/styles.py backend/generation/structure.py backend/generation/services/outline.py backend/generation/test_platform_recommendations.py backend/generation/test_recommendations.py
git commit -m "feat: add platform-aware growth recommendations"
```

## Task 4: 接入前端状态、参数和推荐应用

**Files:**
- Modify: `frontend/src/features/generationOptions.ts`
- Modify: `frontend/src/stores/generator.ts`
- Modify: `frontend/src/api/outline.ts`
- Modify: `frontend/src/composables/useOutlineGeneration.ts`
- Modify: `frontend/src/composables/useGenerationRestore.ts`
- Modify: `frontend/src/composables/useHistoryDraft.ts`
- Modify: `frontend/src/components/workspace/OutlineOptions.vue`
- Create: `frontend/src/components/workspace/RecommendationSummary.vue`
- Test: `frontend/tests/studio/platformRecommendations.test.ts`

**Interfaces:**
- Store fields：`outlinePlatform: GrowthPlatform`、`outlineGoal: GrowthGoal`。
- `applyGrowthRecommendation(recommendation: GrowthRecommendation): void`：只修改处于自动状态的字段。
- `RecommendationSummary` props：`recommendation?: GrowthRecommendation`、`disabled?: boolean`；events：`apply`、`apply-layout`、`apply-style`。

- [ ] **Step 1: 写失败测试验证持久化和覆盖规则**

```ts
it('manual platform survives recommendation application', () => {
  store.outlinePlatform = 'xiaohongshu'
  store.outlineGoal = 'auto'
  applyGrowthRecommendation(store, {
    platform: 'douyin',
    goal: 'inquiry',
    layout: 'hook-cover',
    image_style: 'talking-cover',
    aspect_ratio: '9:16',
  })
  expect(store.outlinePlatform).toBe('xiaohongshu')
  expect(store.outlineGoal).toBe('inquiry')
  expect(store.imageAspectRatio).toBe('9:16')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --dir frontend test -- platformRecommendations.test.ts`

Expected: FAIL because store fields and recommendation application are absent.

- [ ] **Step 3: 扩展 store 和请求恢复**

在 `generator.ts` 增加默认值、localStorage 序列化、`reset()` 和 `prepareNewOutline()` 的保留逻辑。`useGenerationRestore.ts` 和 `useHistoryDraft.ts` 从 `outline.generation_preferences` 恢复平台和目标，旧记录回退为 `auto`。

在 `api/outline.ts` 和 `api/types.ts` 增加 `GrowthRecommendation` 与 `growth_recommendation` 响应字段。

- [ ] **Step 4: 增加平台和目标选择器**

在 `OutlineOptions.vue` 增加两个 select：

```vue
<select v-model="store.outlinePlatform">
  <option value="auto">自动推荐</option>
  <option value="xiaohongshu">小红书</option>
  <option value="douyin">抖音</option>
  <option value="wechat">公众号</option>
  <option value="multi">通用多平台</option>
</select>
```

获客目标使用相同结构。选择器旁显示简短说明，不增加营销说明型大卡片。

- [ ] **Step 5: 应用整套推荐**

在 `useOutlineGeneration.ts` 保存 `growth_recommendation`，实现：

```ts
if (store.outlinePlatform === 'auto') store.outlinePlatform = rec.platform
if (store.outlineGoal === 'auto') store.outlineGoal = rec.goal
if (store.imageStyle.preset === 'auto') store.imageStyle.preset = rec.image_style
if (store.imageAspectRatio === '3:4' && store.outlinePlatform === 'auto') {
  store.imageAspectRatio = rec.aspect_ratio
}
```

页面布局推荐只写入页面仍为“自动”的页面；手动页面保持原值。

- [ ] **Step 6: 增加推荐组合展示**

`RecommendationSummary.vue` 显示平台、目标、布局、风格、比例和理由，并提供图标按钮或清晰的文字操作：

- 应用全部
- 只应用布局
- 只应用风格

组件不直接操作 store，由父级传入事件处理，避免推荐展示组件承担状态管理。

- [ ] **Step 7: 运行测试确认通过**

Run: `pnpm --dir frontend test -- platformRecommendations.test.ts`

Expected: PASS.

Run: `pnpm --dir frontend run typecheck`

Expected: PASS.

- [ ] **Step 8: 提交**

```bash
git add frontend/src/features/generationOptions.ts frontend/src/stores/generator.ts frontend/src/api/outline.ts frontend/src/api/types.ts frontend/src/composables/useOutlineGeneration.ts frontend/src/composables/useGenerationRestore.ts frontend/src/composables/useHistoryDraft.ts frontend/src/components/workspace/OutlineOptions.vue frontend/src/components/workspace/RecommendationSummary.vue frontend/tests/studio/platformRecommendations.test.ts
git commit -m "feat: expose growth platform controls and recommendation summary"
```

## Task 5: 接入布局和风格预览体验

**Files:**
- Modify: `frontend/src/components/workspace/StyleSelect.vue`
- Modify: `frontend/src/components/workspace/ImageStylePicker.vue`
- Modify: `frontend/src/components/workspace/GenerationPanel.vue`
- Modify: `frontend/src/components/workspace/PageStyleTrials.vue`
- Modify: `frontend/src/views/PromptManageView.vue`
- Modify: `frontend/src/features/styles/catalog.ts`
- Test: `frontend/tests/studio/catalogPreview.test.ts`

**Interfaces:**
- `previewAssetUrl(item): string`：统一处理本地样图、自定义参考图和缺失资源。
- 预览弹窗接受 `src`、`alt`、`title`，关闭时恢复焦点。

- [ ] **Step 1: 写失败测试验证样图和缺图占位**

```ts
it('uses a custom reference asset before a built-in preview', () => {
  expect(stylePreview({
    preview: 'ugc-lifestyle',
    previewUrl: '/api/reference-assets/x/image',
  })).toBe('/api/reference-assets/x/image')
})

it('does not render a broken image when preview is missing', () => {
  expect(layoutPreview({ preview: '' })).toContain('暂无样图')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --dir frontend test -- catalogPreview.test.ts`

Expected: FAIL because preview resolution and layout preview are incomplete.

- [ ] **Step 3: 抽取预览 URL 和放大预览**

在 `StyleSelect.vue` 和新布局组件之间共享一个小型 preview helper，优先顺序：

1. 用户自定义 `previewUrl`
2. 目录 `preview`
3. 空值占位

点击缩略图使用原生 `dialog` 打开大图；图片加载失败时显示错误占位和风格/布局总结，不能把卡片高度撑乱。

- [ ] **Step 4: 把布局选择接入工作区**

在页面级试用面板和当前页面设置中使用 `LayoutSelect`，布局选择通过现有 `withLayout()` 更新页面内容，风格选择继续使用 `StyleSelect`。布局和风格的样图、总结和适用场景使用同一套卡片密度。

- [ ] **Step 5: 更新提示词管理预览**

在 `PromptManageView.vue` 的图片布局和图片风格列表中显示样图、总结和放大入口；自定义风格继续优先显示用户上传参考图。

- [ ] **Step 6: 运行测试确认通过**

Run: `pnpm --dir frontend test -- catalogPreview.test.ts`

Expected: PASS.

Run: `pnpm --dir frontend run typecheck`

Expected: PASS.

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/workspace/StyleSelect.vue frontend/src/components/workspace/ImageStylePicker.vue frontend/src/components/workspace/GenerationPanel.vue frontend/src/components/workspace/PageStyleTrials.vue frontend/src/views/PromptManageView.vue frontend/src/features/styles/catalog.ts frontend/tests/studio/catalogPreview.test.ts
git commit -m "feat: add catalog summaries and enlarged previews"
```

## Task 6: 实现文案与图片一致性检查

**Files:**
- Create: `backend/generation/consistency.py`
- Create: `backend/generation/test_consistency.py`
- Modify: `backend/generation/urls.py`
- Modify: `backend/generation/views.py`
- Create: `frontend/src/api/consistency.ts`
- Modify: `frontend/src/views/WorkspaceView.vue`
- Test: `frontend/tests/studio/workspace.test.ts`

**Interfaces:**
- Backend `check_content_image_consistency(topic: str, pages: list[dict], images: list[dict], growth_preferences: dict) -> dict`
- 返回：
  `{"status": "consistent"|"mostly_consistent"|"risk", "summary": str, "pages": [{"index": int, "status": str, "risks": list[str], "suggestions": list[str]}]}`
- API：`GET /api/generation/consistency/<task_id>`。

- [ ] **Step 1: 写失败测试覆盖三种状态**

```python
def test_consistency_flags_unmentioned_product(self):
    result = check_content_image_consistency(
        "存钱习惯",
        [{"index": 0, "content": "[封面]\n上图文字：存钱习惯"}],
        [{"index": 0, "prompt": "展示一台未在正文出现的咖啡机"}],
        {"goal": "brand"},
    )
    self.assertEqual(result["status"], "risk")
    self.assertTrue(result["pages"][0]["risks"])

def test_matching_page_is_consistent(self):
    result = check_content_image_consistency(
        "存钱习惯",
        [{"index": 0, "content": "[封面]\n上图文字：存钱习惯"}],
        [{"index": 0, "prompt": "围绕存钱习惯的标题页"}],
        {"goal": "follow"},
    )
    self.assertEqual(result["status"], "consistent")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python manage.py test generation.test_consistency -v 2`

Expected: FAIL because the consistency checker and endpoint do not exist.

- [ ] **Step 3: 实现确定性检查器**

从正文提取标题、上图文字、画面描述、数字、产品名和 CTA 关键词；从图片提示词提取主体、数字和 CTA 关键词。比较页面索引、关键词覆盖、平台安全区描述和获客目标。检查器只报告风险，不修改正文、页面或图片提示词。

- [ ] **Step 4: 暴露 API**

在 `views.py` 根据任务记录读取页面和实际图片生成提示词，调用检查器并返回 JSON；任务不存在或无权限时沿用现有错误响应格式。增加 URL 路由并覆盖权限测试。

- [ ] **Step 5: 接入结果页**

在 `WorkspaceView.vue` 增加“文案与图片一致性”入口。默认显示总体状态和摘要，展开后按页显示风险与建议；检查失败时显示“暂时无法检查”，不阻塞图片查看、下载和重新生成。

- [ ] **Step 6: 运行测试确认通过**

Run: `python manage.py test generation.test_consistency generation.tests -v 2`

Expected: PASS.

Run: `pnpm --dir frontend test -- workspace.test.ts`

Expected: PASS.

- [ ] **Step 7: 提交**

```bash
git add backend/generation/consistency.py backend/generation/test_consistency.py backend/generation/urls.py backend/generation/views.py frontend/src/api/consistency.ts frontend/src/views/WorkspaceView.vue frontend/tests/studio/workspace.test.ts
git commit -m "feat: add copy and image consistency checks"
```

## Task 7: 完成端到端验证和兼容回归

**Files:**
- Modify: `frontend/tests/preview/fixtures.ts`
- Modify: `backend/generation/test_catalog_integration.py`
- Modify: `backend/generation/test_styles.py`
- Modify: `backend/generation/test_layers.py`
- Modify: `frontend/tests/studio/outline.test.ts`
- Modify: `frontend/tests/studio/restore.test.ts`
- Create: `docs/superpowers/verification/2026-09-26-multi-platform-growth-recommendation.md`

**Interfaces:**
- 测试 fixture 必须同时覆盖旧记录（无平台/目标）和新记录（有平台/目标）。
- 验证文档记录命令、结果、已知限制和未覆盖的外部模型差异。

- [ ] **Step 1: 增加旧记录兼容 fixture**

在 `frontend/tests/preview/fixtures.ts` 增加不含 `platform`、`goal` 的旧大纲记录，验证恢复为 `auto`；增加含有无效布局/风格推荐的响应，验证前端不崩溃。

- [ ] **Step 2: 增加端到端推荐 fixture**

覆盖：

- 自动推荐通用内容。
- 小红书 + 产品种草。
- 抖音 + 私信咨询。
- 公众号 + 品牌认知。
- 手动布局和风格覆盖推荐。

- [ ] **Step 3: 运行后端全量相关测试**

Run: `python manage.py test generation prompts history -v 2`

Expected: PASS with no migration changes required because preferences remain in JSONField.

- [ ] **Step 4: 运行前端检查**

Run: `pnpm --dir frontend test`

Expected: PASS.

Run: `pnpm --dir frontend run typecheck`

Expected: PASS.

Run: `pnpm --dir frontend run build`

Expected: PASS.

- [ ] **Step 5: 写验证记录**

在 `docs/superpowers/verification/2026-09-26-multi-platform-growth-recommendation.md` 记录：

- 执行日期。
- 后端测试命令和结果。
- 前端测试、类型检查和构建结果。
- 自动推荐、手动覆盖、历史恢复、样图放大、缺图占位和一致性检查的验收结果。
- 外部图片模型输出差异仍需人工抽样检查。

- [ ] **Step 6: 提交**

```bash
git add frontend/tests/preview/fixtures.ts backend/generation/test_catalog_integration.py backend/generation/test_styles.py backend/generation/test_layers.py frontend/tests/studio/outline.test.ts frontend/tests/studio/restore.test.ts docs/superpowers/verification/2026-09-26-multi-platform-growth-recommendation.md
git commit -m "test: verify multi-platform growth recommendations"
```

## Plan Self-Review

- Spec coverage: 平台与目标入口对应 Task 1、Task 4；布局和风格扩展对应 Task 2、Task 5；推荐协议和兜底对应 Task 3；一致性检查对应 Task 6；兼容与验收对应 Task 7。
- Placeholder scan: 计划中没有 `TBD`、`TODO`、未定义的“适当处理”步骤；每个任务都包含具体文件、接口、测试和命令。
- Type consistency: `GrowthPlatform`、`GrowthGoal`、`GrowthRecommendation` 在 Task 1 定义并由 Task 3/4 使用；`normalize_growth_preferences` 和 `recommend_growth` 的参数及返回字段在后续任务保持一致。
- Scope check: 所有任务都围绕同一条生成链路，目录、推荐、UI 和一致性检查通过生成偏好与推荐对象连接，没有拆出互相独立的产品。
- Compatibility check: 保留现有 `style_recommendation` 和 `generation_recommendation` 字段，新字段只增不改；旧记录缺少平台和目标时使用 `auto`。

