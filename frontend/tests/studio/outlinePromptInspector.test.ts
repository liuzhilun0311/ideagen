import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import { renderer, root, nodes, button, settle, text } from '../history/renderer'
import OutlinePromptInspector from '../../src/components/workspace/OutlinePromptInspector.vue'
import { useGeneratorStore } from '../../src/stores/generator'
import { previewOutlinePrompt, listOutlineRuns, type OutlineRun } from '../../src/api/outline'

vi.mock('../../src/api/outline', () => ({ previewOutlinePrompt: vi.fn(), listOutlineRuns: vi.fn() }))
let unmount: (() => void) | undefined
beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  useGeneratorStore().topic = ' Changed topic '
  vi.mocked(previewOutlinePrompt).mockReset().mockResolvedValue({ prompt: 'NEXT' })
  vi.mocked(listOutlineRuns).mockReset().mockResolvedValue([])
})
afterEach(() => unmount?.())
function mount() {
  const app = renderer.createApp(OutlinePromptInspector, { home: true })
  app.use(getActivePinia()!)
  app.mount(root)
  unmount = () => app.unmount()
  Object.assign(nodes().find(node => node.tag === 'dialog')!, { showModal: vi.fn(), close: vi.fn() })
}

it('previews the same automatic home preferences used for generation', async () => {
  const store = useGeneratorStore()
  store.outlineOrganization = '步骤教程'
  store.outlineTone = '专业简洁'
  mount()
  await button('查看本次提示词')!.props.onClick()
  await settle()
  expect(previewOutlinePrompt).toHaveBeenCalledWith(expect.objectContaining({
    topic: 'Changed topic', organization: '步骤教程', tone: '自动匹配',
  }))
  expect(nodes().find(node => node.tag === 'textarea')?.props.value).toBe('NEXT')
})

it('shows the saved request first after generation and switches to the next preview explicitly', async () => {
  const store = useGeneratorStore()
  store.outline.generation_record_id = 'sent'
  vi.mocked(listOutlineRuns).mockResolvedValue([{
    id: 'sent', prompt: 'ORIGINAL SENT PROMPT', sent: true, status: 'succeeded',
    references: [], created_at: '2026-09-28T00:00:00Z', model: 'model', provider: 'provider',
  } as unknown as OutlineRun])
  mount()
  await button('查看本次提示词')!.props.onClick()
  await settle()
  expect(listOutlineRuns).toHaveBeenCalledWith('sent')
  expect(previewOutlinePrompt).not.toHaveBeenCalled()
  expect(nodes().find(node => node.tag === 'textarea')?.props.value).toBe('ORIGINAL SENT PROMPT')
  const previewTab = nodes().find(node => node.props.role === 'tab' && text(node) === '下次生成预览')!
  await previewTab.props.onClick()
  await settle()
  expect(previewOutlinePrompt).toHaveBeenCalledOnce()
  expect(nodes().find(node => node.tag === 'textarea')?.props.value).toBe('NEXT')
})

it('reports an empty custom reader without sending a preview request', async () => {
  useGeneratorStore().outlineAudience = '自定义'
  mount()
  await button('查看本次提示词')!.props.onClick()
  await settle()
  expect(previewOutlinePrompt).not.toHaveBeenCalled()
  expect(text()).toContain('具体目标读者')
})
