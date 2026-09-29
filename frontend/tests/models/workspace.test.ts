import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRenderer, h, KeepAlive, nextTick, reactive, ref, computed, type Ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import ProviderTable from '../../src/components/settings/ProviderTable.vue'
import SettingsView from '../../src/views/SettingsView.vue'
import { useProviderForm } from '../../src/composables/useProviderForm'
import { useLibraryOrder } from '../../src/composables/useLibraryOrder'
import { getConfig } from '../../src/api'
import { useAuthStore } from '../../src/stores/auth'

const hooks = vi.hoisted(() => ({ leave: () => {} }))
vi.mock('vue-router', () => ({ onBeforeRouteLeave: (callback: () => void) => { hooks.leave = callback } }))
vi.mock('../../src/api', () => ({
  getConfig: vi.fn(), saveProvider: vi.fn(), updateConfig: vi.fn(),
  testConnection: vi.fn(), setProviderUsers: vi.fn(),
}))
vi.mock('../../src/api/auth', () => ({ listUsers: vi.fn() }))
vi.mock('../../src/composables/useLibraryOrder', () => ({ useLibraryOrder: vi.fn() }))
vi.mock('../../src/composables/useProviderForm', async original => {
  const actual = await original<typeof import('../../src/composables/useProviderForm')>()
  return { ...actual, useProviderForm: vi.fn(actual.useProviderForm) }
})
vi.mock('../../src/components/settings/ProviderModal.vue', () => ({ default: { render: () => null } }))
vi.mock('../../src/components/settings/ImageProviderModal.vue', () => ({ default: { render: () => null } }))
vi.mock('../../src/components/common/ErrorCard.vue', () => ({ default: { render: () => null } }))

class HostNode {
  children: HostNode[] = []
  parent: HostNode | null = null
  props: Record<string, any> = {}
  text = ''
  constructor(public tag: string) {}
}
const renderer = createRenderer<HostNode, HostNode>({
  createElement: tag => new HostNode(tag),
  createText: text => Object.assign(new HostNode('#text'), { text }),
  createComment: () => new HostNode('#comment'),
  setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.text = text; node.children = [] },
  parentNode: node => node.parent,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] ?? null,
  patchProp: (node, key, _old, value) => { node.props[key] = value },
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
  insertStaticContent: (content, parent, anchor) => {
    const node = Object.assign(new HostNode('#static'), { text: content, parent })
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
    return [node, node]
  },
})
let root: HostNode
let dispose: () => void
const provider = { type: 'openai_compatible', model: 'synthetic', api_key_masked: '********' }
const config = () => ({
  text_generation: { active_provider: 'text', providers: { text: { ...provider } } },
  image_generation: { active_provider: 'image', providers: { image: { ...provider, type: 'image_api' } } },
})
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}
async function settle() {
  for (let index = 0; index < 12; index++) await nextTick()
}
function nodes(node = root): HostNode[] { return [node, ...node.children.flatMap(child => nodes(child))] }
function row(id: string) { return nodes().find(node => node.props['data-reorder-id'] === id)! }
async function selectCategory(kind: 'text' | 'image') {
  const nav = nodes().find(node => node.props['aria-label'] === '模型类型')!
  const tabs = nav.children.filter(node => node.tag === 'button')
  tabs[kind === 'text' ? 0 : 1]!.props.onClick()
  await nextTick()
  expect(row(kind)).toBeDefined()
}
function button(label: string, node = root) {
  return nodes(node).find(child => child.tag === 'button' && child.props['aria-label'] === label)!
}
function form() { return vi.mocked(useProviderForm).mock.results[0]!.value as ReturnType<typeof useProviderForm> }
function library(kind: 'text' | 'image') {
  return vi.mocked(useLibraryOrder).mock.results[kind === 'text' ? 0 : 1]!.value as ReturnType<typeof useLibraryOrder>
}
async function mountSettings() {
  root = new HostNode('root')
  const app = renderer.createApp(SettingsView)
  app.use(createPinia())
  app.mount(root)
  dispose = () => app.unmount()
  await vi.waitFor(() => expect(row('text')).toBeDefined())
}
async function mountCachedSettings() {
  const visible = ref(true)
  const other = { render: () => h('div', 'Other page') }
  root = new HostNode('root')
  const app = renderer.createApp({
    render: () => h(KeepAlive, null, { default: () => visible.value ? h(SettingsView) : h(other) }),
  })
  app.use(createPinia())
  app.mount(root)
  dispose = () => app.unmount()
  await vi.waitFor(() => expect(row('text')).toBeDefined())
  return async (show: boolean) => {
    visible.value = show
    await settle()
  }
}
beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  vi.mocked(getConfig).mockResolvedValue({ success: true, config: config() })
  vi.mocked(useLibraryOrder).mockImplementation((_resource, _kind, ids: Ref<string[]>) => ({
    order: computed(() => ids.value), busy: ref(false), error: ref(''),
    refresh: vi.fn().mockResolvedValue(true),
    move: vi.fn().mockResolvedValue(true),
    copy: vi.fn().mockResolvedValue(null),
    invalidate: vi.fn(),
  }))
})
afterEach(() => { dispose?.(); vi.unstubAllGlobals() })

describe('model table ordering', () => {
  it('merges saved IDs, skips stale/duplicate IDs and emits adjacent target moves', async () => {
    const move = vi.fn(), copy = vi.fn()
    const props = reactive({
      providers: { first: provider, second: provider, third: provider },
      activeProvider: 'first', order: ['second', 'missing', 'second', 'first'], busy: false,
      onMove: move, onCopy: copy,
    })
    root = new HostNode('root')
    const app = renderer.createApp({ render: () => h(ProviderTable, props) })
    app.mount(root)
    dispose = () => app.unmount()
    expect(nodes().filter(node => node.props['data-reorder-id']).map(node => node.props['data-reorder-id']))
      .toEqual(['second', 'first', 'third'])
    expect(button('上移', row('second')).props.disabled).toBe(true)
    expect(button('下移', row('third')).props.disabled).toBe(true)
    button('下移', row('second')).props.onClick()
    expect(move).toHaveBeenCalledWith('second', 'first')
    button('复制模型', row('first')).props.onClick()
    expect(copy).toHaveBeenCalledWith('first')
    const list = {}
    const target = {
      dataset: { reorderId: 'third' },
      classList: { add: vi.fn(), remove: vi.fn() },
      closest: () => list,
    }
    vi.stubGlobal('document', { elementFromPoint: () => ({ closest: () => target }) })
    vi.stubGlobal('window', { innerHeight: 800, scrollBy: vi.fn() })
    const handle = button('拖动排序', row('second'))
    handle.props.onPointerdown({
      button: 0, pointerId: 1, preventDefault: vi.fn(),
      currentTarget: { closest: () => list, setPointerCapture: vi.fn() },
    })
    handle.props.onPointermove({ pointerId: 1, clientX: 100, clientY: 200 })
    handle.props.onPointerup({ pointerId: 1 })
    expect(move).toHaveBeenLastCalledWith('second', 'third')
    expect(target.classList.add).toHaveBeenCalledWith('reorder-target')
    props.busy = true
    await nextTick()
    expect(nodes().filter(node => node.tag === 'button').every(node => node.props.disabled)).toBe(true)
    button('下移', row('second')).props.onClick()
    expect(move).toHaveBeenCalledTimes(2)
    expect(nodes().some(node => Object.prototype.hasOwnProperty.call(node.props, 'data-reorder-list'))).toBe(true)
  })
})

describe('model settings copy integration', () => {
  it.each(['text', 'image'] as const)('copies %s by ID, reloads then edits the server-created disabled model', async kind => {
    await mountSettings()
    await selectCategory(kind)
    const pending = deferred<{ id: string; name: string } | null>()
    vi.mocked(library(kind).copy).mockReturnValue(pending.promise)
    const click = button('复制模型', row(kind)).props.onClick
    const operation = click()
    await nextTick()
    expect(button('复制模型', row(kind)).props.disabled).toBe(true)
    await click()
    expect(library(kind).copy).toHaveBeenCalledTimes(1)
    expect(library(kind).copy).toHaveBeenCalledWith(kind)
    expect(getConfig).toHaveBeenCalledTimes(1)
    const copied = { ...provider, enabled: false, allowed_users: [] }
    const next = config()
    Object.assign(next[`${kind}_generation`].providers, { 'server-id': copied })
    vi.mocked(getConfig).mockResolvedValue({ success: true, config: next })
    pending.resolve({ id: 'server-id', name: 'server-id' })
    await operation
    await settle()
    expect(getConfig).toHaveBeenCalledTimes(2)
    expect((kind === 'text' ? form().editingTextProvider : form().editingImageProvider).value).toBe('server-id')
    const fields = (kind === 'text' ? form().textForm : form().imageForm).value
    expect(fields.api_key).toBe('')
    ;(kind === 'text' ? form().closeTextModal : form().closeImageModal)()
    expect((kind === 'text' ? form().textConfig : form().imageConfig).value.providers['server-id']).toEqual(
      expect.objectContaining({ enabled: false, allowed_users: [] }),
    )
  })

  it('reports successful creation followed by failed refresh without retrying creation', async () => {
    await mountSettings()
    vi.mocked(library('text').copy).mockResolvedValue({ id: 'new', name: 'new' })
    vi.mocked(getConfig).mockRejectedValue(new Error('offline'))
    await button('复制模型', row('text')).props.onClick()
    await settle()
    expect(JSON.stringify(form().feedback.value)).toContain('副本已创建')
    expect(JSON.stringify(form().feedback.value)).toContain('不要重复复制')
    expect(form().showTextModal.value).toBe(false)
    expect(library('text').copy).toHaveBeenCalledTimes(1)
  })

  it('does not reload or open an editor when creation fails', async () => {
    await mountSettings()
    library('text').error.value = 'Copy denied'
    await button('复制模型', row('text')).props.onClick()
    await settle()
    expect(getConfig).toHaveBeenCalledTimes(1)
    expect(form().showTextModal.value).toBe(false)
  })

  it('reports a missing created ID as refresh failure rather than opening the source model', async () => {
    await mountSettings()
    await selectCategory('image')
    vi.mocked(library('image').copy).mockResolvedValue({ id: 'missing', name: 'missing' })
    await button('复制模型', row('image')).props.onClick()
    await settle()
    expect(JSON.stringify(form().feedback.value)).toContain('副本已创建')
    expect(form().showImageModal.value).toBe(false)
    expect(form().editingImageProvider.value).toBeNull()
  })

  it('keeps text and image copy responses bound to their respective categories', async () => {
    await mountSettings()
    const text = deferred<{ id: string; name: string } | null>()
    const image = deferred<{ id: string; name: string } | null>()
    vi.mocked(library('text').copy).mockReturnValue(text.promise)
    vi.mocked(library('image').copy).mockReturnValue(image.promise)
    button('复制模型', row('text')).props.onClick()
    await selectCategory('image')
    button('复制模型', row('image')).props.onClick()
    const next = config()
    Object.assign(next.text_generation.providers, { 'text-copy': provider })
    Object.assign(next.image_generation.providers, { 'image-copy': provider })
    vi.mocked(getConfig).mockResolvedValue({ success: true, config: next })
    image.resolve({ id: 'image-copy', name: 'image-copy' })
    await settle()
    expect(form().editingImageProvider.value).toBe('image-copy')
    expect(form().showTextModal.value).toBe(false)
    text.resolve({ id: 'text-copy', name: 'text-copy' })
    await settle()
    expect(form().editingTextProvider.value).toBe('text-copy')
    expect(form().editingImageProvider.value).toBe('image-copy')
  })

  it.each(['navigation', 'account'] as const)('ignores a late copy after %s changes', async change => {
    await mountSettings()
    const pending = deferred<{ id: string; name: string } | null>()
    vi.mocked(library('text').copy).mockReturnValue(pending.promise)
    const operation = button('复制模型', row('text')).props.onClick()
    if (change === 'navigation') hooks.leave()
    else useAuthStore().token = 'another-session'
    pending.resolve({ id: 'new', name: 'new' })
    await operation
    await settle()
    expect(getConfig).toHaveBeenCalledTimes(1)
    expect(form().showTextModal.value).toBe(false)
    expect(library('text').invalidate).toHaveBeenCalled()
  })

  it('discards a late config refresh after an account change', async () => {
    await mountSettings()
    vi.mocked(library('text').copy).mockResolvedValue({ id: 'new', name: 'new' })
    const pending = deferred<Awaited<ReturnType<typeof getConfig>>>()
    vi.mocked(getConfig).mockReturnValue(pending.promise)
    const operation = button('复制模型', row('text')).props.onClick()
    await vi.waitFor(() => expect(getConfig).toHaveBeenCalledTimes(2))
    useAuthStore().sessionRevision++
    pending.resolve({ success: true, config: config() })
    await operation
    await settle()
    expect(form().textConfig.value.providers).toEqual({})
    expect(form().imageConfig.value.providers).toEqual({})
    expect(form().showTextModal.value).toBe(false)
  })

  it('routes moves to the source category and blocks moves while copying', async () => {
    await mountSettings()
    form().textConfig.value.providers.other = { ...provider }
    await nextTick()
    button('下移', row('text')).props.onClick()
    expect(library('text').move).toHaveBeenCalledWith('text', 'other')
    expect(library('image').move).not.toHaveBeenCalled()
    const pending = deferred<{ id: string; name: string } | null>()
    vi.mocked(library('text').copy).mockReturnValue(pending.promise)
    const operation = button('复制模型', row('text')).props.onClick()
    await nextTick()
    button('下移', row('text')).props.onClick()
    expect(library('text').move).toHaveBeenCalledTimes(1)
    pending.resolve(null)
    await operation
    await settle()
  })
})

describe('cached model settings lifetimes', () => {
  it('reactivates the existing settings instance and enables copy and reorder after leaving', async () => {
    const show = await mountCachedSettings()
    const originalForm = form()
    expect(getConfig).toHaveBeenCalledTimes(1)
    await show(false)
    expect(row('text')).toBeUndefined()
    expect(library('text').invalidate).toHaveBeenCalled()
    const next = config()
    Object.assign(next.text_generation.providers, { other: provider })
    vi.mocked(getConfig).mockResolvedValue({ success: true, config: next })
    await show(true)
    expect(useProviderForm).toHaveBeenCalledTimes(1)
    expect(form()).toBe(originalForm)
    expect(getConfig).toHaveBeenCalledTimes(2)
    expect(button('复制模型', row('text')).props.disabled).toBe(false)
    button('下移', row('text')).props.onClick()
    expect(library('text').move).toHaveBeenCalledWith('text', 'other')
    button('复制模型', row('text')).props.onClick()
    await settle()
    expect(library('text').copy).toHaveBeenCalledWith('text')
    expect(button('复制模型', row('text')).props.disabled).toBe(false)
  })

  it('ignores an old copy after reentry without releasing the new copy lock or opening the old editor', async () => {
    const show = await mountCachedSettings()
    const oldCopy = deferred<{ id: string; name: string } | null>()
    const newCopy = deferred<{ id: string; name: string } | null>()
    vi.mocked(library('text').copy).mockReturnValueOnce(oldCopy.promise).mockReturnValueOnce(newCopy.promise)
    button('复制模型', row('text')).props.onClick()
    await settle()
    expect(button('复制模型', row('text')).props.disabled).toBe(true)
    await show(false)
    await show(true)
    expect(button('复制模型', row('text')).props.disabled).toBe(false)
    button('复制模型', row('text')).props.onClick()
    await settle()
    oldCopy.resolve({ id: 'old-copy', name: 'old-copy' })
    await settle()
    expect(getConfig).toHaveBeenCalledTimes(2)
    expect(form().showTextModal.value).toBe(false)
    expect(button('复制模型', row('text')).props.disabled).toBe(true)
    const next = config()
    Object.assign(next.text_generation.providers, { 'new-copy': provider })
    vi.mocked(getConfig).mockResolvedValue({ success: true, config: next })
    newCopy.resolve({ id: 'new-copy', name: 'new-copy' })
    await settle()
    expect(getConfig).toHaveBeenCalledTimes(3)
    expect(form().editingTextProvider.value).toBe('new-copy')
    expect(form().showTextModal.value).toBe(true)
    expect(form().feedback.value).toBeNull()
  })

  it.each(['old-first', 'new-first'] as const)('protects reentry config and loading state when reloads finish %s', async resolution => {
    const show = await mountCachedSettings()
    const oldLoad = deferred<Awaited<ReturnType<typeof getConfig>>>()
    const newLoad = deferred<Awaited<ReturnType<typeof getConfig>>>()
    vi.mocked(getConfig).mockReturnValueOnce(oldLoad.promise).mockReturnValueOnce(newLoad.promise)
    vi.mocked(library('text').copy).mockResolvedValue({ id: 'old-copy', name: 'old-copy' })
    button('复制模型', row('text')).props.onClick()
    await settle()
    expect(getConfig).toHaveBeenCalledTimes(2)
    await show(false)
    await show(true)
    expect(getConfig).toHaveBeenCalledTimes(3)
    expect(form().loading.value).toBe(true)
    const stale = config()
    stale.text_generation.providers.text.model = 'stale-model'
    Object.assign(stale.text_generation.providers, { 'old-copy': provider })
    const fresh = config()
    fresh.text_generation.providers.text.model = 'fresh-model'
    fresh.image_generation.providers.image.model = 'fresh-image'
    if (resolution === 'old-first') {
      oldLoad.resolve({ success: true, config: stale })
      await settle()
      expect(form().loading.value).toBe(true)
      expect(form().textConfig.value.providers).toEqual({})
      expect(form().showTextModal.value).toBe(false)
      newLoad.resolve({ success: true, config: fresh })
    } else {
      newLoad.resolve({ success: true, config: fresh })
      await settle()
      expect(form().loading.value).toBe(false)
      expect(form().textConfig.value.providers.text.model).toBe('fresh-model')
      oldLoad.resolve({ success: true, config: stale })
    }
    await settle()
    expect(form().textConfig.value.providers.text.model).toBe('fresh-model')
    expect(form().imageConfig.value.providers.image.model).toBe('fresh-image')
    expect(form().textConfig.value.providers).not.toHaveProperty('old-copy')
    expect(form().showTextModal.value).toBe(false)
    expect(form().feedback.value).toBeNull()
    expect(form().loading.value).toBe(false)
    expect(button('复制模型', row('text')).props.disabled).toBe(false)
  })
})
