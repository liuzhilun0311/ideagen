import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createRenderer, h, nextTick, reactive } from 'vue'
import ImageDownloadDialog from '../../src/components/common/ImageDownloadDialog.vue'
import { exportImageDownload } from '../../src/utils/imageDownload'

vi.mock('../../src/utils/imageDownload', async original => ({
  ...await original<typeof import('../../src/utils/imageDownload')>(),
  exportImageDownload: vi.fn().mockResolvedValue({ status: 'saved', message: '已保存到所选文件夹' }),
}))
const location = { directoryName: '作品', relativePath: 'ideagen_test' }
class Node {
  children: Node[] = []
  parent: Node | null = null
  props: Record<string, any> = {}
  text = ''
  value: unknown
  selected = false
  selectedIndex = -1
  focus = vi.fn()
  addEventListener = vi.fn()
  removeEventListener = vi.fn()
  constructor(public tagName: string) {}
  get options() { return this.children }
  getRootNode() { return { activeElement: null } }
}
let root: Node
let dispose: () => void
const renderer = createRenderer<Node, Node>({
  createElement: tag => new Node(tag.toUpperCase()),
  createText: text => Object.assign(new Node('#text'), { text }),
  createComment: () => new Node('#comment'),
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
  remove: node => { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) },
  setScopeId: () => {},
  querySelector: () => root,
})
function nodes(node = root): Node[] { return [node, ...node.children.flatMap(child => nodes(child))] }
function text(node: Node): string { return node.text + node.children.map(text).join('') }
function button(label: string) { return nodes().find(node => node.tagName === 'BUTTON' && text(node).trim() === label)! }
function select(id = 'download-version') { return nodes().find(node => node.tagName === 'SELECT' && node.props.id === id)! }
function copyButton() { return nodes().find(node => node.props['aria-label'] === '复制目录位置')! }
function locationInput() { return nodes().find(node => node.props.id === 'download-location')! }
function mount(pages = [{ index: 0, original_url: '/original.png', processed_url: '/processed.png' as string | null }]) {
  const props = reactive({ visible: false, pages, loading: false, loadError: '' })
  root = new Node('ROOT')
  const app = renderer.createApp({ render: () => h(ImageDownloadDialog, props) })
  app.mount(new Node('APP'))
  dispose = () => app.unmount()
  props.visible = true
  return props
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(exportImageDownload).mockResolvedValue({ status: 'saved', location, message: '已保存到所选文件夹' })
  vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
  vi.stubGlobal('document', { activeElement: null })
  vi.stubGlobal('Document', class {})
  vi.stubGlobal('ShadowRoot', class {})
})
afterEach(() => { dispose?.(); vi.unstubAllGlobals() })

it.each(['saved', 'submitted'] as const)('replaces download controls with a clear %s result and blocks duplicate submission', async status => {
  vi.mocked(exportImageDownload).mockResolvedValue(status === 'saved'
    ? { status, location, message: 'Result detail' } : { status, message: 'Result detail' })
  const props = mount()
  await nextTick()
  const download = button('下载').props.onClick
  await download()
  await nextTick()
  expect(button('下载')).toBeUndefined()
  expect(select()).toBeUndefined()
  expect(button('完成')).toBeDefined()
  if (status === 'saved') {
    expect(locationInput().value).toBe('作品/ideagen_test')
    expect(text(root)).toContain('非完整磁盘路径')
    await copyButton().props.onClick()
    await nextTick()
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('作品/ideagen_test')
    expect(text(root)).toContain('目录位置已复制')
    expect(exportImageDownload).toHaveBeenCalledTimes(1)
  } else {
    expect(copyButton()).toBeUndefined()
    expect(locationInput()).toBeUndefined()
  }
  expect(button('查看保存位置')).toBeUndefined()
  expect(text(root)).toContain(status === 'saved' ? '保存完成' : '已提交浏览器下载')
  await download()
  expect(exportImageDownload).toHaveBeenCalledTimes(1)
  props.visible = false
  await nextTick()
  props.visible = true
  await nextTick()
  expect(button('下载')).toBeDefined()
  expect(locationInput()).toBeUndefined()
  expect(text(root)).not.toContain('目录位置已复制')
})

it('defaults to a folder and offers explicit ZIP without changing the image version', async () => {
  vi.mocked(exportImageDownload).mockResolvedValue({ status: 'submitted', message: 'Browser download' })
  const props = mount()
  await nextTick()
  expect(select('download-format').options[select('download-format').selectedIndex]?.value).toBe('directory')
  select('download-format').props['onUpdate:modelValue']('zip')
  await nextTick()
  await button('下载').props.onClick()
  expect(exportImageDownload).toHaveBeenCalledWith(expect.objectContaining({
    format: 'zip', files: [{ index: 0, version: 'processed', url: '/processed.png', name: 'processed/page_1.png' }],
  }))
  props.visible = false
  await nextTick()
  props.visible = true
  await nextTick()
  expect(select('download-format').options[select('download-format').selectedIndex]?.value).toBe('directory')
})

it('keeps the location selectable if clipboard permission is denied', async () => {
  vi.mocked(navigator.clipboard.writeText).mockRejectedValue(new Error('Denied'))
  mount()
  await nextTick()
  await button('下载').props.onClick()
  await nextTick()
  await copyButton().props.onClick()
  await nextTick()
  expect(text(root)).toContain('复制失败')
  expect(text(root)).not.toContain('目录位置已复制')
  expect(locationInput().value).toBe('作品/ideagen_test')
  expect(locationInput().props.readonly).not.toBeUndefined()
  expect(copyButton().props.disabled).toBe(false)
})

it('keeps cancellation retryable without claiming success', async () => {
  vi.mocked(exportImageDownload).mockResolvedValue({ status: 'cancelled', message: '已取消下载' })
  mount()
  await nextTick()
  await button('下载').props.onClick()
  await nextTick()
  expect(button('完成')).toBeUndefined()
  expect(button('下载')).toBeDefined()
})

it('keeps failures visible with an explicit retry action', async () => {
  vi.mocked(exportImageDownload).mockRejectedValue(new Error('Network failed'))
  mount()
  await nextTick()
  await button('下载').props.onClick()
  await nextTick()
  expect(button('完成')).toBeUndefined()
  expect(button('重试下载')).toBeDefined()
  expect(text(root)).toContain('Network failed')
})

it('defaults to processed on every opening independently of previous selection', async () => {
  const props = mount()
  await nextTick()
  expect(select().options[select().selectedIndex]?.value).toBe('processed')
  select().props['onUpdate:modelValue']('original')
  await nextTick()
  props.visible = false
  await nextTick()
  props.visible = true
  await nextTick()
  expect(select().options[select().selectedIndex]?.value).toBe('processed')
})

it('requires explicit partial confirmation and exports only selected processed files', async () => {
  mount([
    { index: 0, original_url: '/original.png', processed_url: '/processed.png' },
    { index: 1, original_url: '/original-1.png', processed_url: null },
  ])
  await nextTick()
  expect(button('下载').props.disabled).toBe(true)
  nodes().find(node => node.tagName === 'INPUT')!.props['onUpdate:modelValue'](true)
  await nextTick()
  expect(button('下载').props.disabled).toBe(false)
  await button('下载').props.onClick()
  expect(exportImageDownload).toHaveBeenCalledWith(expect.objectContaining({
    files: [{ index: 0, version: 'processed', url: '/processed.png', name: 'processed/page_1.png' }],
  }))
})

it('does not create empty downloads and allows explicit original selection', async () => {
  mount([{ index: 3, original_url: '/original.png', processed_url: null }])
  await nextTick()
  expect(button('下载').props.disabled).toBe(true)
  expect(nodes().some(node => node.tagName === 'INPUT')).toBe(false)
  select().props['onUpdate:modelValue']('original')
  await nextTick()
  expect(button('下载').props.disabled).toBe(false)
})

it('blocks export while version reads fail or are pending', async () => {
  const props = mount()
  await nextTick()
  props.loading = true
  await nextTick()
  expect(button('下载').props.disabled).toBe(true)
  props.loading = false
  props.loadError = '版本读取失败'
  await nextTick()
  expect(button('下载').props.disabled).toBe(true)
  expect(text(root)).toContain('版本读取失败')
})
