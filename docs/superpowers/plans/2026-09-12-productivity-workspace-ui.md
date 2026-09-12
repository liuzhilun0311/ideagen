# Productivity Workspace UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 IdeaGen 的全局布局、首页创作入口和核心工作台，使其更适合高频连续创作，同时保持现有业务逻辑和路由不变。

**Architecture:** 在现有 Vue 3 + Pinia 结构上做局部模板和 CSS 重排，不新增状态管理层。全局样式负责统一设计令牌、页面容器和控件状态；`App.vue`、`HomeView.vue`、`WorkspaceView.vue` 负责页面层级与操作分组；现有工作台子组件继续负责各自业务行为。

**Tech Stack:** Vue 3, TypeScript, Vite, Pinia, Vue Router, lucide-vue-next, CSS, Vitest, vue-tsc

## Global Constraints

- 不改变后端 API、数据模型、生成协议、路由和核心数据流。
- 桌面端使用浅色生产力工具风格，卡片圆角不超过 8px。
- 交互元素最小触摸目标为 44px，并保留可见键盘焦点状态。
- 在 375px、768px、1024px、1440px 下无页面级横向滚动。
- 异步任务必须提供稳定的加载、错误、成功或恢复状态。
- 使用 `lucide-vue-next` 图标，不使用 emoji 作为界面图标。
- 遵守 `prefers-reduced-motion`，不使用导致布局跳动的 hover 缩放。

---

## 文件地图

- Modify: `frontend/src/assets/css/variables.css`：统一颜色、尺寸、层级和阴影设计令牌。
- Modify: `frontend/src/assets/css/base.css`：统一页面容器、标题区、表单和响应式基础规则。
- Modify: `frontend/src/assets/css/components.css`：统一按钮、状态、卡片、标签和通用组件状态。
- Modify: `frontend/src/App.vue`：优化应用导航、账户区、任务状态条和移动端导航行为。
- Modify: `frontend/src/views/HomeView.vue`：整理首页创作入口的结构和操作层级。
- Modify: `frontend/src/views/WorkspaceView.vue`：整理工作台顶部操作、整套生成区和三栏布局。
- Modify: `frontend/src/components/workspace/PageList.vue`：适配左栏页面结构的密度、状态和操作布局。
- Modify: `frontend/src/components/workspace/PageEditor.vue`：强化中间编辑区的当前页层级和操作反馈。
- Modify: `frontend/src/components/workspace/GenerationPanel.vue`：把模型与参数设置收敛为上下文工具。
- Modify: `frontend/src/components/workspace/PostprocessingToolbar.vue`：将后处理设置降级为工具区内的次级操作。
- Test: `frontend/tests/preview/` 或现有 `frontend/tests/studio/`：补充关键布局状态对应的行为回归测试。

## Task 1: 建立全局生产力视觉基础

**Files:**
- Modify: `frontend/src/assets/css/variables.css`
- Modify: `frontend/src/assets/css/base.css`
- Modify: `frontend/src/assets/css/components.css`
- Test: `frontend/src/assets/css/` 无独立测试，使用后续 typecheck/build 和浏览器尺寸检查验证

- [ ] **Step 1: 标记全局样式现状**

运行：

```powershell
rg -n "color:|background:|border-radius:|box-shadow:|@media" frontend/src/assets/css frontend/src/App.vue
```

记录重复的颜色、尺寸和响应式规则，后续仅合并与本次页面相关的规则。

- [ ] **Step 2: 更新设计令牌**

在 `variables.css` 中保留现有变量名，补充页面最大宽度、内容间距、层级和工作台栏宽变量，例如：

```css
:root {
  --content-max-width: 1440px;
  --page-gutter: 32px;
  --section-gap: 24px;
  --z-header: 100;
  --z-mobile-nav: 120;
  --z-dialog: 1000;
  --workspace-sidebar: 224px;
  --workspace-tools: 320px;
}
```

- [ ] **Step 3: 统一基础容器和控件状态**

调整 `base.css` 和 `components.css`，确保 `.layout-main` 使用统一最大宽度与内边距，按钮、输入框、标签和卡片统一高度、圆角、边框和 focus-visible 样式；保留现有选择器兼容旧页面。

- [ ] **Step 4: 添加全局 reduced-motion 和窄屏规则**

确保过渡只作用于颜色、边框、透明度或 transform，禁止 hover 改变布局尺寸；在 700px 以下将页面内边距和卡片间距降级为移动端值。

- [ ] **Step 5: 验证**

运行：

```powershell
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

预期：两个命令均通过。

- [ ] **Step 6: 提交**

```powershell
git add frontend/src/assets/css/variables.css frontend/src/assets/css/base.css frontend/src/assets/css/components.css
git commit -m "style: establish productivity workspace design tokens"
```

## Task 2: 优化应用导航与任务状态

**Files:**
- Modify: `frontend/src/App.vue`
- Test: `frontend/tests/studio/session.test.ts`

- [ ] **Step 1: 增加导航行为回归测试**

覆盖以下行为：当前路由正确标记导航项；移动菜单打开后点击导航关闭；Escape 关闭菜单并恢复菜单按钮焦点；创作任务进行中离开页面仍被阻止。

- [ ] **Step 2: 重排应用头部模板**

保留现有 `navigation`、`navTo`、`handleLogout` 和路由守卫，仅调整模板层级，使品牌、主导航、任务状态和账户区有稳定的三个区域；图标按钮保留 `aria-label` 与 `title`。

- [ ] **Step 3: 优化任务状态条**

让 `creation-status` 在桌面端贴合内容容器，在移动端支持换行；状态文字、返回工作台和关闭提示保持独立焦点目标，避免状态条出现时页面主内容跳动。

- [ ] **Step 4: 优化导航 CSS**

调整 `App.vue` scoped style：桌面端导航间距更紧凑，当前项更明显；移动端抽屉宽度、分隔线、账户区和滚动区域稳定；所有可点击区域不低于 44px。

- [ ] **Step 5: 验证与提交**

运行：

```powershell
pnpm --dir frontend test -- tests/studio/session.test.ts
pnpm --dir frontend typecheck
```

预期：测试和类型检查通过。

```powershell
git add frontend/src/App.vue frontend/tests/studio/session.test.ts
git commit -m "refactor: clarify app navigation and task status"
```

## Task 3: 优化首页创作入口

**Files:**
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/components/home/ComposerInput.vue`
- Modify: `frontend/src/components/workspace/OutlineOptions.vue`
- Test: `frontend/tests/studio/outline.test.ts`

- [ ] **Step 1: 增加首页关键交互回归测试**

覆盖主题为空提交、模型不可用跳转设置提示、生成中取消、灵感替换主题但保留参考内容与设置。

- [ ] **Step 2: 重排首页模板**

保持 `handleGenerate`、`handleCancel`、`chooseInspiration` 和现有数据绑定不变，将页面组织为标题区、主创作区、辅助设置区、状态反馈区和灵感区。主创作区只突出一个开始生成按钮。

- [ ] **Step 3: 调整辅助设置呈现**

将大纲选项、模型选择和提示词检查使用统一的辅助区域样式呈现；不要隐藏现有设置字段和错误信息。

- [ ] **Step 4: 更新首页响应式布局**

桌面端主创作区保持集中宽度，设置区与主题输入形成清晰层级；移动端设置纵向排列，灵感卡片改为可扫描的横向缩略布局。

- [ ] **Step 5: 验证与提交**

运行：

```powershell
pnpm --dir frontend test -- tests/studio/outline.test.ts
pnpm --dir frontend typecheck
```

```powershell
git add frontend/src/views/HomeView.vue frontend/src/components/home/ComposerInput.vue frontend/src/components/workspace/OutlineOptions.vue frontend/tests/studio/outline.test.ts
git commit -m "refactor: streamline creation entry"
```

## Task 4: 重排工作台三栏生产布局

**Files:**
- Modify: `frontend/src/views/WorkspaceView.vue`
- Modify: `frontend/src/components/workspace/PageList.vue`
- Modify: `frontend/src/components/workspace/PageEditor.vue`
- Modify: `frontend/src/components/workspace/GenerationPanel.vue`
- Modify: `frontend/src/components/workspace/PostprocessingToolbar.vue`
- Test: `frontend/tests/studio/workspace.test.ts`, `frontend/tests/studio/generationOptions.test.ts`

- [ ] **Step 1: 增加工作台主流程回归测试**

覆盖图片制作和发布文案模式切换、保存按钮调用、预览按钮在无已生成图片时禁用、生成剩余页面和停止操作的状态。

- [ ] **Step 2: 重排工作台顶部操作**

保留现有事件函数和计算属性，将顶部操作固定为返回/标题、保存状态、新建/导出、保存、预览五组；仅保留预览为最高优先级 CTA。

- [ ] **Step 3: 整理整套生成工具栏**

将整套生成操作、生成取消和后处理设置分组，避免所有按钮平铺在同一视觉层；异步期间显示明确进行中状态并禁用重复提交。

- [ ] **Step 4: 固定三栏布局**

将 `.studio-grid` 改为使用 `var(--workspace-sidebar) minmax(0, 1fr) var(--workspace-tools)`，为左栏、中栏、右栏设置最小宽度和局部滚动边界；发布文案模式继续使用两栏布局。

- [ ] **Step 5: 优化页面列表与编辑区层级**

在 `PageList.vue` 中强化当前页、生成状态和排序操作的区分；在 `PageEditor.vue` 中突出当前页面内容与预览；不改变已有 emit 名称和数据结构。

- [ ] **Step 6: 收敛工具区**

在 `GenerationPanel.vue` 和 `PostprocessingToolbar.vue` 中降低低频参数视觉权重，保留所有控件和事件，确保表单 label、帮助提示和错误状态仍可访问。

- [ ] **Step 7: 优化移动工作台**

保留现有 `mobilePanel`、`settingsDialog` 和底部导航机制，调整为结构、编辑、工具三段式；工具区 dialog 采用稳定全高侧栏，页面主体不得被固定元素遮挡。

- [ ] **Step 8: 验证与提交**

运行：

```powershell
pnpm --dir frontend test -- tests/studio/workspace.test.ts tests/studio/generationOptions.test.ts
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

```powershell
git add frontend/src/views/WorkspaceView.vue frontend/src/components/workspace/PageList.vue frontend/src/components/workspace/PageEditor.vue frontend/src/components/workspace/GenerationPanel.vue frontend/src/components/workspace/PostprocessingToolbar.vue frontend/tests/studio/workspace.test.ts frontend/tests/studio/generationOptions.test.ts
git commit -m "refactor: organize workspace production layout"
```

## Task 5: 全页面响应式与视觉验收

**Files:**
- Modify: `frontend/src/views/HistoryView.vue` only if shared page layout regressions are found
- Modify: `frontend/src/views/PromptManageView.vue` only if shared page layout regressions are found
- Modify: `frontend/src/views/SettingsView.vue` only if shared page layout regressions are found
- Test: existing frontend test suite

- [ ] **Step 1: 运行完整前端验证**

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

- [ ] **Step 2: 检查四档视口**

使用可用浏览器或本地开发服务器检查 `/`、`/workspace`、`/workspace/copy`、`/history`、`/prompts` 和 `/settings` 在 375px、768px、1024px、1440px 下：

- 页面没有横向滚动。
- 标题、按钮和表单文字没有溢出。
- 工作台三栏不发生异常挤压。
- 移动端菜单、底部导航和工具 dialog 不遮挡内容。

- [ ] **Step 3: 做无障碍检查**

检查键盘 Tab 顺序、焦点环、按钮 aria-label、表单 label、状态 `role` 和图片 `alt`。

- [ ] **Step 4: 修复仅由验收发现的布局问题**

只修改与本设计规格相关的页面样式或模板，不扩展业务范围。

- [ ] **Step 5: 最终提交**

```powershell
git add frontend/src/views frontend/src/components frontend/src/assets/css frontend/tests
git commit -m "test: verify responsive productivity UI"
```
