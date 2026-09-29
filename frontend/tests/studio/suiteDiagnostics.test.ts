import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import { renderer, root, nodes, button, text, settle } from '../history/renderer'
import SuiteDiagnostics from '../../src/components/workspace/SuiteDiagnostics.vue'
import { useGeneratorStore } from '../../src/stores/generator'
import { getHistory } from '../../src/api/history'
import { getGenerationDiagnostics } from '../../src/api/diagnostics'

vi.mock('../../src/api/history', () => ({ getHistory: vi.fn() }))
vi.mock('../../src/api/diagnostics', () => ({ getGenerationDiagnostics: vi.fn() }))
let unmount: () => void
beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  vi.mocked(getHistory).mockReset()
  vi.mocked(getGenerationDiagnostics).mockReset().mockResolvedValue({
    success: true, task_id: 'failed-task',
    events: [{ at: 'now', event: 'response', page_index: 0, generation_id: 'attempt-1', http_status: 500, error: 'Failed upstream' }],
  })
  const app = renderer.createApp(SuiteDiagnostics)
  app.use(getActivePinia()!)
  app.mount(root)
  unmount = () => app.unmount()
  Object.assign(nodes().find(node => node.tag === 'dialog')!, { showModal: vi.fn(), close: vi.fn() })
})
afterEach(() => unmount())
function mountPage(generationId?: string) {
  unmount()
  const app = renderer.createApp(SuiteDiagnostics, { pageIndex: 0, generationId })
  app.use(getActivePinia()!)
  app.mount(root)
  unmount = () => app.unmount()
  Object.assign(nodes().find(node => node.tag === 'dialog')!, { showModal: vi.fn(), close: vi.fn() })
}
it('filters single-page diagnostics by the visible candidate without dropping local responses', async () => {
  mountPage('attempt-1')
  useGeneratorStore().taskId = 'failed-task'
  await button('查看请求与响应')!.props.onClick()
  await settle()
  expect(getGenerationDiagnostics).toHaveBeenCalledWith('failed-task', 0, 'attempt-1')
  expect(text()).toContain('第 1 页 · 请求与响应')
  expect(text()).toContain('Failed upstream')
  expect(nodes().some(node => node.tag === 'select')).toBe(false)
})
it('finds single-page failure diagnostics even before a candidate has been adopted', async () => {
  mountPage()
  useGeneratorStore().recordId = 'record'
  vi.mocked(getHistory).mockResolvedValue({ success: true, record: { images: { task_id: 'failed-task' } } } as Awaited<ReturnType<typeof getHistory>>)
  await button('查看请求与响应')!.props.onClick()
  await settle()
  expect(getGenerationDiagnostics).toHaveBeenCalledWith('failed-task', 0, undefined)
  expect(text()).toContain('Failed upstream')
})
it('finds the first failed generation task from the saved work', async () => {
  const store = useGeneratorStore()
  store.recordId = 'record'
  vi.mocked(getHistory).mockResolvedValue({ success: true, record: { images: { task_id: 'failed-task' } } } as Awaited<ReturnType<typeof getHistory>>)
  await button('查看请求与响应')!.props.onClick()
  await settle()
  expect(getGenerationDiagnostics).toHaveBeenCalledWith('failed-task')
  expect(text()).toContain('500')
  expect(text()).toContain('Failed upstream')
  expect(text()).toContain('attempt-1')
})
it('opens before any generation with a clear empty state', async () => {
  await button('查看请求与响应')!.props.onClick()
  await settle()
  expect(text()).toContain('暂无图片生成记录')
  expect(getGenerationDiagnostics).not.toHaveBeenCalled()
})
it('does not use stale local diagnostics when access to the record fails', async () => {
  useGeneratorStore().recordId = 'record'
  useGeneratorStore().taskId = 'old-task'
  vi.mocked(getHistory).mockRejectedValue(new Error('denied'))
  await button('查看请求与响应')!.props.onClick()
  await settle()
  expect(text()).toContain('加载失败')
  expect(getGenerationDiagnostics).not.toHaveBeenCalled()
})
