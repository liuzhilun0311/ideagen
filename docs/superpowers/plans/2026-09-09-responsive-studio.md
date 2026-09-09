# Responsive Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付电脑和手机可用的极简首页、连续创作工作台和作品预览。

**Architecture:** Vue/Pinia 与已有 API 不变。新增 `/workspace` 统一大纲与图文编辑，旧编辑路由重定向到工作台；首页直接生成大纲。创建选项、大纲生成、保存分别封装为 composable，继续复用阶段 1 图片 runner。

**Tech Stack:** Vue 3、TypeScript、Pinia、Vite 5、Lucide Vue、Vitest 2。执行子技能本机缺失，按现有逐任务子代理流程执行。

## Execution Status

- [x] Task 1：外壳、导航、登录和基础控件，已集成并完成类型、构建和视口检查。
- [x] Task 2：首页、参考输入、真实模型选项、大纲生成和取消，已集成并通过离线测试。
- [x] Task 3：工作台、保存快照、结构编辑和串行生成，已通过单测及模拟浏览器流程。
- [x] Task 4：成品预览、复制反馈和下载入口，已完成模拟检查。
- [x] Task 5：独立审查和最终验证通过，纳入本轮提交。详细证据见 `../verification/2026-09-09-responsive-studio.md`；截图保留在会话中，以下原始步骤保留作为范围对照。

本轮是阶段 2 的 UI 子项目；路线图中的跨设备冲突、按用户隔离草稿、稳定页面 ID 和完整 SSE 解析仍未完成。图片已存在时锁定结构编辑。没有已确认服务器快照的刷新草稿保守显示未保存；不凭 recordId 显示已保存。

## Global Constraints

- 卡片圆角不超过 8px；页面区块以无框布局为主，卡片仅用于重复项目、弹窗和确实需要边界的工具。
- 交互目标最小尺寸 44x44px；正文移动端不小于 16px。
- 验证视口：375px、390px、768px、1024px、1440px，禁止横向滚动和文字遮挡。
- 图片具备描述性 alt 文本；表单输入具备 label；颜色不是唯一状态指示。
- 动画仅用于状态切换和反馈，时长 150-300ms，并尊重 `prefers-reduced-motion`。
- 保留 Django API、Pinia store、SSE 图片生成和现有历史记录模型。
- 本轮不修改用户已有 Docker/YAML 改动，不读取 API Key，不运行真实供应商。
- 主色为实色蓝 `#315ee8`，文字 `#252935`，白与中性灰背景，青绿成功色；不使用大面积紫色、渐变背景或装饰光球。
- 基础路径 `F:\02_ai_tools_projects\IdeaGen`；npm 命令在 `frontend` 执行，Python 用 `.venv\Scripts\python.exe`。
- 后端跨设备版本冲突、按用户隔离草稿、完整 SSE parser 和任务级跨 worker 取消属于路线图剩余接口工作，不以本轮 UI 验收冒充它们已完成。

## File Ownership

| 任务 | 文件 |
| --- | --- |
| 1 全局外壳 | `frontend/src/App.vue`、`frontend/src/assets/css/{variables,base,components}.css`、`frontend/src/views/LoginView.vue`、`frontend/index.html` |
| 2 首页与选项 | `frontend/src/views/HomeView.vue`、`frontend/src/components/home/ComposerInput.vue`、`frontend/src/composables/{useCreationOptions,useOutlineGeneration}.ts`、`frontend/src/features/templates/catalog.ts` |
| 3 工作台 | `frontend/src/views/WorkspaceView.vue`、`frontend/src/components/workspace/{PageList,PageEditor,GenerationPanel}.vue`、`frontend/src/composables/{useStudio,useDraftSave}.ts`、`frontend/src/router/index.ts` |
| 4 结果 | `frontend/src/views/ResultView.vue`、`frontend/src/components/result/ContentDisplay.vue` |
| 5 验证 | `frontend/tests/studio/`、`frontend/dev-preview.html`、`frontend/tests/preview/`、`docs/superpowers/verification/` |

## Contracts

```ts
interface ModelOption { name: string; label: string }
// useCreationOptions(): loading, error, textModels, imageModels, prompts, load
// prompts is Ref<{ outline: PromptItem[]; image: PromptItem[]; content: PromptItem[] }>
// models are Ref<ModelOption[]>; load(): Promise<void>
// useOutlineGeneration(): generating: Ref<boolean>, error: Ref<AppError|null>,
// start(): Promise<boolean>, cancel(): Promise<void>
// useDraftSave(): saving: Ref<boolean>, error: Ref<AppError|null>,
// dirty: ComputedRef<boolean>, save(): Promise<boolean>
```

`useOutlineGeneration.start` 使用 store 的 topic、referenceContent、userImages、outlinePromptName、outlineModelName。成功调用 `store.setOutline`，返回 true；失败就地报错返回 false，取消后的旧响应不改 store。首页新建时只调用一次 `prepareNewOutline()`，路由不再隐式清空。

保存采用点击保存与保存后预览；同一 composable 内复用正在进行的 Promise，序列化请求，保存时拍快照，完成后若内容变化仍标为未保存。不给用户展示未实际保存的“已保存”标记。跨设备并发冲突尚不保证，单列剩余范围。

## Task 1: 外壳与设计系统

- [ ] 增加 Lucide 依赖，不升级 Vue/Vite；保留已有按钮类供设置与历史记录兼容。
- [ ] 桌面顶部品牌和导航，移动端菜单可通过按钮打开/关闭、Escape 关闭，导航项可聚焦。正文提供跳到主要内容链接。
- [ ] 移除全局卡片 hover 位移、旧主色渐变和字体外链；字体使用系统字体，letter-spacing 为 0。
- [ ] 登录页保持认证逻辑，只更新视觉、表单标签、错误与 loading 状态。
- [ ] 全局 `.btn`、`.icon-button`、`.field` 提供尺寸、焦点、禁用态；次要页面表格限定自身滚动区域。

全局尺寸核心：

```css
.icon-button { width:44px; height:44px; flex:0 0 44px; }
.field { width:100%; min-width:0; min-height:44px; }
.studio-grid { display:grid; grid-template-columns:208px minmax(0,1fr) 280px; }
@media(max-width:1100px) { .studio-grid { grid-template-columns:180px minmax(0,1fr); } }
@media(max-width:700px) { .studio-grid { display:block; } }
```

验证：`npm run typecheck`、`npm run build`；五个视口登录/首页导航截图、键盘焦点和菜单切换。

## Task 2: 极简首页

- [ ] 首页显示 IdeaGen 品牌、主题输入、更多设置、真实示例题材入口；示例只填主题，不冒充历史作品或已生成结果。
- [ ] ComposerInput 保持现有 v-model/event 接口，增加取消事件、展开选项插槽；保留普通 Enter 换行，Ctrl/Meta+Enter 才触发且忽略输入法 composing。
- [ ] 参考图最多 5 张，仅 JPEG/PNG/WebP 且每张 <=10MiB，错误就地展示，删除按钮触控可见，释放 blob URL；取消不能清空输入。
- [ ] `useCreationOptions` 从 `getConfig/getPrompts` 获取真实已启用模型，旧选择失效时回退；无模型提供设置入口，禁止无效生成。
- [ ] `useOutlineGeneration` 实际调用 generateOutline 并传参考图，维护 store.outlineStatus，防重复点击、晚到响应；生成成功进入 `/workspace`。
- [ ] 保留新建前确认，已有结果不能被静默清空；无效未来模板不作为可点按钮。

验证用例：

```ts
it('passes all reference inputs and ignores a cancelled response', async () => {
  const store = useGeneratorStore()
  store.topic = 'A city walk'
  store.referenceContent = 'Use a calm tone'
  const request = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  const action = useOutlineGeneration()
  const pending = action.start()
  action.cancel()
  request.resolve({ success:true, outline:'late', pages:[{index:0,type:'cover',content:'late'}] })
  expect(await pending).toBe(false)
  expect(store.outline.pages).toEqual([])
})
```

此测试在 `frontend/tests/studio/outline.test.ts` 使用现有 Vitest mock、Pinia setup，`deferred` 是测试内定义的 Promise 控制器；先运行并确认旧代码没有该功能，再实现后复跑。运行 `npm test -- tests/studio/outline.test.ts`。

## Task 3: 连续工作台

- [ ] `/workspace` 显示标题、实际保存状态、保存、预览；旧 `/outline`、`/generate` 保留 route name，以 redirect 兼容历史页和结果页入口。
- [ ] `PageList` 通过选中位置选择页面；上下移动、增删有键盘按钮。已有图片或正在生成时禁止结构变更，避免旧 index 错配；不在本轮伪造稳定 ID 迁移。
- [ ] `PageEditor` 当前页图片 object-fit:contain，支持放大与重试；当前页大纲可编辑，整套标题/文案/标签单独标签页编辑，空/忙/失败状态都有明确显示。
- [ ] `GenerationPanel` 分别选择大纲/图片/文案的真实模型和提示词，复用图片 runner/useImageRetry；大纲和文案通过 AbortController/所有权防止取消回写。
- [ ] 后端仍按用户统一取消，因此同一工作台一次只运行一种生成，文案与图片可以分别运行但不同时开始。取消流程未结束前禁用新生成。
- [ ] 图片生成前先保存当前大纲和文案，保存失败不生成；生成后显式保存并预览，不让历史恢复覆盖本地新编辑。
- [ ] 手机底部“结构/编辑/生成”导航，平板右侧工具移到主列下方；1440px 三栏。生成中路由离开被阻止并显示就地提示。
- [ ] 禁用单图重试条件：没有 taskId、页面不是 error/done 或任一任务忙；不能保留无响应的重试按钮。

保存快照协议：

```ts
function draftPayload(store: ReturnType<typeof useGeneratorStore>) {
  return {
    title: store.topic,
    outline: {raw:store.outline.raw, pages:store.outline.pages.map(p=>({...p}))},
    content: {titles:[...store.content.titles],copywriting:store.content.copywriting,tags:[...store.content.tags]},
  }
}
```

`useDraftSave.save` 使用 `createHistory(topic, outline, taskId?)` 获得 ID，再 `updateHistory(id,payload)`；检查两个返回值的 success。后端已生成的 images 不在普通文案保存请求里覆盖。比较成功时的 payload JSON 与当前 payload，避免把请求中途编辑标为已保存。

测试 `frontend/tests/studio/save.test.ts` 覆盖创建失败、更新失败、重复保存复用 Promise、请求期间编辑保持 dirty；运行 `npm test -- tests/studio/save.test.ts`。

## Task 4: 成品预览

- [ ] ResultView 标题为“作品预览”，不在仍有失败时固定显示“创作完成”；显示页数、成功数量和返回工作台。
- [ ] 图片等比例完整展示，缩略图导航与单图下载/复制可访问，失败页有返回编辑入口。
- [ ] 保留已有去 AI 化下载与 ZIP fallback，不改变底层处理能力；错误在页面显示，可重试，不承诺去 AI 检测成功。
- [ ] ContentDisplay 统一 Lucide 与复制反馈，保留原 props/slot/store 接口；复制失败不显示成功。

验证：生产构建、结果空态、部分失败、长标题/标签、手机宽度；不实际执行用户数据下载或去 AI 化处理。

## Task 5: 独立验收

- [ ] 使用单独的 `dev-preview.html` 测试入口和模拟账号/作品/API，不修改真实账号、不在 production bundle 开启 mock。入口明确标为开发预览。
- [ ] 浏览器验证：首页填写、高级设置、创建工作台、页面选择、上下移动、保存、结果预览、返回编辑；记录模拟请求调用和错误状态。
- [ ] 登录、首页、工作台和结果在 375/390/768/1024/1440px 检查溢出与资源加载，至少保存桌面与手机截图。
- [ ] 运行 `npm test`、`npm run typecheck`、`npm run test:typecheck`、`npm run build`；生产入口仍鉴权，开发模拟不进入 dist。
- [ ] 独立子代理审查，处理可复现缺陷后再次验证。单独提交 UI 改动和验收记录。

## 执行安排

用户已确认子代理执行方式，继续沿用，不重复询问。全局外壳、首页与结果可并行，各自不改他人文件；主代理负责工作台和整合。未通过的验收项保持未勾选，后端冲突与 Docker 工作不在本轮标记完成。
