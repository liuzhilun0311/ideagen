import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import { renderer, root, nodes, button, settle } from '../history/renderer'
import ImagePromptInspector from '../../src/components/workspace/ImagePromptInspector.vue'
import { previewImagePrompt } from '../../src/api/imagePrompt'
import { useGeneratorStore } from '../../src/stores/generator'
import { resolveImageStyle } from '../../src/features/styles/catalog'

vi.mock('../../src/api/imagePrompt', () => ({ previewImagePrompt: vi.fn() }))
let unmount: (() => void) | undefined
beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  const store = useGeneratorStore()
  store.topic = '主题'
  store.imageModelName = 'images'
  store.outline.pages = [
    { index: 0, type: 'cover', content: '单页布局：封面\n主题' },
    { index: 1, type: 'content', content: '单页布局：对比\n要点' },
  ]
  store.imageStyle = { preset: 'auto', notes: '', recommendation: {
    preset: 'watercolor', reason: '氛围', alternatives: [],
  }, palette: { mode: 'auto', recommendation: 'lavender', reason: '柔和' } }
  vi.mocked(previewImagePrompt).mockReset().mockResolvedValue({
    prompt: 'PROMPT', parameters: { resolution: '2K', aspect_ratio: '3:4', quality: 'low', output_format: 'png' },
    gpt_images_parameters: { size: '1536x2048', quality: 'low', output_format: 'png', n: 1 },
    references: { count: 0, user_count: 0, cover_count: 0, mode: 'text_to_image' },
  })
})
afterEach(() => unmount?.())
function mount(suite: boolean) {
  const store = useGeneratorStore()
  const app = renderer.createApp(ImagePromptInspector, { index: 0, style: store.imageStyle, suite })
  app.use(getActivePinia()!)
  app.mount(root)
  unmount = () => app.unmount()
}
it.each([true, false])('resolves the same automatic style and palette as generation (suite=%s)', async suite => {
  mount(suite)
  await button(suite ? '预览提示词' : '预览本页提示词')!.props.onClick()
  await settle()
  expect(previewImagePrompt).toHaveBeenCalledWith(expect.objectContaining({
    image_style: resolveImageStyle(useGeneratorStore().imageStyle), provider_name: 'images',
  }))
})
it('switches the suite preview to the selected page layout', async () => {
  mount(true)
  await button('预览提示词')!.props.onClick()
  await settle()
  const select = nodes().find(node => node.props['aria-label'] === '预览页面')!
  select.props['onUpdate:modelValue'](1)
  await settle()
  await select.props.onChange()
  await settle()
  expect(previewImagePrompt).toHaveBeenLastCalledWith(expect.objectContaining({
    page: expect.objectContaining({ index: 1, content: '单页布局：对比\n要点' }),
  }))
})
