# Generation Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留现有界面的前提下修复图片进度重复计数、断流卡住、取消丢进度以及记录创建失败仍发起生成。

**Architecture:** 保持 Pinia store 和既有回调式图片 API。store 根据图片实际状态计算进度，runner 负责异步请求所有权与终止，restore 显式返回记录 ID 或抛错；通过离线测试覆盖这一边界。

**Tech Stack:** Vue 3、Pinia 2、TypeScript 5、现有 Vite 5；增加与 Vite 5 匹配的 Vitest 2.1.9，仅用作本地开发测试。

## Global Constraints

- 保留 Django API、Pinia store、SSE 图片生成和现有历史记录模型。
- 取消请求与前端 AbortController 都执行。
- SSE 连接断开时展示恢复或重试选项。
- 单页图片失败：只标记该页并允许重试。
- 本阶段不重写 AI 服务商协议、不开发原生移动 App、不引入新的计费系统。
- 仓库根目录为 `F:\02_ai_tools_projects\IdeaGen`；本计划内所有路径相对于该目录。
- 所有 npm 命令工作目录为 `F:\02_ai_tools_projects\IdeaGen\frontend`；Git 命令工作目录为仓库根目录；各命令单独执行。
- 测试不调用真实图片/文案服务商，不读取用户供应商 YAML、不写入已有历史资料。
- 本计划只完成整体路线阶段 1；跨进程取消和完整刷新恢复不能由本阶段验收代替。

---

## File Structure

| 文件 | 职责 |
| --- | --- |
| `frontend/vitest.config.ts` | 仅离线单元测试配置 |
| `frontend/tests/setup.ts` | 隔离 localStorage |
| `frontend/tests/generation/progress.test.ts` | Pinia 进度与结果保留回归 |
| `frontend/tests/generation/restore.test.ts` | 历史记录创建门槛 |
| `frontend/tests/generation/runner.test.ts` | 请求生命周期与晚到事件 |
| `frontend/src/stores/generator.ts` | 派生进度与图片终态 |
| `frontend/src/composables/useGenerationRestore.ts` | 返回 ID 或抛错 |
| `frontend/src/composables/useGenerationRunner.ts` | 防重复、断流、取消 |
| `frontend/package.json`、`frontend/package-lock.json` | 测试依赖和脚本 |

## Task 1: 图片进度幂等与保留成功结果

**执行记录（2026-09-09）：** 提交 `011476e`。先复现 6 项失败，修正后新增重绘终态回归又复现 1 项失败；最终 7/7 通过，typecheck/build 退出码 0。实现补充：非批量生成中的任务随单图重绘重新计算终态。

**Files:** 创建测试配置、setup、`progress.test.ts`；修改 `generator.ts` 和 npm manifest/lock。

**Interfaces:**

- 消费 `GeneratedImage`、`GeneratorState` 和现有 `updateProgress(index, status, url?, error?)`。
- 产出 `syncImageProgress(): void`、`stopGeneration(message: string): void`；保留 `progress.status` 既有联合类型，避免无关页面改动。
- `progress.current` 始终等于当前 `status === 'done'` 的图片数；结束后有任意失败时 `progress.status === 'error'`。

- [x] **Step 1: 安装测试依赖并配置**

```powershell
npm install --save-dev --save-exact vitest@2.1.9
npm pkg set "scripts.test=vitest run"
```

这是测试工具安装而非升级运行时框架。Vitest 版本已通过 npm registry 查询确认依赖 Vite `^5.0.0`。测试不启动 Vitest 公网 UI 服务。

完整 `frontend/vitest.config.ts`：

```ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    setupFiles: ['./tests/setup.ts'],
    clearMocks: true,
  },
})
```

完整 `frontend/tests/setup.ts`：

```ts
import { beforeEach } from 'vitest'

const values = new Map<string, string>()
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, String(value)),
    removeItem: (key: string) => { values.delete(key) },
    clear: () => values.clear(),
    key: (index: number) => [...values.keys()][index] ?? null,
    get length() { return values.size },
  },
})
beforeEach(() => values.clear())
```

- [x] **Step 2: 写失败测试**

完整 `frontend/tests/generation/progress.test.ts`：

```ts
import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../../src/stores/generator'

beforeEach(() => setActivePinia(createPinia()))

function draft() {
  const store = useGeneratorStore()
  store.setOutline('cover\n\nbody', [
    { index: 0, type: 'cover', content: 'cover' },
    { index: 1, type: 'content', content: 'body' },
  ])
  store.startGeneration()
  return store
}

it('counts duplicate completion only once and ignores unknown indices', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.updateProgress(9, 'done', '/api/images/task/9.png')
  expect(store.progress.current).toBe(1)
})

it('keeps partial success on interruption and allows retry', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.stopGeneration('连接中断')
  expect(store.progress).toEqual({ current: 1, total: 2, status: 'error' })
  expect(store.images[0].status).toBe('done')
  expect(store.images[1]).toMatchObject({
    status: 'error', error: '连接中断', retryable: true,
  })
})

it('does not mark a partially failed finish as successful', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.finishGeneration('task')
  expect(store.progress.status).toBe('error')
  expect(store.progress.current).toBe(1)
  expect(store.taskId).toBe('task')
})

it('recounts redraw and clears old errors when retry succeeds', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.setImageRetrying(0)
  expect(store.progress.current).toBe(0)
  store.updateProgress(0, 'error', undefined, 'failure')
  store.updateImage(0, '/api/images/task/0-new.png')
  expect(store.images[0].error).toBeUndefined()
  expect(store.progress.current).toBe(1)
})
```

- [x] **Step 3: 运行红灯测试**

Run: `npm test -- tests/generation/progress.test.ts`

Expected: FAIL，重复事件计数不等于 1，且 `stopGeneration` 尚不存在。必须记录实际失败，不能将依赖安装失败当作回归红灯。

- [x] **Step 4: 在 store actions 中增加两方法并替换四个既有方法**

下列代码完整替换同名方法，其他 store actions 不动：

```ts
syncImageProgress() {
  this.progress.current = this.images.filter(img => img.status === 'done').length
  this.progress.total = this.images.length
},

stopGeneration(message: string) {
  for (const image of this.images) {
    if (image.status === 'generating' || image.status === 'retrying') {
      image.status = 'error'
      image.error = message
      image.retryable = true
    }
  }
  this.syncImageProgress()
  this.progress.status = this.images.length > 0
    && this.images.every(img => img.status === 'done') ? 'done' : 'error'
  this.stage = 'outline'
},

updateProgress(
  index: number,
  status: 'generating' | 'done' | 'error',
  url?: string,
  error?: string,
) {
  const image = this.images.find(img => img.index === index)
  if (!image) return
  image.status = status
  if (url) image.url = withToken(url)
  if (status === 'done') {
    delete image.error
    delete image.retryable
  } else if (status === 'error') {
    image.error = error || '图片生成失败'
    image.retryable = true
  }
  this.syncImageProgress()
},

updateImage(index: number, newUrl: string) {
  const image = this.images.find(img => img.index === index)
  if (!image) return
  const tokenUrl = withToken(newUrl)
  image.url = `${tokenUrl}${tokenUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
  image.status = 'done'
  delete image.error
  delete image.retryable
  this.syncImageProgress()
},

finishGeneration(taskId: string) {
  this.taskId = taskId
  this.stopGeneration('图片生成未完成')
  this.stage = this.progress.status === 'done' ? 'result' : 'outline'
},

setImageRetrying(index: number) {
  const image = this.images.find(img => img.index === index)
  if (!image) return
  image.status = 'retrying'
  delete image.error
  this.syncImageProgress()
},
```

替换四个既有方法（`updateProgress`、`updateImage`、`finishGeneration`、`setImageRetrying`）并新增两个方法；保留 `startGeneration` 初始化行为。不修改页面路由，`stage` 是状态字段，不触发跳转。

- [x] **Step 5: 运行绿灯与类型检查**

```powershell
npm test -- tests/generation/progress.test.ts
npm run typecheck
npm run build
```

Expected: 4 tests passed，后两条退出码 0。确认既有 `useImageRetry` 成功回调仍使用 `updateImage` 与 `finishGeneration`。

- [x] **Step 6: 检查并提交本任务文件**

```powershell
git diff --check
git add -- frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/tests/setup.ts frontend/tests/generation/progress.test.ts frontend/src/stores/generator.ts
git commit -m "fix: make image progress idempotent and preserve partial results"
```

## Task 2: 记录创建失败阻止后续生成

**执行记录（2026-09-09）：** 提交 `dbf07a1`。子代理先运行得到 8 失败 / 4 通过，再实现显式错误；主代理独立复跑 12/12 通过，typecheck 退出码 0。补充覆盖网络异常、结构化错误和历史恢复不回归。

**Files:** 修改 `frontend/src/composables/useGenerationRestore.ts`；创建 `frontend/tests/generation/restore.test.ts`。

**Interfaces:**

- 消费现有 `createHistory(topic, outline)` 与 `normalizeApiError(error, fallbackTitle)`。
- 将 `ensureRecord(): Promise<void>` 改为 `ensureRecord(): Promise<string>`，失败抛 `AppError`，不吞错。
- `restoreFromHistory(): Promise<boolean>` 保持原样。

- [x] **Step 1: 写失败测试**

完整测试文件：

```ts
import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../src/api', () => ({
  createHistory: vi.fn(),
  getHistory: vi.fn(),
  getImageUrl: vi.fn(),
}))

import { createHistory } from '../../src/api'
import { useGeneratorStore } from '../../src/stores/generator'
import { useGenerationRestore } from '../../src/composables/useGenerationRestore'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(createHistory).mockReset()
})

it('rejects failed creation and does not set record ID', async () => {
  vi.mocked(createHistory).mockResolvedValue({
    success: false, error: '存储不可用',
  })
  await expect(useGenerationRestore().ensureRecord()).rejects.toMatchObject({
    code: expect.any(String),
  })
  expect(useGeneratorStore().recordId).toBeNull()
})

it('returns an existing ID without creating another record', async () => {
  useGeneratorStore().setRecordId('existing')
  await expect(useGenerationRestore().ensureRecord()).resolves.toBe('existing')
  expect(createHistory).not.toHaveBeenCalled()
})

it('returns and persists a newly created ID', async () => {
  vi.mocked(createHistory).mockResolvedValue({
    success: true, record_id: 'created',
  })
  await expect(useGenerationRestore().ensureRecord()).resolves.toBe('created')
  expect(useGeneratorStore().recordId).toBe('created')
})

it('rejects success responses missing an ID', async () => {
  vi.mocked(createHistory).mockResolvedValue({ success: true })
  await expect(useGenerationRestore().ensureRecord()).rejects.toBeDefined()
})
```

- [x] **Step 2: 运行红灯**

Run: `npm test -- tests/generation/restore.test.ts`

Expected: FAIL，既有实现返回 undefined 且吞掉失败。

- [x] **Step 3: 增加 import 并完整替换 ensureRecord**

```ts
import { normalizeApiError } from '../utils/errors'
```

```ts
async function ensureRecord(): Promise<string> {
  if (store.recordId) return store.recordId
  const result = await createHistory(store.topic, {
    raw: store.outline.raw,
    pages: store.outline.pages,
  })
  if (!result.success || !result.record_id) {
    throw normalizeApiError(
      result.error || result.error_message || '历史记录未返回 ID',
      '无法创建作品记录',
    )
  }
  store.setRecordId(result.record_id)
  return result.record_id
}
```

- [x] **Step 4: 绿灯并提交**

```powershell
npm test -- tests/generation/restore.test.ts
npm run typecheck
```

Expected: 4 tests passed，类型检查退出码 0。

```powershell
git diff --check
git add -- frontend/src/composables/useGenerationRestore.ts frontend/tests/generation/restore.test.ts
git commit -m "fix: fail generation when record creation fails"
```

## Task 3: 图片流生命周期与晚到回调隔离

**执行记录（2026-09-09）：** 提交 `eda8ee8`。子代理红灯 14/14 失败，扩充至 17 个通过；主代理与独立审查另外复现并修复缺失 finish 的假成功、finish 后连接不关闭导致不能重启、真实 SSE 客户端吞回调异常三个边界。最终 runner 18/18、真实客户端离线流 5/5，通过全部 42 项测试。另加 `tsconfig.test.json` 和 `test:typecheck`，测试源码也通过类型检查。完整证据见 `docs/superpowers/verification/2026-09-09-generation-reliability.md`。

**Files:** 替换 `frontend/src/composables/useGenerationRunner.ts`；创建 `frontend/tests/generation/runner.test.ts`。

**Interfaces:**

- 消费任务 1 的 `stopGeneration(message)`、任务 2 的 `ensureRecord(): Promise<string>`。
- 保持 `startGenerationFlow(force?: boolean): Promise<void>` 和 `cancelGenerationFlow()` 导出名称。
- `generateImagesPost` 现有参数次序不变；它通过 callback 报错并返回 Promise，runner 必须 await。
- 不修改后端按用户取消协议。本阶段界面只能显示“本地已取消”，不能声称远端已确认停止；取消 API 吞错的行为及任务 ID 取消由阶段 3 处理。

- [x] **Step 1: 写失败测试**

完整测试文件：

```ts
import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('../../src/api', () => ({
  generateImagesPost: vi.fn(),
  cancelCurrentGeneration: vi.fn(),
}))
vi.mock('../../src/composables/useGenerationRestore', () => ({
  useGenerationRestore: () => ({ ensureRecord: mocks.ensureRecord }),
}))
const mocks = vi.hoisted(() => ({ ensureRecord: vi.fn() }))

import { generateImagesPost, cancelCurrentGeneration } from '../../src/api'
import { useGeneratorStore } from '../../src/stores/generator'
import { useGenerationRunner } from '../../src/composables/useGenerationRunner'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(generateImagesPost).mockReset()
  vi.mocked(cancelCurrentGeneration).mockReset().mockResolvedValue(undefined)
  mocks.ensureRecord.mockReset().mockResolvedValue('record')
  useGeneratorStore().setOutline('cover', [
    { index: 0, type: 'cover', content: 'cover' },
  ])
})

it('does not call image provider when saving the record fails', async () => {
  mocks.ensureRecord.mockRejectedValue(new Error('save failed'))
  const report = vi.fn()
  await useGenerationRunner(report).startGenerationFlow()
  expect(generateImagesPost).not.toHaveBeenCalled()
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: 'save failed',
  }))
})

it('treats EOF without finish as interruption', async () => {
  vi.mocked(generateImagesPost).mockResolvedValue(undefined)
  const report = vi.fn()
  await useGenerationRunner(report).startGenerationFlow()
  expect(useGeneratorStore().progress.status).toBe('error')
  expect(useGeneratorStore().images[0].retryable).toBe(true)
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: expect.stringContaining('连接中断'),
  }))
})

it('accepts successful finish', async () => {
  vi.mocked(generateImagesPost).mockImplementation(async (...args) => {
    args[4]({ index: 0, status: 'done', image_url: '/api/images/t/0.png' })
    args[6]({ success: true, task_id: 't', images: ['0.png'] })
  })
  await useGenerationRunner(vi.fn()).startGenerationFlow()
  expect(useGeneratorStore().progress).toEqual({
    current: 1, total: 1, status: 'done',
  })
})

it('blocks duplicate starts and ignores callbacks after cancel', async () => {
  let release!: () => void
  vi.mocked(generateImagesPost).mockImplementation(() =>
    new Promise<void>(resolve => { release = resolve }),
  )
  const runner = useGenerationRunner(vi.fn())
  const pending = runner.startGenerationFlow()
  await vi.waitFor(() => expect(generateImagesPost).toHaveBeenCalledOnce())
  await runner.startGenerationFlow()
  expect(generateImagesPost).toHaveBeenCalledOnce()
  const args = vi.mocked(generateImagesPost).mock.calls[0]
  runner.cancelGenerationFlow()
  args[4]({ index: 0, status: 'done', image_url: '/api/images/old/0.png' })
  args[6]({ success: true, task_id: 'old', images: ['0.png'] })
  expect(args[13]?.aborted).toBe(true)
  expect(cancelCurrentGeneration).toHaveBeenCalledOnce()
  expect(useGeneratorStore().images[0].status).toBe('error')
  expect(useGeneratorStore().taskId).not.toBe('old')
  release()
  await pending
})
```

- [x] **Step 2: 运行红灯**

Run: `npm test -- tests/generation/runner.test.ts`

Expected: FAIL，记录失败异常未被处理、EOF 仍 generating 或旧回调改写 store。

- [x] **Step 3: 完整替换 runner 文件**

```ts
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateImagesPost, cancelCurrentGeneration } from '../api'
import { formatErrorMessage, normalizeApiError, type AppError } from '../utils/errors'
import { useGenerationRestore } from './useGenerationRestore'

export function useGenerationRunner(setError: (error: AppError | null) => void) {
  const router = useRouter()
  const store = useGeneratorStore()
  const { ensureRecord } = useGenerationRestore()
  let active: AbortController | null = null
  let cancelPending = false

  async function startGenerationFlow(force = false): Promise<void> {
    if (active || cancelPending) return
    if (store.outline.pages.length === 0) {
      await router.push('/')
      return
    }
    const controller = new AbortController()
    active = controller
    let finished = false
    let started = false
    const ownsRun = () => active === controller && !controller.signal.aborted
    setError(null)
    try {
      await ensureRecord()
      if (!ownsRun()) return
      store.startGeneration()
      started = true
      await generateImagesPost(
        store.outline.pages,
        null,
        store.outline.raw,
        () => {},
        event => {
          if (ownsRun() && !finished && event.image_url) {
            store.updateProgress(event.index, 'done', event.image_url)
          }
        },
        event => {
          if (ownsRun() && !finished) {
            store.updateProgress(
              event.index,
              'error',
              undefined,
              formatErrorMessage(event.error || event.message || '图片生成失败'),
            )
          }
        },
        event => {
          if (!ownsRun() || finished) return
          finished = true
          store.finishGeneration(event.task_id)
        },
        error => {
          if (!ownsRun() || finished) return
          finished = true
          store.stopGeneration('连接中断，请重试未完成图片')
          setError(normalizeApiError(error, '图片生成失败'))
        },
        store.userImages.length ? store.userImages : undefined,
        store.topic,
        store.recordId,
        force,
        store.imagePromptName,
        controller.signal,
        store.imageModelName,
      )
      if (ownsRun() && !finished) {
        store.stopGeneration('连接中断，请重试未完成图片')
        setError(normalizeApiError('连接中断，未收到完成确认', '图片生成中断'))
      }
    } catch (error) {
      if (ownsRun()) {
        if (started) store.stopGeneration('图片生成中断')
        setError(normalizeApiError(error, '无法开始生成'))
      }
    } finally {
      if (active === controller) active = null
    }
  }

  function cancelGenerationFlow(): void {
    if (!active) return
    active.abort()
    active = null
    cancelPending = true
    store.stopGeneration('本地已取消，未完成图片可重试')
    void cancelCurrentGeneration()
      .catch(error => setError(normalizeApiError(error, '远端取消未确认')))
      .finally(() => { cancelPending = false })
  }

  return { startGenerationFlow, cancelGenerationFlow }
}
```

保留了已完成图片，但缺少 taskId 的中断任务不能直接调用单图重试；现有全组生成按钮作为本阶段重试入口。阶段 2 必须通过 `recordId` 恢复服务端 taskId 后才启用逐张重试，不能显示一个不可用按钮。

- [x] **Step 4: 绿灯与全量本阶段验证**

```powershell
npm test
npm run typecheck
npm run build
```

Expected: 三文件共 12 tests passed，类型检查和构建退出码 0。不用这些离线结果宣称真实模型已生成成功。

- [x] **Step 5: 提交并记录证据**

```powershell
git diff --check
git add -- frontend/src/composables/useGenerationRunner.ts frontend/tests/generation/runner.test.ts
git commit -m "fix: settle interrupted generation and ignore stale callbacks"
```

## Handoff

- [x] 记录实际扩展后的 42 个测试、应用与测试 typecheck、build 的输出和退出码。
- [x] 核对本阶段提交仅含 frontend 文件，没有覆盖 `.dockerignore`、Compose 或用户供应商配置。
- [x] 本阶段保留明确限制：跨进程取消未修复、完整 SSE parser 未更换、真实供应商未测试。
- [ ] 基于阶段 1 实际接口编写阶段 2 的逐组件实施计划；再编写阶段 3 的部署实施计划。不要把路线图当作另外两阶段已经可逐行执行的计划。
