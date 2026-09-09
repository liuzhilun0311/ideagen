import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../src/api', () => ({
  createHistory: vi.fn(),
  getHistory: vi.fn(),
  getImageUrl: vi.fn(),
}))

import { createHistory, getHistory, getImageUrl, type HistoryDetail } from '../../src/api'
import { useGeneratorStore } from '../../src/stores/generator'
import { useGenerationRestore } from '../../src/composables/useGenerationRestore'
import { normalizeApiError } from '../../src/utils/errors'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(createHistory).mockReset()
  vi.mocked(getHistory).mockReset()
  vi.mocked(getImageUrl).mockReset()
})

it('rejects failed creation without accepting an ID from the failed response', async () => {
  vi.mocked(createHistory).mockResolvedValue({
    success: false, record_id: 'invalid', error: 'Storage unavailable',
  })
  await expect(useGenerationRestore().ensureRecord()).rejects.toMatchObject({
    code: expect.any(String),
    detail: 'Storage unavailable',
  })
  expect(useGeneratorStore().recordId).toBeNull()
})

it('returns an existing ID without creating another record', async () => {
  useGeneratorStore().setRecordId('existing')
  await expect(useGenerationRestore().ensureRecord()).resolves.toBe('existing')
  expect(createHistory).not.toHaveBeenCalled()
})

it('returns and persists a newly created ID using the current topic and outline', async () => {
  const store = useGeneratorStore()
  store.setTopic('Topic')
  store.setOutline('cover', [{ index: 0, type: 'cover', content: 'cover' }])
  vi.mocked(createHistory).mockResolvedValue({
    success: true, record_id: 'created',
  })
  await expect(useGenerationRestore().ensureRecord()).resolves.toBe('created')
  expect(store.recordId).toBe('created')
  expect(createHistory).toHaveBeenCalledOnce()
  expect(createHistory).toHaveBeenCalledWith('Topic', {
    raw: 'cover', pages: [{ index: 0, type: 'cover', content: 'cover' }],
  })
})

it.each([undefined, ''])('rejects success responses with invalid ID %s', async record_id => {
  vi.mocked(createHistory).mockResolvedValue({ success: true, record_id })
  await expect(useGenerationRestore().ensureRecord()).rejects.toMatchObject({
    code: expect.any(String),
  })
  expect(useGeneratorStore().recordId).toBeNull()
})

it('normalizes thrown network errors and leaves the record unset', async () => {
  vi.mocked(createHistory).mockRejectedValue(new Error('Network unavailable'))
  await expect(useGenerationRestore().ensureRecord()).rejects.toMatchObject({
    code: expect.any(String),
    detail: 'Network unavailable',
  })
  expect(useGeneratorStore().recordId).toBeNull()
})

it('uses error_message when the failed response has no error', async () => {
  vi.mocked(createHistory).mockResolvedValue({
    success: false, error_message: 'Record storage failed',
  })
  await expect(useGenerationRestore().ensureRecord()).rejects.toMatchObject({
    detail: 'Record storage failed',
    code: expect.any(String),
  })
  expect(useGeneratorStore().recordId).toBeNull()
})

it('preserves a structured API error', async () => {
  const error = normalizeApiError('Storage unavailable', 'Cannot save')
  vi.mocked(createHistory).mockResolvedValue({ success: false, error })
  await expect(useGenerationRestore().ensureRecord()).rejects.toBe(error)
  expect(useGeneratorStore().recordId).toBeNull()
})

it('does not fetch history without a record ID', async () => {
  await expect(useGenerationRestore().restoreFromHistory()).resolves.toBe(false)
  expect(getHistory).not.toHaveBeenCalled()
  expect(createHistory).not.toHaveBeenCalled()
})

it('clears an inaccessible history record without creating a replacement', async () => {
  useGeneratorStore().setRecordId('missing')
  vi.mocked(getHistory).mockResolvedValue({ success: false })
  await expect(useGenerationRestore().restoreFromHistory()).resolves.toBe(false)
  expect(getHistory).toHaveBeenCalledWith('missing')
  expect(useGeneratorStore().recordId).toBeNull()
  expect(createHistory).not.toHaveBeenCalled()
})

it.each([false, true])('preserves history hydration for complete=%s', async complete => {
  const record: HistoryDetail = {
    id: 'saved',
    title: 'Saved topic',
    created_at: '',
    updated_at: '',
    status: 'completed',
    thumbnail: null,
    outline: {
      raw: 'cover\n\nbody',
      pages: [
        { index: 0, type: 'cover', content: 'cover' },
        { index: 1, type: 'content', content: 'body' },
      ],
    },
    images: { task_id: 'task', generated: complete ? ['0.png', '1.png'] : ['0.png'] },
    content: { titles: ['Title'], copywriting: 'Copy', tags: ['tag'] },
  }
  const store = useGeneratorStore()
  store.setRecordId(record.id)
  vi.mocked(getHistory).mockResolvedValue({ success: true, record })
  vi.mocked(getImageUrl).mockImplementation((task, filename) => `/api/images/${task}/${filename}`)
  await expect(useGenerationRestore().restoreFromHistory()).resolves.toBe(true)
  expect(store.topic).toBe(record.title)
  expect(store.outline).toEqual(record.outline)
  expect(store.recordId).toBe(record.id)
  expect(store.taskId).toBe('task')
  expect(store.content).toMatchObject({ ...record.content, status: 'done' })
  expect(store.progress).toEqual({
    current: complete ? 2 : 1, total: 2, status: complete ? 'done' : 'error',
  })
  expect(store.stage).toBe(complete ? 'result' : 'generating')
  expect(store.images).toEqual([
    { index: 0, url: '/api/images/task/0.png', status: 'done', retryable: false },
    {
      index: 1,
      url: complete ? '/api/images/task/1.png' : '',
      status: complete ? 'done' : 'error',
      retryable: !complete,
    },
  ])
  expect(createHistory).not.toHaveBeenCalled()
})
