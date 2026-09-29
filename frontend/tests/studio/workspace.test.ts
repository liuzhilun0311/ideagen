import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createRenderer, h, KeepAlive, nextTick, type VNode } from 'vue'
import { RouterView } from 'vue-router'

vi.mock('vue-router', async importOriginal => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, createWebHistory: actual.createMemoryHistory }
})
vi.mock('../../src/components/common/ImageViewer.vue', () => ({ default: { render: () => null } }))
vi.mock('../../src/components/common/ImageDownloadDialog.vue', () => ({ default: { render: () => null } }))
vi.mock('../../src/api/postprocessing', () => ({
  getProcessingState: vi.fn(async () => ({ success: true, preferences: { automatic: false, strength: 'light' }, pages: [] })),
  updatePostprocessing: vi.fn(async () => ({ success: true, preferences: { automatic: false, strength: 'light' }, pages: [] })),
}))
vi.mock('../../src/api/candidates', () => ({
  listCandidates: vi.fn(async () => []), generateCandidate: vi.fn(), adoptCandidate: vi.fn(),
}))
vi.mock('../../src/views/HistoryView.vue', () => ({ default: { render: () => null } }))
vi.mock('../../src/api', () => ({
  generateContent: vi.fn(), cancelCurrentGeneration: vi.fn(),
  getConfig: vi.fn(), getPrompts: vi.fn(),
}))
vi.mock('../../src/api/history', () => ({
  createHistory: vi.fn(), updateHistory: vi.fn(), getHistory: vi.fn(),
}))
vi.mock('../../src/composables/useStudio', async importOriginal => {
  const actual = await importOriginal<typeof import('../../src/composables/useStudio')>()
  return { useStudio: vi.fn(actual.useStudio) }
})

import router from '../../src/router'
import WorkspaceView from '../../src/views/WorkspaceView.vue'
import App from '../../src/App.vue'
import { useStudio } from '../../src/composables/useStudio'
import { useGeneratorStore } from '../../src/stores/generator'
import { useStudioSession } from '../../src/stores/studioSession'
import { setToken } from '../../src/api/token'
import { generateContent, getConfig, getPrompts, type ContentResponse } from '../../src/api'
import { createHistory, updateHistory, getHistory } from '../../src/api/history'
import { getProcessingState } from '../../src/api/postprocessing'
import { listCandidates, generateCandidate, adoptCandidate, type ImageCandidate } from '../../src/api/candidates'

// A minimal Vue host exercises actual component lifetimes and handlers without a browser dependency.
class HostNode {
  style = { display: '' }
  children: HostNode[] = []
  parent: HostNode | null = null
  props: Record<string, any> = {}
  value: unknown = ''
  text = ''
  selected = false
  constructor(public tagName: string) {}
  get options() { return this.children.filter(child => child.tagName === 'OPTION') }
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
  patchProp: (node, key, _previous, value) => {
    node.props[key] = value
    if (key === 'value') node.value = value
  },
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
function find(predicate: (node: HostNode) => boolean) {
  const result = nodes().find(predicate)
  if (!result) throw new Error('Expected rendered control')
  return result
}
function byId(id: string) { return find(node => node.props.id === id) }
function byLabel(label: string) { return find(node => node.props['aria-label'] === label) }
function text(node: HostNode): string { return node.text + node.children.map(text).join('') }
function button(label: string) { return find(node => node.tagName === 'BUTTON' && text(node) === label) }
async function mount(path: string, fullApp = false) {
  await router.push(path)
  const app = renderer.createApp(fullApp ? App : {
    render: () => h(RouterView, null, {
      default: ({ Component }: { Component: VNode }) => h(KeepAlive, null, () => Component),
    }),
  })
  app.use(pinia)
  app.use(router)
  root = new HostNode('ROOT')
  app.mount(root)
  unmount = () => app.unmount()
  await vi.waitFor(() => expect(byId(path === '/workspace/copy' ? 'content-model' : 'images-model').props.disabled).toBe(false))
}
let pinia: ReturnType<typeof createPinia>
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listCandidates).mockResolvedValue([])
  pinia = createPinia()
  setActivePinia(pinia)
  setToken('test-token')
  vi.stubGlobal('window', {
    location: { href: 'http://localhost/workspace' },
    confirm: vi.fn(() => true), addEventListener: vi.fn(), removeEventListener: vi.fn(),
    scrollTo: vi.fn(), scrollY: 0,
  })
  vi.stubGlobal('Document', class {})
  vi.stubGlobal('ShadowRoot', class {})
  vi.mocked(getConfig).mockResolvedValue({
    success: true,
    config: {
      text_generation: { active_provider: 'text', providers: { text: { model: 'text' } } },
      image_generation: { active_provider: 'image', providers: { image: { model: 'image' } } },
    },
  })
  vi.mocked(getPrompts).mockResolvedValue({ success: true, prompts: { outline: [], content: [], image: [] } })
  vi.mocked(createHistory).mockResolvedValue({ success: true, record_id: 'record' })
  vi.mocked(updateHistory).mockResolvedValue({ success: true })
  vi.mocked(getProcessingState).mockResolvedValue({
    success: true, preferences: { automatic: false, strength: 'light' }, pages: [],
  })
  const store = useGeneratorStore()
  store.topic = 'Synthetic draft'
  store.setOutline('Outline', [
    { index: 0, type: 'cover', content: 'Cover' },
    { index: 1, type: 'content', content: 'Second page' },
  ])
  store.setContent(['Title'], 'Body', ['tag'])
})
afterEach(() => { unmount?.(); unmount = undefined; vi.unstubAllGlobals() })

it('keeps original pages and images when the structure transaction fails', async () => {
  const store = useGeneratorStore()
  store.recordId = 'record'
  store.taskId = 'old-task'
  store.images = [{ index: 0, url: '/old.png', status: 'done' }]
  const original = JSON.stringify(store.outline)
  vi.mocked(getHistory).mockResolvedValue({
    success: true, record: { id: 'record', outline: JSON.parse(original) } as any,
  })
  vi.mocked(updateHistory).mockImplementation(async (_id, payload) =>
    payload.structure_change ? { success: false, error: 'Conflict' } : { success: true })
  await mount('/workspace')
  byLabel('下移页面').props.onClick()
  await vi.waitFor(() => expect(text(root)).toContain('Conflict'))
  expect(JSON.stringify(store.outline)).toBe(original)
  expect(store.images[0]?.url).toBe('/old.png')
  expect(store.taskId).toBe('old-task')
  expect(useStudioSession().structureBusy).toBe(false)
})

it('saves new structure once, then detaches old images only on success', async () => {
  const store = useGeneratorStore()
  store.recordId = 'record'
  store.taskId = 'old-task'
  store.images = [{ index: 0, url: '/old.png', status: 'done' }]
  vi.mocked(getHistory).mockResolvedValue({
    success: true, record: { id: 'record', outline: JSON.parse(JSON.stringify(store.outline)) } as any,
  })
  let finish!: (value: { success: boolean }) => void
  vi.mocked(updateHistory).mockImplementation(async (_id, payload) =>
    payload.structure_change ? new Promise(resolve => { finish = resolve }) : { success: true })
  await mount('/workspace')
  const click = byLabel('下移页面').props.onClick
  click()
  await vi.waitFor(() => expect(finish).toBeTypeOf('function'))
  click()
  expect(store.images).toHaveLength(1)
  expect(store.outline.pages[0]?.content).toBe('Cover')
  finish({ success: true })
  await vi.waitFor(() => expect(store.taskId).toBeNull())
  expect(store.outline.pages.map(page => page.content)).toEqual(['Second page', 'Cover'])
  expect(store.images).toEqual([])
  expect(vi.mocked(updateHistory).mock.calls.filter(([, payload]) => payload.structure_change)).toHaveLength(1)
})

it('copies each title independently and publishes only the selected title', async () => {
  const store = useGeneratorStore()
  store.setContent(['First', 'Second'], 'Body', ['tag'])
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  await mount('/workspace/copy')
  expect(store.content.selectedTitleIndex).toBe(0)
  byLabel('采用标题 2').props['onUpdate:modelValue'](1)
  await nextTick()
  await byLabel('复制全部文案').props.onClick()
  expect(writeText).toHaveBeenLastCalledWith('Second\n\nBody\n\n#tag')
  await byLabel('复制标题 1').props.onClick()
  expect(writeText).toHaveBeenLastCalledWith('First')
  expect(store.content.selectedTitleIndex).toBe(1)
})

it('reuses the primary action slot for stopping a batch instead of adding another toolbar row', async () => {
  let finish!: (value: ImageCandidate) => void
  vi.mocked(generateCandidate).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const candidate: ImageCandidate = {
    id: 'generated', index: 0, style: { preset: 'infographic', notes: '' }, prompt: '',
    provider: 'image', status: 'ready', image_url: '/generated.png',
    adopted: true, stale: false, created_at: '',
  }
  vi.mocked(adoptCandidate).mockResolvedValue({ task_id: 'task', image_url: '/generated.png', candidate })
  await mount('/workspace')
  const pending = find(node => node.tagName === 'BUTTON' && text(node).startsWith('生成剩余')).props.onClick()
  await vi.waitFor(() => expect(generateCandidate).toHaveBeenCalledOnce())
  const stop = byLabel('停止后续生成')
  expect(stop.props.class).toContain('image-action')
  expect(nodes().filter(node => node.tagName === 'BUTTON' && text(node).startsWith('生成剩余'))).toHaveLength(0)
  stop.props.onClick()
  await nextTick()
  expect(byLabel('本张完成后停止').props.disabled).toBe(true)
  finish(candidate)
  await pending
  await nextTick()
  expect(generateCandidate).toHaveBeenCalledOnce()
  expect(nodes().some(node => node.props['aria-label'] === '停止后续生成')).toBe(false)
  expect(find(node => node.tagName === 'BUTTON' && text(node).startsWith('生成剩余')).props.class).toContain('image-action')
})

it('displays and copies tags with one hash prefix while keeping them editable', async () => {
  const store = useGeneratorStore()
  store.setContent(['Title'], 'Body', ['中文', '#旅行', '##美食'])
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  await mount('/workspace/copy')
  expect(byId('copy-tags').value).toBe('#中文 #旅行 #美食')
  await byLabel('复制全部标签').props.onClick()
  expect(writeText).toHaveBeenLastCalledWith('#中文 #旅行 #美食')
  byId('copy-tags').props['onUpdate:modelValue']('#春日 ##出行 普通标签 #')
  await nextTick()
  expect(store.content.tags).toEqual(['春日', '出行', '普通标签'])
  expect(byId('copy-tags').value).toBe('#春日 #出行 #普通标签')
  await byLabel('复制全部标签').props.onClick()
  expect(writeText).toHaveBeenLastCalledWith('#春日 #出行 #普通标签')
  byId('copy-tags').props['onUpdate:modelValue']('')
  await nextTick()
  expect(byLabel('复制全部标签').props.disabled).toBe(true)
})

it('selects a style without saving or generating until the user acts', async () => {
  await mount('/workspace')
  expect(byId('workspace-style').tagName).toBe('SELECT')
  await vi.waitFor(() => expect(byId('workspace-style').props.disabled).toBe(false))
  byId('workspace-style').props.onChange({ target: { value: 'comic' } })
  await nextTick()
  expect(useGeneratorStore().imageStyle).toMatchObject({ preset: 'comic', notes: '' })
  expect(createHistory).not.toHaveBeenCalled()
  expect(updateHistory).not.toHaveBeenCalled()
  await button('保存').props.onClick()
  expect(updateHistory).toHaveBeenCalledWith('record', expect.objectContaining({
    image_style: { preset: 'comic', notes: '' },
  }))
})

it.each(['/workspace', '/workspace/copy'])('does not render removed audit panels on %s', async path => {
  await mount(path)
  expect(text(root)).not.toContain('文案与图片一致性')
  expect(text(root)).not.toContain('本次生效设置')
  expect(text(root)).not.toContain('开始检查')
})

it('uses one candidate preview and reloads a broken image without generating again', async () => {
  useGeneratorStore().recordId = 'record'
  vi.mocked(listCandidates).mockResolvedValue([{
    id: 'trial', index: 0, style: { preset: 'ink', notes: '' }, prompt: 'Ink',
    provider: 'image', status: 'ready', image_url: '/api/image-candidates/record/trial/image',
    adopted: false, stale: false, created_at: '',
  }])
  await mount('/workspace')
  await vi.waitFor(() => expect(nodes().some(node => node.props.alt === '第 1 页水墨插画候选图')).toBe(true))
  expect(text(root)).not.toContain('图片待生成')
  find(node => node.props.alt === '第 1 页水墨插画候选图').props.onError()
  await nextTick()
  expect(text(root)).toContain('生成结果已保留，无需重新生成。')
  await button('重新加载图片').props.onClick()
  await nextTick()
  expect(find(node => node.props.alt === '第 1 页水墨插画候选图').props.src).toContain('reload=1')
  expect(generateCandidate).not.toHaveBeenCalled()
})

it('retains copy after page edits without showing a consistency reminder', async () => {
  const store = useGeneratorStore()
  store.content.source = { topic: store.topic, outline: 'Cover\n\n<page>\n\nSecond page' }
  await mount('/workspace/copy')
  expect(text(root)).not.toContain('页面内容已变化')
  store.updatePage(0, 'Changed page')
  await nextTick()
  expect(text(root)).not.toContain('页面内容已变化')
  expect(store.content.copywriting).toBe('Body')
  store.updatePage(0, 'Cover')
  await nextTick()
  expect(text(root)).not.toContain('页面内容已变化')
})

it('recovers a removed work after returning from history without losing text or model choices', async () => {
  const store = useGeneratorStore()
  store.recordId = 'removed'
  store.taskId = 'old-task'
  store.images = [{ index: 0, url: '/old.png', status: 'done' }]
  await mount('/workspace/copy')
  const model = store.contentModelName
  await router.push('/history')
  vi.mocked(getProcessingState).mockRejectedValue({
    code: 'RESOURCE_NOT_FOUND', title: 'Missing', detail: 'Removed', status: 404,
  })
  await router.push('/workspace/copy')
  await vi.waitFor(() => expect(button('转为新作品继续')).toBeTruthy())
  expect(store.recordId).toBe('removed')
  expect(button('保存').props.disabled).toBe(true)
  await button('转为新作品继续').props.onClick()
  await nextTick()
  expect(store.recordId).toBeNull()
  expect(store.taskId).toBeNull()
  expect(store.images).toEqual([])
  expect(store.topic).toBe('Synthetic draft')
  expect(store.outline.pages).toHaveLength(2)
  expect(store.content.copywriting).toBe('Body')
  expect(store.contentModelName).toBe(model)
  expect(router.currentRoute.value.path).toBe('/workspace/copy')
  expect(text(root)).toContain('已转为新草稿')
  expect(JSON.parse(localStorage.getItem('generator-state')!).recordId).toBeNull()
  await button('保存').props.onClick()
  expect(createHistory).toHaveBeenCalledWith('Synthetic draft', expect.any(Object), undefined)
  expect(store.recordId).toBe('record')
})

it('does not offer detachment or discard a draft for a transient processing failure', async () => {
  const store = useGeneratorStore()
  store.recordId = 'valid'
  store.taskId = 'task'
  vi.mocked(getProcessingState).mockRejectedValue({
    code: 'UPSTREAM_ERROR', title: 'Temporary', detail: 'Retry later', status: 500,
  })
  await mount('/workspace')
  expect(nodes().some(node => node.tagName === 'BUTTON' && text(node) === '转为新作品继续')).toBe(false)
  expect(store.recordId).toBe('valid')
  expect(store.taskId).toBe('task')
  expect(store.content.copywriting).toBe('Body')
})

it('registers both guarded URLs with the identical workspace component', async () => {
  for (const path of ['/workspace', '/workspace/copy']) {
    expect(router.resolve(path).matched[0].components?.default).toBe(WorkspaceView)
    setToken('')
    await router.push(path)
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe(path)
    setToken('test-token')
    useGeneratorStore().outline.pages = []
    await router.push(path)
    expect(router.currentRoute.value.name).toBe('home')
  }
})

it('renders only image controls on the image page and only text controls on the copy page', async () => {
  await mount('/workspace')
  expect(byLabel('作品结构')).toBeDefined()
  expect(byId('page-content')).toBeDefined()
  expect(byId('images-model')).toBeDefined()
  expect(nodes().some(node => node.props.id === 'content-model')).toBe(false)
  expect(byId('outline-model')).toBeDefined()
  expect(find(node => node.tagName === 'DETAILS').props.open).toBeUndefined()
  expect(nodes().some(node => node.tagName === 'BUTTON' && text(node).includes('生成文案'))).toBe(false)
  expect(nodes().filter(node => node.tagName === 'BUTTON' && text(node).startsWith('生成剩余'))).toHaveLength(1)
  expect(nodes().filter(node => node.tagName === 'BUTTON' && text(node) === '生成本页 · 1 张')).toHaveLength(1)
  expect(nodes(byLabel('生成设置')).some(node => node.tagName === 'BUTTON' && text(node) === '生成全部图片')).toBe(false)
  await router.push('/workspace/copy')
  await nextTick()
  expect(byId('copy-body')).toBeDefined()
  expect(byId('content-model')).toBeDefined()
  expect(nodes().some(node => node.props['aria-label'] === '作品结构')).toBe(false)
  expect(nodes().some(node => ['images-model', 'outline-model', 'page-content'].includes(node.props.id))).toBe(false)
  expect(nodes().some(node => node.tagName === 'BUTTON' && /生成.*图片|导出大纲/.test(text(node)))).toBe(false)
  expect(button('预览作品').props.disabled).toBe(true)
  expect(nodes().filter(node => node.props['aria-label'] === '创作页面')).toHaveLength(1)
  expect(nodes().filter(node => node.tagName === 'BUTTON' && text(node) === '重新生成文案')).toHaveLength(1)
  expect(nodes(byLabel('生成设置')).some(node => node.tagName === 'BUTTON' && text(node) === '预览完整文案提示词')).toBe(true)
  expect(nodes().some(node => node.props.id === 'content-prompt')).toBe(false)
  expect(nodes().filter(node => ['copy-style', 'copy-structure', 'copy-length'].includes(node.props.id))).toHaveLength(3)
  useGeneratorStore().content.copywriting = ''
  await nextTick()
  expect(nodes().filter(node => node.tagName === 'BUTTON' && text(node) === '生成文案')).toHaveLength(1)
})

it('keeps empty copy sections distinct and places generation before parameters', async () => {
  await mount('/workspace/copy')
  const store = useGeneratorStore()
  store.content.titles = []
  store.content.copywriting = ''
  store.content.tags = []
  store.content.status = 'idle'
  await nextTick()
  expect(text(byLabel('文案制作'))).toContain('待生成标题')
  expect(byId('copy-body').props.placeholder).toBe('待生成正文')
  expect(byId('copy-tags').props.placeholder).toBe('待生成标签')
  expect(byId('copy-body-heading')).toBeDefined()
  expect(byId('copy-tags-heading')).toBeDefined()
  const settings = nodes(byLabel('文案制作设置'))
  const generateIndex = settings.findIndex(node => node.tagName === 'BUTTON' && text(node) === '生成文案')
  const parametersIndex = settings.findIndex(node => node.props['aria-label'] === '生成设置')
  expect(generateIndex).toBeGreaterThanOrEqual(0)
  expect(parametersIndex).toBeGreaterThan(generateIndex)
})

it('keeps selected page, unsaved copy, models and live task ownership across routes', async () => {
  await mount('/workspace')
  const studio = vi.mocked(useStudio).mock.results[0].value as ReturnType<typeof useStudio>
  const choices = nodes().filter(node => node.props.class?.includes('page-choice'))
  choices[1].props.onClick()
  await nextTick()
  byId('page-content').props.onInput({ target: { value: 'Unsaved page' } })
  await router.push('/workspace/copy')
  await nextTick()
  byId('copy-body').props['onUpdate:modelValue']('Unsaved copy')
  const session = useStudioSession()
  expect(session.dirty).toBe(true)
  let finish!: (value: ContentResponse) => void
  vi.mocked(generateContent).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const pending = studio.run('content')
  await vi.waitFor(() => expect(generateContent).toHaveBeenCalledOnce())
  await router.push('/workspace')
  await nextTick()
  expect(byId('page-content').props.value).toBe('Unsaved page')
  expect(nodes().some(node => node.tagName === 'BUTTON' && text(node).startsWith('生成剩余'))).toBe(false)
  expect(button('取消文案生成').props.disabled).toBe(false)
  expect(button('取消文案生成').props.class).toContain('image-action')
  expect(session.busy).toBe(true)
  expect(session.replaceDraft()).toBe(false)
  await studio.run('images')
  expect(generateContent).toHaveBeenCalledOnce()
  expect(vi.mocked(useStudio)).toHaveBeenCalledOnce()
  expect(studio.store.content.copywriting).toBe('Unsaved copy')
  expect(studio.store.contentModelName).toBe('text')
  expect(studio.store.recordId).toBe('record')
  finish({ success: true, titles: ['Generated'], copywriting: 'Completed', tags: [] })
  await pending
  await router.push('/workspace/copy')
  await nextTick()
  expect(byId('copy-body').value).toBe('Completed')
  expect(session.busy).toBe(false)
  expect(session.dirty).toBe(true)
})

it('restores outline adjustment only on the image page and locks it after images exist', async () => {
  await mount('/workspace')
  const studio = vi.mocked(useStudio).mock.results[0].value as ReturnType<typeof useStudio>
  const run = vi.spyOn(studio, 'run').mockResolvedValue(undefined)
  await nextTick()
  expect(button('重新生成大纲').props.disabled).toBe(false)
  button('重新生成大纲').props.onClick()
  expect(run).toHaveBeenCalledWith('outline')
  studio.store.images = [{ index: 0, url: '/synthetic.png', status: 'done' }]
  await nextTick()
  expect(button('重新生成大纲').props.disabled).toBe(true)
  expect(byId('outline-model').props.disabled).toBe(true)
  expect(nodes().some(node => node.props.id === 'outline-prompt')).toBe(false)
  expect(find(node => node.tagName === 'FIELDSET' && node.props.class === 'outline-options').props.disabled).toBe(true)
  studio.phase.value = 'images'
  await router.push('/workspace/copy')
  await nextTick()
  expect(nodes().some(node => node.tagName === 'DETAILS' && node.props.class?.includes('outline-adjustments'))).toBe(false)
  expect(button('取消图片生成').props.disabled).toBe(false)
  studio.cancelling.value = true
  await nextTick()
  expect(button('正在取消图片生成').props.disabled).toBe(true)
  studio.cancelling.value = false
  studio.phase.value = null
  run.mockRestore()
})

it('keeps the current outline when its replacement is not confirmed', async () => {
  await mount('/workspace')
  const studio = vi.mocked(useStudio).mock.results[0].value as ReturnType<typeof useStudio>
  vi.mocked(window.confirm).mockReturnValue(false)
  const original = JSON.stringify(studio.store.outline)
  await studio.run('outline')
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('替换当前大纲'))
  expect(JSON.stringify(studio.store.outline)).toBe(original)
  expect(studio.busy.value).toBe(false)
})

it.each(['/workspace', '/workspace/copy'])('saves before opening the shared preview from %s', async path => {
  useGeneratorStore().images = [{ index: 0, url: '/synthetic.png', status: 'done' }]
  await mount(path)
  const studio = vi.mocked(useStudio).mock.results[0].value as ReturnType<typeof useStudio>
  const save = vi.spyOn(studio, 'save').mockResolvedValue(false)
  expect(button('预览作品').props.disabled).toBe(false)
  await button('预览作品').props.onClick()
  expect(save).toHaveBeenCalledOnce()
  expect(router.currentRoute.value.path).toBe(path)
  save.mockResolvedValue(true)
  await button('预览作品').props.onClick()
  expect(save).toHaveBeenCalledTimes(2)
  expect(router.currentRoute.value.path).toBe('/result')
})

it('does not redirect away from a page selected while preview save is pending', async () => {
  useGeneratorStore().images = [{ index: 0, url: '/synthetic.png', status: 'done' }]
  await mount('/workspace/copy')
  const studio = vi.mocked(useStudio).mock.results[0].value as ReturnType<typeof useStudio>
  let finish!: (value: boolean) => void
  vi.spyOn(studio, 'save').mockReturnValue(new Promise(resolve => { finish = resolve }))
  const pending = button('预览作品').props.onClick()
  await router.push('/workspace')
  finish(true)
  await pending
  expect(router.currentRoute.value.path).toBe('/workspace')
})

it('opens a restored draft directly on the copy URL and copies the current publication text', async () => {
  const snapshot = JSON.stringify(useGeneratorStore().$state)
  pinia = createPinia()
  setActivePinia(pinia)
  localStorage.setItem('generator-state', snapshot)
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  await mount('/workspace/copy')
  expect(byId('copy-body').value).toBe('Body')
  await byLabel('复制全部文案').props.onClick()
  expect(writeText).toHaveBeenLastCalledWith('Title\n\nBody\n\n#tag')
  await byLabel('复制正文').props.onClick()
  expect(writeText).toHaveBeenLastCalledWith('Body')
  writeText.mockRejectedValue(new Error('Denied'))
  await byLabel('复制正文').props.onClick()
  await nextTick()
  expect(nodes().some(node => node.props.role === 'alert' && text(node).includes('复制失败'))).toBe(true)
})

it('returns from another module to the copy page through the actual main navigation', async () => {
  await mount('/workspace/copy', true)
  expect(useStudioSession().workspacePath).toBe('/workspace/copy')
  button('作品').props.onClick()
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/history'))
  button('创作').props.onClick()
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/workspace/copy'))
  expect(byId('copy-body').value).toBe('Body')
  expect(vi.mocked(useStudio)).toHaveBeenCalledOnce()
})

it.each(['/workspace', '/workspace/copy'])('preserves the draft on back and continues without regeneration from %s', async path => {
  const store = useGeneratorStore()
  store.recordId = 'record'
  store.taskId = 'task'
  store.images = [{ index: 0, url: '/synthetic.png', status: 'done' }]
  await mount(path)
  const snapshot = JSON.stringify({ outline: store.outline, images: store.images, content: store.content })
  const revision = useStudioSession().revision
  byLabel('返回创作设置').props.onClick()
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/'))
  expect(useStudioSession().revision).toBe(revision)
  expect(store.recordId).toBe('record')
  expect(store.taskId).toBe('task')
  expect(JSON.stringify({ outline: store.outline, images: store.images, content: store.content })).toBe(snapshot)
  expect(button('继续图文制作').props.disabled).toBe(false)
  await button('继续图文制作').props.onClick()
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe(path))
  expect(JSON.stringify({ outline: store.outline, images: store.images, content: store.content })).toBe(snapshot)
  expect(generateCandidate).not.toHaveBeenCalled()
  expect(generateContent).not.toHaveBeenCalled()
})

it.each(['/workspace', '/workspace/copy'])('returns from the actual preview to its originating workspace %s', async path => {
  useGeneratorStore().images = [{ index: 0, url: '/synthetic.png', status: 'done' }]
  await mount(path, true)
  const studio = vi.mocked(useStudio).mock.results[0].value as ReturnType<typeof useStudio>
  vi.spyOn(studio, 'save').mockResolvedValue(true)
  await button('预览作品').props.onClick()
  await nextTick()
  expect(router.currentRoute.value.path).toBe('/result')
  button('返回工作台').props.onClick()
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe(path))
  expect(byId(path === '/workspace/copy' ? 'copy-body' : 'page-content')).toBeDefined()
})
