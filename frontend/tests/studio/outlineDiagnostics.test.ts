import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { renderer, root, nodes, button, text, settle, deferred } from '../history/renderer'
import OutlineDiagnostics from '../../src/components/workspace/OutlineDiagnostics.vue'
import { listOutlineRuns, type OutlineRun } from '../../src/api/outline'
import { getOutlineDiagnostics } from '../../src/api/diagnostics'

vi.mock('../../src/api/outline', () => ({ listOutlineRuns: vi.fn() }))
vi.mock('../../src/api/diagnostics', () => ({ getOutlineDiagnostics: vi.fn() }))
let unmount: (() => void) | undefined
let show: ReturnType<typeof vi.fn>
const run = { id: 'outline-run', created_at: '2026-09-28T10:00:00', model: 'test', status: 'failed' } as OutlineRun
const diagnostic = {
  success: true, record_id: run.id, status: 'failed', response_available: true,
  events: [{ at: 'now', event: 'response' as const, source: 'upstream', http_status: 403, body: { error: 'denied' } }],
}
function mount(recordId?: string) {
  const app = renderer.createApp(OutlineDiagnostics, { recordId })
  app.mount(root)
  unmount = () => app.unmount()
  show = vi.fn()
  Object.assign(nodes().find(node => node.tag === 'dialog')!, { showModal: show, close: vi.fn() })
}
beforeEach(() => {
  vi.mocked(listOutlineRuns).mockReset().mockResolvedValue([run])
  vi.mocked(getOutlineDiagnostics).mockReset().mockResolvedValue(diagnostic)
})
afterEach(() => unmount?.())

it('opens by outline record without an image task and shows the upstream failure', async () => {
  mount(run.id)
  await button('查看请求与响应')!.props.onClick()
  await settle()
  expect(show).toHaveBeenCalledOnce()
  expect(listOutlineRuns).toHaveBeenCalledWith(run.id)
  expect(getOutlineDiagnostics).toHaveBeenCalledWith(run.id)
  expect(text()).toContain('403')
  expect(text()).toContain('denied')
})

it('opens immediately while loading and shows request errors with a working retry', async () => {
  const pending = deferred<OutlineRun[]>()
  vi.mocked(listOutlineRuns).mockReturnValueOnce(pending.promise)
  mount()
  const opened = button('查看请求与响应')!.props.onClick()
  await nextTick()
  expect(show).toHaveBeenCalledOnce()
  expect(text()).toContain('正在加载')
  vi.mocked(getOutlineDiagnostics).mockRejectedValueOnce(new Error('Access denied'))
  pending.resolve([run])
  await opened
  await settle()
  expect(text()).toContain('Access denied')
  await button('刷新大纲诊断')!.props.onClick()
  await settle()
  expect(text()).toContain('denied')
  expect(text()).not.toContain('Access denied')
})

it('shows legacy snapshots without claiming a response exists', async () => {
  vi.mocked(getOutlineDiagnostics).mockResolvedValue({
    ...diagnostic, response_available: false,
    events: [{ at: 'now', source: 'snapshot', event: 'request', prompt: 'Saved prompt' }],
  })
  mount(run.id)
  await button('查看请求与响应')!.props.onClick()
  await settle()
  expect(text()).toContain('未保存响应')
  expect(text()).toContain('Saved prompt')
})

it('shows an empty account and never asks for image diagnostics', async () => {
  vi.mocked(listOutlineRuns).mockResolvedValue([])
  mount()
  await button('查看请求与响应')!.props.onClick()
  await settle()
  expect(text()).toContain('暂无大纲生成记录')
  expect(getOutlineDiagnostics).not.toHaveBeenCalled()
})

it('discards a pending result when the dialog closes', async () => {
  const pending = deferred<OutlineRun[]>()
  vi.mocked(listOutlineRuns).mockReturnValueOnce(pending.promise)
  mount()
  const opened = button('查看请求与响应')!.props.onClick()
  button('关闭大纲诊断')!.props.onClick()
  pending.resolve([run])
  await opened
  expect(getOutlineDiagnostics).not.toHaveBeenCalled()
})

it('switches records and clears the previous response when the next lookup fails', async () => {
  vi.mocked(listOutlineRuns).mockResolvedValue([run, { ...run, id: 'other-run' }])
  mount(run.id)
  await button('查看请求与响应')!.props.onClick()
  vi.mocked(getOutlineDiagnostics).mockRejectedValueOnce(new Error('Record unavailable'))
  const select = nodes().find(node => node.tag === 'select')!
  select.props['onUpdate:modelValue']('other-run')
  await select.props.onChange()
  await settle()
  expect(getOutlineDiagnostics).toHaveBeenLastCalledWith('other-run')
  expect(text()).toContain('Record unavailable')
  expect(text()).not.toContain('"http_status"')
})
