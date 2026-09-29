import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { renderer, root, nodes, button, text } from '../history/renderer'
import NewCreationButton from '../../src/components/workspace/NewCreationButton.vue'
import { useGeneratorStore } from '../../src/stores/generator'
import { useStudioSession } from '../../src/stores/studioSession'
import { createHistory, updateHistory } from '../../src/api/history'

const { push } = vi.hoisted(() => ({ push: vi.fn(async () => undefined) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('../../src/api/history', () => ({ createHistory: vi.fn(), updateHistory: vi.fn() }))

let unmount: (() => void) | undefined
let close: ReturnType<typeof vi.fn>
let show: ReturnType<typeof vi.fn>
function mount() {
  const app = renderer.createApp(NewCreationButton)
  app.mount(root)
  unmount = () => app.unmount()
  const dialog = nodes().find(node => node.tag === 'dialog')!
  close = vi.fn()
  show = vi.fn()
  Object.assign(dialog, { close, showModal: show })
}
beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  const store = useGeneratorStore()
  store.topic = 'Current work'
  store.setOutline('Outline', [{ index: 0, type: 'cover', content: 'Cover' }])
  store.setContent(['Title'], 'Manual text', [])
  vi.mocked(createHistory).mockResolvedValue({ success: true, record_id: 'saved-work' })
  vi.mocked(updateHistory).mockResolvedValue({ success: true })
})
afterEach(() => unmount?.())

it('cancel keeps the current work untouched', async () => {
  mount()
  const store = useGeneratorStore()
  const snapshot = JSON.stringify(store.$state)
  button('新建创作')!.props.onClick()
  expect(show).toHaveBeenCalledOnce()
  button('取消')!.props.onClick()
  expect(close).toHaveBeenCalledOnce()
  expect(JSON.stringify(store.$state)).toBe(snapshot)
  expect(push).not.toHaveBeenCalled()
})

it('saves all current content before clearing the working draft', async () => {
  mount()
  await button('保存并新建')!.props.onClick()
  expect(updateHistory).toHaveBeenCalledWith('saved-work', expect.objectContaining({
    content: expect.objectContaining({ copywriting: 'Manual text' }),
    title: 'Current work',
  }))
  expect(useGeneratorStore().outline.pages).toEqual([])
  expect(useGeneratorStore().topic).toBe('')
  expect(useStudioSession().revision).toBe(1)
  expect(push).toHaveBeenCalledWith('/')
})

it('a failed save keeps the draft and dialog open', async () => {
  mount()
  vi.mocked(updateHistory).mockRejectedValue(new Error('Network unavailable'))
  await button('保存并新建')!.props.onClick()
  await nextTick()
  expect(useGeneratorStore().content.copywriting).toBe('Manual text')
  expect(useGeneratorStore().outline.pages).toHaveLength(1)
  expect(useStudioSession().revision).toBe(0)
  expect(text()).toContain('Network unavailable')
  expect(close).not.toHaveBeenCalled()
  expect(push).not.toHaveBeenCalled()
  expect(useStudioSession().draftSaving).toBe(false)
})

it('discard clears only the working draft without deleting saved records', async () => {
  useGeneratorStore().recordId = 'existing-record'
  mount()
  await button('放弃并新建')!.props.onClick()
  expect(createHistory).not.toHaveBeenCalled()
  expect(updateHistory).not.toHaveBeenCalled()
  expect(useGeneratorStore().recordId).toBeNull()
  expect(useGeneratorStore().outline.pages).toEqual([])
})

it('cannot save an incomplete outline or replace during generation', async () => {
  useGeneratorStore().outline.pages = []
  mount()
  expect(button('保存并新建')!.props.disabled).toBe(true)
  useStudioSession().trialBusy = true
  await nextTick()
  expect(button('新建创作')!.props.disabled).toBe(true)
  await button('放弃并新建')!.props.onClick()
  expect(useGeneratorStore().topic).toBe('Current work')
  expect(push).not.toHaveBeenCalled()
})
