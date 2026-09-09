import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../src/api/history', () => ({
  createHistory: vi.fn(),
  updateHistory: vi.fn(),
}))

import { createHistory, updateHistory } from '../../src/api/history'
import { useGeneratorStore } from '../../src/stores/generator'
import { useDraftSave } from '../../src/composables/useDraftSave'
import { useStudioSession } from '../../src/stores/studioSession'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(createHistory).mockReset().mockResolvedValue({ success: true, record_id: 'record' })
  vi.mocked(updateHistory).mockReset().mockResolvedValue({ success: true })
  const store = useGeneratorStore()
  store.topic = 'City walk'
  store.setOutline('cover', [{ index: 0, type: 'cover', content: 'cover' }])
})

it('creates and updates a snapshot before marking saved', async () => {
  const store = useGeneratorStore()
  const saver = useDraftSave()
  expect(saver.dirty.value).toBe(true)
  expect(await saver.save()).toBe(true)
  expect(store.recordId).toBe('record')
  expect(updateHistory).toHaveBeenCalledWith('record', expect.objectContaining({
    title: 'City walk',
    outline: { raw: 'cover', pages: [{ index: 0, type: 'cover', content: 'cover' }] },
  }))
  expect(saver.dirty.value).toBe(false)
})

it('does not update when creation fails', async () => {
  vi.mocked(createHistory).mockResolvedValue({ success: false, error: 'offline' })
  const saver = useDraftSave()
  expect(await saver.save()).toBe(false)
  expect(updateHistory).not.toHaveBeenCalled()
  expect(saver.dirty.value).toBe(true)
  expect(saver.error.value?.detail).toBe('offline')
})

it('does not mark failed updates as saved', async () => {
  vi.mocked(updateHistory).mockResolvedValue({ success: false, error: 'update failed' })
  const saver = useDraftSave()
  expect(await saver.save()).toBe(false)
  expect(saver.dirty.value).toBe(true)
  expect(saver.error.value?.detail).toBe('update failed')
})

it('shares an in-flight save and keeps edits during the request dirty', async () => {
  let finish!: (value: { success: boolean }) => void
  vi.mocked(updateHistory).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const saver = useDraftSave()
  const first = saver.save()
  expect(saver.save()).toBe(first)
  await vi.waitFor(() => expect(updateHistory).toHaveBeenCalledOnce())
  useGeneratorStore().updatePage(0, 'updated while saving')
  finish({ success: true })
  expect(await first).toBe(true)
  expect(saver.dirty.value).toBe(true)
  expect(useGeneratorStore().outline.pages[0].content).toBe('updated while saving')
  vi.mocked(updateHistory).mockResolvedValue({ success: true })
  expect(await saver.save()).toBe(true)
  expect(saver.dirty.value).toBe(false)
})

it('does not send image state with text edits or overwrite generated files', async () => {
  const saver = useDraftSave()
  await saver.save()
  expect(updateHistory).toHaveBeenCalledWith('record', expect.not.objectContaining({
    images: expect.anything(),
  }))
})

it('does not assume a restored record ID proves the local draft was saved', () => {
  useGeneratorStore().setRecordId('existing')
  expect(useDraftSave().dirty.value).toBe(true)
})

it('retains the confirmed snapshot across workspace remounts', async () => {
  const store = useGeneratorStore()
  await useDraftSave().save()
  expect(useDraftSave().dirty.value).toBe(false)
  store.updatePage(0, 'unsaved edit')
  expect(useDraftSave().dirty.value).toBe(true)
})

it('does not reuse confirmation for a different record', async () => {
  await useDraftSave().save()
  useGeneratorStore().setRecordId('another')
  expect(useDraftSave().dirty.value).toBe(true)
})

it('invalidates the cached workspace save baseline when replacing a draft', async () => {
  const saver = useDraftSave()
  await saver.save()
  saver.resetBaseline()
  expect(saver.dirty.value).toBe(true)
})

it('does not mark a replacement draft saved when an older save completes', async () => {
  const store = useGeneratorStore()
  store.setRecordId('old')
  let finish!: (result: { success: boolean }) => void
  vi.mocked(updateHistory).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const saver = useDraftSave()
  const save = saver.save()
  useStudioSession().replaceDraft()
  store.setRecordId('new')
  store.updatePage(0, 'New draft')
  finish({ success: true })
  expect(await save).toBe(false)
  expect(store.recordId).toBe('new')
  expect(saver.dirty.value).toBe(true)
})
