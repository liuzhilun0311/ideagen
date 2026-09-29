import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { useGeneratorStore, setupAutoSave } from '../../src/stores/generator'
import { useStudioSession } from '../../src/stores/studioSession'
import { useAuthStore } from '../../src/stores/auth'
import { useReferenceDraftPersistence } from '../../src/composables/useReferenceDraftPersistence'
import type { ReferenceDraft, ReferenceDraftStorage } from '../../src/features/referenceDraftStorage'
import { deferred } from '../history/renderer'

let stops: (() => void)[] = []
const image = () => new File(['reference'], 'photo.png', { type: 'image/png', lastModified: 123 })
const snapshot = (key: string): ReferenceDraft => ({ key, files: [{ name: 'photo.png', type: 'image/png', lastModified: 123, blob: image() }] })
beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })
afterEach(() => { stops.forEach(stop => stop()); stops = []; vi.restoreAllMocks() })

function mount(storage: ReferenceDraftStorage) {
  const persistence = useReferenceDraftPersistence(storage)
  stops.push(persistence.stop)
  return persistence
}

it('restores exact bytes and metadata from the matching image snapshot', async () => {
  const store = useGeneratorStore()
  store.referenceImageKey = 'saved'
  const write = vi.fn()
  const persistence = mount({ read: async () => snapshot('saved'), write })
  expect(useStudioSession().referenceLoading).toBe(true)
  await persistence.ready
  expect(await store.userImages[0]!.text()).toBe('reference')
  expect(store.userImages[0]!.name).toBe('photo.png')
  expect(store.userImages[0]!.lastModified).toBe(123)
  expect(write).not.toHaveBeenCalled()
  expect(useStudioSession().referenceLoading).toBe(false)
})

it('writes images outside localStorage and serializes removal after an in-flight save', async () => {
  const store = useGeneratorStore()
  const pending = deferred<void>()
  const write = vi.fn().mockReturnValueOnce(pending.promise).mockResolvedValue(undefined)
  mount({ read: async () => undefined, write })
  store.userImages = [image()]
  const key = store.referenceImageKey
  await nextTick()
  expect(key).toBeTruthy()
  expect(localStorage.getItem('generator-state')).not.toContain('reference"')
  store.userImages = []
  expect(store.referenceImageKey).toBe('')
  pending.resolve()
  await vi.waitFor(() => expect(useStudioSession().referenceSaving).toBe(false))
  expect(write.mock.calls.at(-1)![1].files).toEqual([])
})

it.each(['mismatched', 'missing', 'failed'])('reports %s restoration without overwriting the manifest', async kind => {
  const store = useGeneratorStore()
  store.referenceImageKey = 'saved'
  const read = vi.fn(async () => {
    if (kind === 'failed') throw new Error('read failed')
    return kind === 'missing' ? undefined : snapshot('another')
  })
  const write = vi.fn()
  const persistence = mount({ read, write })
  await persistence.ready
  expect(store.userImages).toEqual([])
  expect(store.referenceImageKey).toBe('saved')
  expect(useStudioSession().referenceStorageError).toContain('恢复失败')
  expect(write).not.toHaveBeenCalled()
  read.mockResolvedValue(snapshot('saved'))
  await persistence.retry()
  expect(store.userImages).toHaveLength(1)
  expect(useStudioSession().referenceStorageError).toBe('')
})

it('keeps newly uploaded references when an old restore finishes late', async () => {
  const store = useGeneratorStore()
  store.referenceImageKey = 'saved'
  const pending = deferred<ReferenceDraft>()
  const persistence = mount({ read: () => pending.promise, write: async () => {} })
  const replacement = new File(['new'], 'new.png', { type: 'image/png' })
  store.userImages = [replacement]
  pending.resolve(snapshot('saved'))
  await persistence.ready
  expect(store.userImages[0]!.name).toBe('new.png')
})

it('does not restore references after an account change', async () => {
  const auth = useAuthStore()
  auth.user = { id: 'first', username: 'First', is_admin: false }
  const store = useGeneratorStore()
  store.referenceImageKey = 'saved'
  const pending = deferred<ReferenceDraft>()
  const persistence = mount({ read: () => pending.promise, write: async () => {} })
  auth.user = { id: 'second', username: 'Second', is_admin: false }
  pending.resolve(snapshot('saved'))
  await persistence.ready
  expect(store.userImages).toEqual([])
  expect(store.referenceImageKey).toBe('')
  expect(useStudioSession().referenceLoading).toBe(false)
})

it('surfaces failed writes and retries without losing in-memory references', async () => {
  const write = vi.fn().mockRejectedValueOnce(new Error('quota')).mockResolvedValue(undefined)
  const persistence = mount({ read: async () => undefined, write })
  const store = useGeneratorStore()
  store.userImages = [image()]
  await vi.waitFor(() => expect(useStudioSession().referenceSaving).toBe(false))
  expect(useStudioSession().referenceStorageError).toContain('尚未保存')
  expect(store.userImages).toHaveLength(1)
  await persistence.retry()
  expect(useStudioSession().referenceStorageError).toBe('')
})

it('persists settings changed independently of topic or outline', async () => {
  const store = useGeneratorStore()
  stops.push(setupAutoSave())
  store.outlinePlatform = 'douyin'
  store.outlineGoal = 'share'
  store.outlineAudience = '自定义'
  store.outlineAudienceDetail = '采购负责人'
  store.outlinePageCount = 7
  await nextTick()
  const saved = JSON.parse(localStorage.getItem('generator-state')!)
  expect(saved).toMatchObject({ outlinePlatform: 'douyin', outlineGoal: 'share',
    outlineAudienceDetail: '采购负责人', outlinePageCount: 7 })
})

it('surfaces text-storage failures instead of claiming a saved draft', () => {
  const store = useGeneratorStore()
  vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('quota') })
  vi.spyOn(console, 'error').mockImplementation(() => {})
  store.saveToStorage()
  expect(useStudioSession().localStorageError).toContain('保存失败')
})
