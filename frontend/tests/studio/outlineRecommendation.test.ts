import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import { renderer, root, nodes, button, text } from '../history/renderer'
import OutlineRecommendation from '../../src/components/workspace/OutlineRecommendation.vue'
import { useGeneratorStore } from '../../src/stores/generator'

let unmount: (() => void) | undefined
beforeEach(() => { setActivePinia(createPinia()) })
afterEach(() => { unmount?.() })
function mount() {
  const app = renderer.createApp(OutlineRecommendation)
  app.use(getActivePinia()!)
  app.mount(root)
  unmount = () => app.unmount()
}
function draft() {
  const store = useGeneratorStore()
  store.setOutline('主题', [{ index: 0, type: 'cover', content: '主题' }])
  store.outline.growth_recommendation = {
    platform: 'douyin', goal: 'follow', layout: '清单', image_style: 'collage',
    aspect_ratio: '9:16', content_structure: '问题到方法', reason: '突出核心步骤',
  }
  return store
}
it('disables the recommendation button before an outline exists', () => {
  mount()
  expect(button('本次推荐方案')!.props.disabled).toBe(true)
})
it('opens and closes a read-only modal without changing generation settings', () => {
  const store = draft()
  const before = JSON.stringify(store.$state)
  mount()
  const dialog = nodes().find(node => node.tag === 'dialog')!
  const showModal = vi.fn()
  const close = vi.fn()
  Object.assign(dialog, { showModal, close })
  expect(dialog.props.open).toBeUndefined()
  button('本次推荐方案')!.props.onClick()
  expect(showModal).toHaveBeenCalledOnce()
  button('关闭推荐方案')!.props.onClick()
  expect(close).toHaveBeenCalledOnce()
  for (const label of ['应用全部', '只应用布局', '只应用风格']) expect(button(label)).toBeUndefined()
  expect(JSON.stringify(store.$state)).toBe(before)
})
it('keeps every recommendation field in the dialog', () => {
  draft()
  mount()
  const dialog = nodes().find(node => node.tag === 'dialog')!
  for (const value of ['抖音', '涨粉关注', '清单', '9:16', '问题到方法', '突出核心步骤']) {
    expect(text(dialog)).toContain(value)
  }
})
it('shows an explicit empty state for historical outlines without recommendations', () => {
  const store = draft()
  store.outline.growth_recommendation = undefined
  mount()
  expect(button('本次推荐方案')!.props.disabled).toBe(false)
  expect(text()).toContain('这份大纲没有保存推荐方案')
})
