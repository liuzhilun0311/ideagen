import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createRenderer, h, nextTick, reactive } from 'vue'
import PageEditor from '../../src/components/workspace/PageEditor.vue'
import PostprocessingToolbar from '../../src/components/workspace/PostprocessingToolbar.vue'
import type { ProcessingPage } from '../../src/api/postprocessing'

const { dialog } = vi.hoisted(() => ({ dialog: vi.fn() }))
vi.mock('../../src/components/common/ImageDownloadDialog.vue', () => ({
  default: {
    props: ['visible', 'pages', 'loading', 'loadError'],
    setup: (props: object) => () => { dialog({ ...props }); return null },
  },
}))
class HostNode {
  children: HostNode[] = []
  parent: HostNode | null = null
  props: Record<string, any> = {}
  value: unknown = ''
  text = ''
  selected = false
  constructor(public tagName: string) {}
  get options() { return this.children.filter(child => child.tagName === 'SELECT' || child.tagName === 'OPTION') }
  getRootNode() { return { activeElement: null } }
  addEventListener = vi.fn()
  removeEventListener = vi.fn()
}
const renderer = createRenderer<HostNode, HostNode>({
  createElement: tag => new HostNode(tag.toUpperCase()),
  createText: text => Object.assign(new HostNode('#text'), { text }),
  createComment: () => new HostNode('#comment'),
  setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.text = text; node.children = [] },
  parentNode: node => node.parent,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] ?? null,
  patchProp: (node, key, _previous, value) => { node.props[key] = value; if (key === 'value') node.value = value },
  insert: (node, parent, anchor) => {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
    node.parent = parent
  },
  remove: node => {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    node.parent = null
  },
  setScopeId: () => {},
})
let root: HostNode
let unmount: (() => void) | undefined
function nodes(node = root): HostNode[] { return [node, ...node.children.flatMap(child => nodes(child))] }
function text(node: HostNode): string { return node.text + node.children.map(text).join('') }
function find(predicate: (node: HostNode) => boolean) {
  const result = nodes().find(predicate)
  if (!result) throw new Error('Missing control')
  return result
}
function label(value: string) { return find(node => node.props['aria-label'] === value) }
function button(value: string) { return find(node => node.tagName === 'BUTTON' && text(node).trim() === value) }
function mount(render: () => ReturnType<typeof h>) {
  const app = renderer.createApp({ render })
  root = new HostNode('ROOT')
  app.mount(root)
  unmount = () => app.unmount()
}
const page = (index = 0, overrides: Partial<ProcessingPage> = {}): ProcessingPage => ({
  index, source_revision: 'revision-1', original_url: '/original.png', processed_url: '/processed.png',
  status: 'done', error: '', strength: 'light', adopted: 'processed', ...overrides,
})
function mountEditor(overrides: Partial<ProcessingPage> = {}) {
  const preview = vi.fn(), adopt = vi.fn(), process = vi.fn(), retry = vi.fn()
  const props = reactive({
    page: { index: 0, type: 'cover' as const, content: 'Synthetic content' },
    image: { index: 0, url: '/fallback.png', status: 'done' as const },
    processingPage: page(0, overrides), locked: false, canRetry: true,
    onPreview: preview, onAdopt: adopt, onProcess: process, onRetry: retry,
  })
  mount(() => h(PageEditor, props))
  return { props, preview, adopt, process, retry }
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('window', { confirm: vi.fn(() => true) })
  vi.stubGlobal('Document', class {})
  vi.stubGlobal('ShadowRoot', class {})
})
afterEach(() => { unmount?.(); vi.unstubAllGlobals() })

it('previews the viewed original/processed version and never adopts by switching or comparing', async () => {
  const { preview, adopt } = mountEditor()
  expect(button('处理图').props['aria-pressed']).toBe(true)
  button('原图').props.onClick()
  await nextTick()
  label('预览原图').props.onClick()
  expect(preview).toHaveBeenLastCalledWith('/original.png', 'original')
  button('处理图').props.onClick()
  await nextTick()
  label('预览处理图').props.onClick()
  expect(preview).toHaveBeenLastCalledWith('/processed.png', 'processed')
  button('对比').props.onClick()
  await nextTick()
  expect(nodes().filter(node => node.tagName === 'IMG')).toHaveLength(2)
  label('预览原图').props.onClick()
  expect(preview).toHaveBeenLastCalledWith('/original.png', 'original')
  expect(adopt).not.toHaveBeenCalled()
  label('采用原图').props.onClick()
  expect(adopt).toHaveBeenCalledWith('original', 'revision-1')
})

it('follows new adopted output unless the user explicitly chose a comparison view', async () => {
  const { props } = mountEditor({ processed_url: null, adopted: 'original', status: 'processing' })
  props.processingPage = page()
  await nextTick()
  expect(button('处理图').props['aria-pressed']).toBe(true)
  button('原图').props.onClick()
  props.processingPage = page(0, { processed_url: '/processed-new.png' })
  await nextTick()
  expect(button('原图').props['aria-pressed']).toBe(true)
})

it('keeps the actual strength label while changing next-run strength without processing', async () => {
  const { process } = mountEditor()
  label('当前图片处理强度').props['onUpdate:modelValue']('heavy')
  await nextTick()
  expect(text(root)).toContain('处理图 · 轻度')
  expect(process).not.toHaveBeenCalled()
  button('重新处理').props.onClick()
  expect(process).toHaveBeenCalledWith('heavy', true)
})

it('defaults new processing to medium and retains generation retry while processing is queued', async () => {
  const { props, process, retry } = mountEditor({ processed_url: null, adopted: 'original', strength: null, status: 'idle' })
  button('处理当前图片').props.onClick()
  expect(process).toHaveBeenCalledWith('medium', false)
  props.processingPage.status = 'queued'
  await nextTick()
  expect(button('处理当前图片').props.disabled).toBe(true)
  expect(label('重新生成当前图片').props.disabled).toBe(false)
  label('重新生成当前图片').props.onClick()
  expect(retry).toHaveBeenCalledOnce()
})

it('keeps previous processed output available after failure and clears viewed version on source replacement', async () => {
  const { props, preview } = mountEditor({ status: 'error', error: 'Failed but old output is usable' })
  button('处理图').props.onClick()
  await nextTick()
  label('预览处理图').props.onClick()
  expect(preview).toHaveBeenCalledWith('/processed.png', 'processed')
  expect(text(root)).toContain('Failed but old output is usable')
  props.processingPage = page(0, { source_revision: 'revision-2', processed_url: null, status: 'idle', adopted: 'original' })
  await nextTick()
  expect(button('原图').props['aria-pressed']).toBe(true)
  expect(button('处理图').props.disabled).toBe(true)
})

it('opens the shared download with both explicit URLs, never processing or adopting', async () => {
  const { process, adopt } = mountEditor()
  button('处理图').props.onClick()
  await nextTick()
  label('下载当前图片').props.onClick()
  await nextTick()
  expect(dialog).toHaveBeenLastCalledWith(expect.objectContaining({
    visible: true, pages: [{ index: 0, original_url: '/original.png', processed_url: '/processed.png' }],
  }))
  expect(process).not.toHaveBeenCalled()
  expect(adopt).not.toHaveBeenCalled()
})

it('skips valid/busy pages by default and confirms force with a strength snapshot', async () => {
  const process = vi.fn()
  const pages = [page(0), page(1, { processed_url: null, status: 'idle' }), page(2, { status: 'queued', processed_url: null }),
    page(3, { status: 'error', processed_url: null })]
  mount(() => h(PostprocessingToolbar, { pages, submitting: false, savingPreferences: false, onProcess: process }))
  button('全部去AI化 2 张').props.onClick()
  expect(process).toHaveBeenLastCalledWith([1, 3], 'medium', false)
  label('去AI化强度').props['onUpdate:modelValue']('medium')
  await nextTick()
  vi.mocked(window.confirm).mockReturnValueOnce(false)
  button('重新去AI化 4 张').props.onClick()
  expect(process).toHaveBeenCalledTimes(1)
  button('重新去AI化 4 张').props.onClick()
  expect(process).toHaveBeenLastCalledWith([0, 1, 3], 'medium', true)
  button('重试失败页 · 1').props.onClick()
  expect(process).toHaveBeenLastCalledWith([3], 'medium', false)
})

it('automatic preferences never submit processing and roll back when save fails', async () => {
  const process = vi.fn(), preferences = vi.fn()
  const props = reactive({ pages: [], submitting: false, savingPreferences: false,
    preferences: { automatic: false, strength: 'light' as const }, onProcess: process, onPreferences: preferences })
  mount(() => h(PostprocessingToolbar, props))
  const automatic = label('生成后自动去AI化')
  automatic.props['onUpdate:modelValue'](true)
  automatic.props.onChange()
  expect(preferences).toHaveBeenCalledWith(true, 'light')
  expect(process).not.toHaveBeenCalled()
  props.savingPreferences = true
  await nextTick()
  props.savingPreferences = false
  await nextTick()
  automatic.props.onChange()
  expect(preferences).toHaveBeenLastCalledWith(false, 'light')
})

it('shares one persisted strength between automatic and batch processing', async () => {
  const process = vi.fn(), preferences = vi.fn()
  const props = reactive({ pages: [page(0, { processed_url: null, status: 'idle' })],
    submitting: false, savingPreferences: false,
    preferences: { automatic: true, strength: 'light' as 'light' | 'medium' },
    onProcess: process, onPreferences: preferences })
  mount(() => h(PostprocessingToolbar, props))
  expect(nodes().filter(node => node.tagName === 'SELECT')).toHaveLength(2)
  const control = label('去AI化强度')
  control.props['onUpdate:modelValue']('medium')
  control.props.onChange()
  expect(preferences).toHaveBeenCalledWith(true, 'medium')
  expect(process).not.toHaveBeenCalled()
  props.savingPreferences = true
  await nextTick()
  expect(button('全部去AI化 1 张').props.disabled).toBe(true)
  props.preferences = { automatic: true, strength: 'medium' }
  props.savingPreferences = false
  await nextTick()
  button('全部去AI化 1 张').props.onClick()
  expect(process).toHaveBeenCalledWith([0], 'medium', false)
})

it('restores the saved shared strength when saving fails', async () => {
  const process = vi.fn()
  const props = reactive({ pages: [page(0, { processed_url: null, status: 'idle' })],
    submitting: false, savingPreferences: false,
    preferences: { automatic: false, strength: 'light' as const }, onProcess: process })
  mount(() => h(PostprocessingToolbar, props))
  label('去AI化强度').props['onUpdate:modelValue']('heavy')
  props.savingPreferences = true
  await nextTick()
  props.savingPreferences = false
  await nextTick()
  button('全部去AI化 1 张').props.onClick()
  expect(process).toHaveBeenCalledWith([0], 'light', false)
})

it('confirms retries that would replace retained successful output on failed pages', () => {
  const process = vi.fn()
  mount(() => h(PostprocessingToolbar, {
    pages: [page(0, { status: 'error' })], submitting: false, savingPreferences: false, onProcess: process,
  }))
  vi.mocked(window.confirm).mockReturnValueOnce(false)
  button('重试失败页 · 1').props.onClick()
  expect(process).not.toHaveBeenCalled()
  button('重试失败页 · 1').props.onClick()
  expect(process).toHaveBeenCalledWith([0], 'medium', true)
})
