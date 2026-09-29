import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import ContentDisplay from '../../src/components/result/ContentDisplay.vue'
import { useGeneratorStore } from '../../src/stores/generator'
import { renderer, root, button, text } from './renderer'

let unmount: (() => void) | undefined
beforeEach(() => { setActivePinia(createPinia()) })
afterEach(() => {
  unmount?.()
  root.children = []
  vi.unstubAllGlobals()
})

function mount(selectedOnly = true) {
  const app = renderer.createApp(ContentDisplay, { selectedOnly })
  app.mount(root)
  unmount = () => app.unmount()
}

it('previews and copies only the selected title without changing alternatives', async () => {
  const store = useGeneratorStore()
  Object.assign(store.content, {
    titles: ['Alternative title', 'Chosen title'], selectedTitleIndex: 1,
    copywriting: 'Body text', tags: ['sample'],
  })
  const snapshot = JSON.stringify(store.content)
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  mount()
  expect(text()).toContain('Chosen title')
  expect(text()).not.toContain('Alternative title')
  expect(text()).toContain('Body text')
  expect(text()).toContain('#sample')
  await button('复制标题')!.props.onClick()
  expect(writeText).toHaveBeenCalledWith('Chosen title')
  expect(JSON.stringify(store.content)).toBe(snapshot)
  store.content.selectedTitleIndex = 0
  await nextTick()
  expect(text()).toContain('Alternative title')
  expect(text()).not.toContain('Chosen title')
})

it('handles invalid selections and empty titles', async () => {
  const store = useGeneratorStore()
  Object.assign(store.content, {
    titles: ['First title', 'Other title'], selectedTitleIndex: 99, copywriting: 'Body',
  })
  mount()
  expect(text()).toContain('First title')
  expect(text()).not.toContain('Other title')
  store.content.titles = []
  await nextTick()
  expect(text()).toContain('暂无标题')
  expect(button('复制标题')!.props.disabled).toBe(true)
})

it('retains all candidates outside selected-only preview mode', () => {
  const store = useGeneratorStore()
  store.content.titles = ['First title', 'Second title']
  mount(false)
  expect(text()).toContain('First title')
  expect(text()).toContain('Second title')
  expect(button('复制全部标题')).toBeTruthy()
})
