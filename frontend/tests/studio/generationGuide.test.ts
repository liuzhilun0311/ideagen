import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import GenerationGuide from '../../src/components/workspace/GenerationGuide.vue'
import { generationGuides, type GenerationGuideKind } from '../../src/features/generationGuides'
import { useGeneratorStore } from '../../src/stores/generator'
import { renderer, root, nodes, button, text, Node } from '../history/renderer'

let unmount: (() => void) | undefined
beforeEach(() => { setActivePinia(createPinia()) })
afterEach(() => { unmount?.(); root.children = [] })

it.each<GenerationGuideKind>(['outline', 'images', 'copy'])('opens and closes the %s guide without changing the draft', async kind => {
  const store = useGeneratorStore()
  store.topic = 'Existing work'
  store.referenceRoles = ['subject']
  const snapshot = JSON.stringify(store.$state)
  const showModal = vi.fn()
  const close = vi.fn()
  Object.assign(Node.prototype, { showModal, close })
  const app = renderer.createApp(GenerationGuide, { kind })
  app.mount(root)
  unmount = () => app.unmount()
  const trigger = button(generationGuides[kind].title)!
  trigger.props.onClick({ stopPropagation: vi.fn() })
  await nextTick()
  const dialog = nodes().find(node => node.tag === 'dialog')!
  await nextTick()
  expect(showModal).toHaveBeenCalledOnce()
  expect(trigger.props['aria-expanded']).toBe(true)
  expect(text()).toContain('内容由什么组成')
  expect(text()).toContain('各项设置影响什么')
  expect(text()).toContain('什么时候生效')
  for (const factor of generationGuides[kind].factors) expect(text()).toContain(factor.name)
  button(`关闭${generationGuides[kind].title}`)!.props.onClick()
  expect(close).toHaveBeenCalledOnce()
  dialog.props.onClose()
  await nextTick()
  expect(trigger.props['aria-expanded']).toBe(false)
  expect(JSON.stringify(store.$state)).toBe(snapshot)
})

it('explains reference boundaries and separates image layout from copy structure', () => {
  expect(generationGuides.images.factors.find(item => item.name === '上传参考图片')?.effect).toContain('仅借鉴你勾选的维度')
  expect(generationGuides.images.factors.find(item => item.name === '参考第一张图')?.effect).toContain('独立的一致性开关')
  expect(generationGuides.copy.factors.find(item => item.name === '正文结构')?.effect).toContain('不会重新排列大纲页面或改变图片布局')
  expect(generationGuides.outline.rules.join('')).toContain('不会自动重写已有大纲')
})
