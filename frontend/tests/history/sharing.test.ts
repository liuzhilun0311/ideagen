import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { computed, h, KeepAlive, reactive, ref, type Component } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import WorkSharingDialog from '../../src/components/history/WorkSharingDialog.vue'
import GalleryCard from '../../src/components/history/GalleryCard.vue'
import ImageGalleryModal from '../../src/components/history/ImageGalleryModal.vue'
import ImageDownloadDialog from '../../src/components/common/ImageDownloadDialog.vue'
import HistoryView from '../../src/views/HistoryView.vue'
import { getHistory, getHistoryList, getHistoryStats, getHistorySharing, setHistorySharing } from '../../src/api/history'
import { getMe, listUsers } from '../../src/api/auth'
import { useAuthStore } from '../../src/stores/auth'
import { useGeneratorStore } from '../../src/stores/generator'
import { useStudioSession } from '../../src/stores/studioSession'
import { usePostprocessing } from '../../src/composables/usePostprocessing'
import { root, renderer, button, nodes, text, settle, deferred } from './renderer'

vi.mock('../../src/api/history', () => ({
  getHistory: vi.fn(), getHistoryList: vi.fn(), getHistoryStats: vi.fn(),
  getHistorySharing: vi.fn(), setHistorySharing: vi.fn(), deleteHistory: vi.fn(), scanAllTasks: vi.fn(),
}))
vi.mock('../../src/api/auth', () => ({ getMe: vi.fn(), listUsers: vi.fn() }))
vi.mock('../../src/composables/usePostprocessing', () => ({ usePostprocessing: vi.fn() }))
vi.mock('../../src/components/common/ImageViewer.vue', async () => {
  const { h } = await import('vue')
  return { default: {
    props: ['visible', 'src', 'alt'],
    setup: (props: any) => () => props.visible ? h('img', { 'data-viewer': true, src: props.src, alt: props.alt }) : null,
  } }
})
const router = vi.hoisted(() => ({ push: vi.fn() }))
const route = reactive({ params: {} as { id?: string }, fullPath: '/history' })
vi.mock('vue-router', () => ({ useRouter: () => router, useRoute: () => route }))
const owner = { id: 'owner', username: 'Author', is_admin: true }
const reader = { id: 'reader', username: 'Reader', is_admin: false }
const card = {
  id: 'work', title: 'Shared work', owner, can_edit: false, can_share: false, is_shared: true,
  updated_at: '2026-09-10', created_at: '2026-09-10', page_count: 1, thumbnail: null, task_id: 'task', status: 'completed',
}
const detail = {
  ...card, outline: { raw: 'outline', pages: [{ index: 0, type: 'cover' as const, content: 'page' }] },
  images: { task_id: 'task', generated: ['0.png'] },
  content: { titles: ['Publishing title'], copywriting: 'Publishing body', tags: ['tag'] },
}
let dispose: (() => void) | undefined
let pinia: ReturnType<typeof createPinia>
function mount(component: Component, props: Record<string, unknown> = {}) {
  const app = renderer.createApp({ render: () => h(component, props) }).use(pinia)
  app.mount(root)
  dispose = () => app.unmount()
}
function processing() { return vi.mocked(usePostprocessing).mock.results.at(-1)!.value as ReturnType<typeof usePostprocessing> }
beforeEach(() => {
  vi.clearAllMocks()
  root.children = []
  root.text = ''
  route.fullPath = '/history'
  route.params = {}
  pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().$patch({ token: 'test', user: owner })
  vi.stubGlobal('Document', class {})
  vi.stubGlobal('ShadowRoot', class {})
  vi.stubGlobal('document', { activeElement: null })
  vi.stubGlobal('window', { setTimeout, clearTimeout, confirm: vi.fn(() => true), location: { href: 'http://localhost/history' } })
  vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
  vi.mocked(getMe).mockResolvedValue({ success: true, user: owner })
  vi.mocked(listUsers).mockResolvedValue({ success: true, users: [owner, reader] })
  vi.mocked(getHistorySharing).mockResolvedValue({ success: true, user_ids: ['reader'] })
  vi.mocked(setHistorySharing).mockResolvedValue({ success: true, user_ids: ['reader'] })
  vi.mocked(getHistory).mockResolvedValue({ success: true, record: detail })
  vi.mocked(getHistoryList).mockResolvedValue({ success: true, records: [card], total: 25, page: 1, page_size: 12, total_pages: 3 })
  vi.mocked(getHistoryStats).mockResolvedValue({ success: true, total: 25, by_status: { completed: 25 } })
  vi.mocked(usePostprocessing).mockImplementation(() => ({
    pages: computed(() => [{ index: 0, original_url: '/original.png', processed_url: '/processed.png', adopted: 'original' }]),
    error: ref(null), loading: ref(false), refresh: vi.fn().mockResolvedValue(null),
  } as unknown as ReturnType<typeof usePostprocessing>))
})
afterEach(() => { dispose?.(); dispose = undefined; vi.unstubAllGlobals() })

it('starts a clean persisted draft from the works page while preserving generation choices', async () => {
  const store = useGeneratorStore()
  const session = useStudioSession()
  store.$patch({
    recordId: 'deleted', taskId: 'old-task', topic: 'Old title', entrySource: 'history',
    outline: { raw: 'Old outline', pages: [{ index: 0, type: 'cover', content: 'Old page' }] },
    images: [{ index: 0, url: '/old.png', status: 'done' }],
    imageModelName: 'chosen-model', imagePromptName: 'chosen-prompt',
  })
  session.workspacePath = '/workspace/copy'
  mount(HistoryView)
  await settle()
  await button('新建图文')!.props.onClick()
  expect(window.confirm).toHaveBeenCalledOnce()
  expect(store.recordId).toBeNull()
  expect(store.taskId).toBeNull()
  expect(store.topic).toBe('')
  expect(store.outline.pages).toEqual([])
  expect(store.images).toEqual([])
  expect(store.entrySource).toBe('home')
  expect(store.imageModelName).toBe('chosen-model')
  expect(store.imagePromptName).toBe('chosen-prompt')
  expect(session.workspacePath).toBe('/workspace')
  expect(JSON.parse(localStorage.getItem('generator-state')!).recordId).toBeNull()
  expect(router.push).toHaveBeenCalledWith('/')
})

it('keeps the current draft and route when new-work confirmation is cancelled', async () => {
  const store = useGeneratorStore()
  store.topic = 'Unsaved idea'
  const before = JSON.stringify(store.$state)
  vi.mocked(window.confirm).mockReturnValue(false)
  mount(HistoryView)
  await settle()
  await button('新建图文')!.props.onClick()
  expect(JSON.stringify(store.$state)).toBe(before)
  expect(router.push).not.toHaveBeenCalled()
})

it('does not replace a draft while generation is running', async () => {
  const store = useGeneratorStore()
  store.topic = 'Running draft'
  useStudioSession().workspaceBusy = true
  mount(HistoryView)
  await settle()
  expect(button('新建图文')!.props.disabled).toBe(true)
  await button('新建图文')!.props.onClick()
  expect(store.topic).toBe('Running draft')
  expect(router.push).not.toHaveBeenCalled()
})

it('restores recipients, excludes owner, keeps selection on failure and blocks repeated saves', async () => {
  const saved = vi.fn()
  mount(WorkSharingDialog, { record: card, onSaved: saved })
  await settle()
  const checkboxes = nodes().filter(node => node.tag === 'input' && node.props.type === 'checkbox')
  expect(checkboxes).toHaveLength(1)
  expect(checkboxes[0]!.checked).toBe(true)
  checkboxes[0]!.props['onUpdate:modelValue']([])
  await settle()
  const request = deferred<Awaited<ReturnType<typeof setHistorySharing>>>()
  vi.mocked(setHistorySharing).mockReturnValue(request.promise)
  const save = button('保存')!.props.onClick
  const pending = save()
  await save()
  expect(setHistorySharing).toHaveBeenCalledTimes(1)
  expect(setHistorySharing).toHaveBeenCalledWith('work', [])
  request.resolve({ success: false, user_ids: [], error_message: 'Save failed' })
  await pending
  await settle()
  expect(saved).not.toHaveBeenCalled()
  expect(text()).toContain('Save failed')
  expect(checkboxes[0]!.checked).toBe(false)
  vi.mocked(setHistorySharing).mockResolvedValue({ success: true, user_ids: [] })
  await button('保存')!.props.onClick()
  expect(saved).toHaveBeenCalledWith('work', [])
})

it('searches usernames without dropping hidden selections', async () => {
  mount(WorkSharingDialog, { record: card })
  await settle()
  nodes().find(node => node.props.type === 'search')!.props['onUpdate:modelValue']('missing')
  await settle()
  expect(text()).toContain('暂无匹配用户')
  await button('保存')!.props.onClick()
  expect(setHistorySharing).toHaveBeenCalledWith('work', ['reader'])
})

it('discards a late save after account changes', async () => {
  const saved = vi.fn()
  const close = vi.fn()
  mount(WorkSharingDialog, { record: card, onSaved: saved, onClose: close })
  await settle()
  const request = deferred<Awaited<ReturnType<typeof setHistorySharing>>>()
  vi.mocked(setHistorySharing).mockReturnValue(request.promise)
  const pending = button('保存')!.props.onClick()
  useAuthStore().user = reader
  request.resolve({ success: true, user_ids: ['reader'] })
  await pending
  expect(close).toHaveBeenCalled()
  expect(saved).not.toHaveBeenCalled()
})

it('does not restore recipients from a previous record selection', async () => {
  const request = deferred<Awaited<ReturnType<typeof getHistorySharing>>>()
  vi.mocked(getHistorySharing).mockReturnValueOnce(request.promise)
  const props = reactive({ record: card })
  mount(WorkSharingDialog, props)
  await settle()
  vi.mocked(getHistorySharing).mockResolvedValue({ success: true, user_ids: [] })
  props.record = { ...card, id: 'second' }
  await settle()
  request.resolve({ success: true, user_ids: ['reader'] })
  await settle()
  await button('保存')!.props.onClick()
  expect(setHistorySharing).toHaveBeenCalledWith('second', [])
})

it('shows only preview and download on shared cards even with conflicting capabilities', async () => {
  mount(GalleryCard, { record: { ...card, can_edit: true, can_share: true }, readonly: true })
  await settle()
  expect(button('预览')).toBeDefined()
  expect(button('下载')).toBeDefined()
  expect(button('编辑')).toBeUndefined()
  expect(button('删除作品')).toBeUndefined()
  expect(button('配置用户')).toBeUndefined()
  expect(text()).toContain('Author')
})

it('exposes owner sharing and confirmed count', async () => {
  mount(GalleryCard, { record: { ...card, is_shared: true, can_edit: true, can_share: true, shared_count: 2 } })
  await settle()
  expect(button('配置用户')).toBeDefined()
  expect(button('编辑')).toBeDefined()
  expect(button('删除作品')).toBeDefined()
  expect(text()).toContain('已共享 2 人')
})

it('previews processed images and copies publishing text without touching the draft', async () => {
  const store = useGeneratorStore()
  store.topic = 'Unsaved draft'
  const snapshot = JSON.stringify(store.$state)
  mount(ImageGalleryModal, { visible: true, record: detail, readonly: true })
  await settle()
  expect(nodes().find(node => node.tag === 'img')!.props.src).toContain('/processed.png')
  expect(button('编辑')).toBeUndefined()
  await button('查看文案')!.props.onClick()
  await settle()
  expect(text()).toContain('Publishing body')
  await button('复制')!.props.onClick()
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('Publishing body'))
  expect(JSON.stringify(store.$state)).toBe(snapshot)
})

it.each([401, 403, 404])('hides cached text and blocks captured copy handlers immediately on processing %s', async status => {
  const unavailable = vi.fn()
  mount(ImageGalleryModal, { visible: true, record: detail, readonly: true, onUnavailable: unavailable })
  await settle()
  button('查看文案')!.props.onClick()
  await settle()
  const copy = button('复制')!.props.onClick
  processing().error.value = { detail: 'Access revoked', status } as any
  await copy()
  await settle()
  expect(unavailable).toHaveBeenCalled()
  expect(navigator.clipboard.writeText).not.toHaveBeenCalled()
  expect(text()).not.toContain('Publishing body')
  expect(nodes().some(node => node.tag === 'img')).toBe(false)
})

it.each([500, 0])('retains preview and publishing text after transient processing error %s and offers retry', async status => {
  const unavailable = vi.fn()
  mount(ImageGalleryModal, { visible: true, record: detail, readonly: true, onUnavailable: unavailable })
  await settle()
  processing().error.value = { detail: 'Temporary failure', status } as any
  await settle()
  expect(unavailable).not.toHaveBeenCalled()
  expect(text()).toContain('Temporary failure')
  expect(nodes().find(node => node.tag === 'img')!.props.src).toContain('/processed.png')
  button('查看文案')!.props.onClick()
  await settle()
  expect(text()).toContain('Publishing body')
  await button('复制')!.props.onClick()
  expect(navigator.clipboard.writeText).toHaveBeenCalled()
  vi.mocked(processing().refresh).mockImplementation(async () => { processing().error.value = null; return null })
  await button('重试读取图片')!.props.onClick()
  await settle()
  expect(processing().refresh).toHaveBeenCalledTimes(1)
  expect(text()).not.toContain('Temporary failure')
  expect(text()).toContain('Publishing body')
})

it('does not infer revocation from an image load event without an HTTP status', async () => {
  const unavailable = vi.fn()
  mount(ImageGalleryModal, { visible: true, record: detail, readonly: true, onUnavailable: unavailable })
  await settle()
  nodes().find(node => node.tag === 'img')!.props.onError()
  await settle()
  expect(unavailable).not.toHaveBeenCalled()
  expect(button('重试读取图片')).toBeDefined()
  expect(button('查看文案')).toBeDefined()
})

it('uses numeric filenames for sparse page versions, viewer, clipboard and download indices', async () => {
  vi.mocked(usePostprocessing).mockImplementation(() => ({
    pages: computed(() => [0, 1, 2].map(index => ({
      index, original_url: `/original-${index}.png`, processed_url: `/processed-${index}.png`,
    }))),
    error: ref(null), loading: ref(false), refresh: vi.fn().mockResolvedValue(null),
  } as unknown as ReturnType<typeof usePostprocessing>))
  const download = vi.fn()
  mount(ImageGalleryModal, {
    visible: true, record: { ...detail, images: { task_id: 'task', generated: ['0.png', '2.png'] } },
    readonly: true, onDownload: download,
  })
  await settle()
  expect(nodes().filter(node => node.tag === 'img').map(node => node.props.src)).toEqual(['/processed-0.png', '/processed-2.png'])
  expect(nodes().filter(node => node.tag === 'img').map(node => node.props.alt)).toEqual(['第 1 页', '第 3 页'])
  nodes().filter(node => node.props.class === 'modal-img-preview')[1]!.props.onClick()
  await settle()
  expect(nodes().find(node => node.props['data-viewer'])!.props.src).toBe('/processed-2.png')
  expect(nodes().find(node => node.props['data-viewer'])!.props.alt).toBe('第 3 页')
  nodes().filter(node => node.props.class === 'img-link' && text(node).trim() === '下载')[1]!.props.onClick({ stopPropagation() {} })
  expect(download).toHaveBeenCalledWith('2.png', 2)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Blob(['image'], { type: 'image/png' }))))
  vi.stubGlobal('ClipboardItem', class { constructor(public items: unknown) {} })
  vi.stubGlobal('navigator', { clipboard: { write: vi.fn().mockResolvedValue(undefined) } })
  await nodes().filter(node => node.props.class === 'img-link' && text(node).trim() === '复制')[1]!.props.onClick({ stopPropagation() {} })
  expect(fetch).toHaveBeenCalledWith('/processed-2.png', expect.anything())
})

it('falls back to originals when there is no processed version', async () => {
  vi.mocked(usePostprocessing).mockImplementation(() => ({
    pages: computed(() => [{ index: 0, original_url: '/original.png', processed_url: null }]),
    error: ref(null), loading: ref(false),
  } as unknown as ReturnType<typeof usePostprocessing>))
  mount(ImageGalleryModal, { visible: true, record: detail, readonly: true })
  await settle()
  expect(nodes().find(node => node.tag === 'img')!.props.src).toContain('/original.png')
})

it('hides processing navigation in read-only download while retaining original and both choices', async () => {
  mount(ImageDownloadDialog, { visible: true, pages: [{ index: 0, original_url: '/original.png', processed_url: null }], canProcess: false })
  await settle()
  expect(button('返回图片制作')).toBeUndefined()
  const versionSelect = nodes().find(node => node.tag === 'select' && node.props.id === 'download-version')!
  expect(nodes(versionSelect).filter(node => node.tag === 'option').map(node => node.props.value))
    .toEqual(['processed', 'original', 'both'])
})

it('combines shared source with status, search and pagination and preserves them after preview closes', async () => {
  mount(HistoryView)
  await settle()
  await button('共享给我')!.props.onClick()
  await settle()
  nodes().find(node => node.props.class === 'tab-item' && text(node).trim() === '已完成')!.props.onClick()
  const input = nodes().find(node => node.tag === 'input' && node.props.placeholder === '搜索标题...')!
  input.props['onUpdate:modelValue']('work')
  await settle()
  input.props.onKeyup({ key: 'Enter' })
  await settle()
  await button('下一页')!.props.onClick()
  await settle()
  expect(getHistoryList).toHaveBeenLastCalledWith(2, 12, 'completed', 'shared', 'work')
  expect(getHistoryStats).toHaveBeenLastCalledWith('shared')
  await button('预览')!.props.onClick({ stopPropagation() {} })
  await settle()
  const calls = vi.mocked(getHistoryList).mock.calls.length
  nodes().find(node => node.props.class === 'close-icon')!.props.onClick()
  await settle()
  expect(getHistoryList).toHaveBeenCalledTimes(calls)
  expect(nodes().find(node => node.tag === 'input' && node.props.placeholder === '搜索标题...')!.value).toBe('work')
  expect(nodes().find(node => node.props['aria-pressed'] === true && text(node) === '共享给我')).toBeDefined()
})

it('rejects a late preview on navigation without loading generator state', async () => {
  mount(HistoryView)
  await settle()
  const request = deferred<Awaited<ReturnType<typeof getHistory>>>()
  vi.mocked(getHistory).mockReturnValue(request.promise)
  const pending = button('预览')!.props.onClick({ stopPropagation() {} })
  route.fullPath = '/workspace'
  request.resolve({ success: true, record: detail })
  await pending
  await settle()
  expect(button('查看文案')).toBeUndefined()
  expect(useGeneratorStore().recordId).not.toBe('work')
})

it('does not restore a pending download after switching source', async () => {
  mount(HistoryView)
  await settle()
  const request = deferred<Awaited<ReturnType<typeof getHistory>>>()
  vi.mocked(getHistory).mockReturnValue(request.promise)
  const pending = button('下载')!.props.onClick({ stopPropagation() {} })
  await settle()
  expect(button('关闭下载')).toBeDefined()
  button('共享给我')!.props.onClick()
  request.resolve({ success: true, record: detail })
  await pending
  await settle()
  expect(button('关闭下载')).toBeUndefined()
})

it('clears records on account change and ignores the old list response', async () => {
  const request = deferred<Awaited<ReturnType<typeof getHistoryList>>>()
  vi.mocked(getHistoryList).mockReturnValueOnce(request.promise)
  mount(HistoryView)
  await settle()
  vi.mocked(getMe).mockResolvedValue({ success: true, user: reader })
  vi.mocked(getHistoryList).mockResolvedValue({ success: true, records: [], total: 0, page: 1, page_size: 12, total_pages: 0 })
  useAuthStore().$patch({ token: 'reader-token', user: reader, sessionRevision: 1 })
  request.resolve({ success: true, records: [card], total: 1, page: 1, page_size: 12, total_pages: 1 })
  await settle()
  expect(text()).not.toContain('Shared work')
})

it('refreshes authorization and list after KeepAlive reactivation while preserving source', async () => {
  const visible = ref(true)
  const app = renderer.createApp({
    render: () => h(KeepAlive, null, { default: () => visible.value ? h(HistoryView) : h('div') }),
  }).use(pinia)
  app.mount(root)
  dispose = () => app.unmount()
  await settle()
  button('共享给我')!.props.onClick()
  await settle()
  visible.value = false
  await settle()
  const count = vi.mocked(getMe).mock.calls.length
  visible.value = true
  await settle()
  expect(getMe).toHaveBeenCalledTimes(count + 1)
  expect(getHistoryList).toHaveBeenLastCalledWith(1, 12, undefined, 'shared', undefined)
})

it('does not fetch or display cached records when refreshed authorization fails', async () => {
  vi.mocked(getMe).mockResolvedValue({ success: false })
  mount(HistoryView)
  await settle()
  expect(getHistoryList).not.toHaveBeenCalled()
  expect(text()).not.toContain('Shared work')
  expect(text()).toContain('登录状态已失效')
})
