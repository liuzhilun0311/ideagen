import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { renderer, root, nodes, button, settle, text } from '../history/renderer'
import HomeView from '../../src/views/HomeView.vue'
import { useGeneratorStore } from '../../src/stores/generator'
import { listOutlineRuns } from '../../src/api/outline'
import { useOutlineGeneration } from '../../src/composables/useOutlineGeneration'

vi.mock('vue-router', () => ({ useRoute: () => ({ path: '/' }), useRouter: () => ({ push: vi.fn() }) }))
vi.mock('../../src/api/outline', () => ({ listOutlineRuns: vi.fn() }))
vi.mock('../../src/api/diagnostics', () => ({ getOutlineDiagnostics: vi.fn() }))
vi.mock('../../src/composables/useOutlineGeneration', () => ({ useOutlineGeneration: vi.fn() }))
vi.mock('../../src/composables/useCreationOptions', () => ({
  useCreationOptions: () => ({
    loading: ref(false), refreshNeeded: ref(false), error: ref(null),
    textModels: ref([{ name: 'text', label: 'Text' }]), load: vi.fn(),
  }),
}))
vi.mock('../../src/components/home/ComposerInput.vue', () => ({ default: { render: () => null } }))
vi.mock('../../src/components/workspace/OutlineOptions.vue', () => ({ default: { render: () => null } }))
vi.mock('../../src/components/workspace/OutlinePromptInspector.vue', () => ({ default: { render: () => null } }))
vi.mock('../../src/components/workspace/NewCreationButton.vue', () => ({ default: { render: () => null } }))

let unmount: (() => void) | undefined
beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('window', { addEventListener: vi.fn(), removeEventListener: vi.fn(), confirm: vi.fn(() => true) })
  vi.mocked(listOutlineRuns).mockReset().mockResolvedValue([])
})

it('does not clear the old work before the generation action resolves', async () => {
  const store = useGeneratorStore()
  store.topic = 'Existing draft'
  store.outlineModelName = 'text'
  store.setOutline('Keep', [{ index: 0, type: 'cover', content: 'Keep' }])
  store.recordId = 'saved'
  const start = vi.fn(async () => false)
  vi.mocked(useOutlineGeneration).mockReturnValue({
    generating: ref(false), cancelling: ref(false), error: ref(null), start, cancel: vi.fn(),
  })
  const app = renderer.createApp(HomeView)
  app.use(getActivePinia()!)
  app.component('RouterLink', { render: () => null })
  app.mount(root)
  unmount = () => app.unmount()
  await button('重新生成大纲')!.props.onClick()
  expect(start).toHaveBeenCalledOnce()
  expect(store.outline.raw).toBe('Keep')
  expect(store.recordId).toBe('saved')
})

it('offers cancellation during home generation', async () => {
  const cancel = vi.fn(async () => {})
  vi.mocked(useOutlineGeneration).mockReturnValue({
    generating: ref(true), cancelling: ref(false), error: ref(null), start: vi.fn(), cancel,
  })
  const app = renderer.createApp(HomeView)
  app.use(getActivePinia()!)
  app.component('RouterLink', { render: () => null })
  app.mount(root)
  unmount = () => app.unmount()
  await button('取消生成')!.props.onClick()
  expect(cancel).toHaveBeenCalledOnce()
})
afterEach(() => { unmount?.(); vi.unstubAllGlobals() })

it.each(['idle', 'generating', 'cancelling'])('keeps read-only diagnostics clickable while %s without image tasks', async state => {
  const store = useGeneratorStore()
  store.topic = 'Existing draft'
  store.setOutline('Topic', [{ index: 0, type: 'cover', content: 'Topic' }])
  store.outline.growth_recommendation = {
    platform: 'douyin', goal: 'follow', layout: '清单', image_style: 'collage',
    aspect_ratio: '9:16', content_structure: '步骤', reason: '匹配主题',
  }
  store.outline.generation_record_id = 'previous-outline'
  store.taskId = null
  vi.mocked(useOutlineGeneration).mockReturnValue({
    generating: ref(state === 'generating'), cancelling: ref(state === 'cancelling'),
    error: ref(null), start: vi.fn(), cancel: vi.fn(),
  })
  const app = renderer.createApp(HomeView)
  app.use(getActivePinia()!)
  app.component('RouterLink', { render: () => null })
  app.mount(root)
  unmount = () => app.unmount()
  expect(text()).toContain('本次推荐方案')
  expect(nodes().some(node => node.props['aria-label'] === '大纲推荐方案')).toBe(true)
  const showModal = vi.fn()
  const dialog = nodes().find(node => node.tag === 'dialog' && node.props['aria-labelledby'] === 'outline-diagnostics-title')!
  Object.assign(dialog, { showModal })
  const trigger = button('查看请求与响应')!
  expect(trigger.props.disabled).toBeFalsy()
  await trigger.props.onClick()
  await settle()
  expect(showModal).toHaveBeenCalledOnce()
  expect(listOutlineRuns).toHaveBeenCalledWith(state === 'idle' ? 'previous-outline' : undefined)
})
