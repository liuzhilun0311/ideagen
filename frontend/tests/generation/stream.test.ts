import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('../../src/composables/useGenerationRestore', () => ({
  useGenerationRestore: () => ({ ensureRecord: async () => 'record' }),
}))

import { useGeneratorStore } from '../../src/stores/generator'
import { useGenerationRunner } from '../../src/composables/useGenerationRunner'

function sseResponse(text: string) {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      // Split across event/data boundaries to exercise the real client's buffer.
      for (let offset = 0; offset < bytes.length; offset += 7) {
        controller.enqueue(bytes.slice(offset, offset + 7))
      }
      controller.close()
    },
  }), { headers: { 'Content-Type': 'text/event-stream' } })
}

function event(name: string, data: object) {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`
}

const complete = event('complete', {
  index: 0, status: 'done', image_url: '/api/images/task/0.png',
})

beforeEach(() => {
  setActivePinia(createPinia())
  useGeneratorStore().setOutline('cover\n\nbody', [
    { index: 0, type: 'cover', content: 'cover' },
    { index: 1, type: 'content', content: 'body' },
  ])
})

afterEach(() => vi.unstubAllGlobals())

it('passes actual SSE chunks through the API client and preserves partial results', async () => {
  const fetchMock = vi.fn().mockResolvedValue(sseResponse(
    complete
    + event('error', { index: 1, status: 'error', message: 'provider failed' })
    + event('finish', { success: false, task_id: 'task', images: ['0.png'] }),
  ))
  vi.stubGlobal('fetch', fetchMock)
  const report = vi.fn()
  await useGenerationRunner(report).startGenerationFlow()
  expect(fetchMock).toHaveBeenCalledOnce()
  expect(fetchMock.mock.calls[0][0]).toBe('/api/generate')
  expect(JSON.parse(fetchMock.mock.calls[0][1].body).record_id).toBe('record')
  expect(useGeneratorStore().progress).toEqual({ current: 1, total: 2, status: 'error' })
  expect(useGeneratorStore().taskId).toBe('task')
  expect(report).toHaveBeenLastCalledWith(null)
})

it('recognizes EOF without finish using the real API reader', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse(complete)))
  const report = vi.fn()
  await useGenerationRunner(report).startGenerationFlow()
  expect(useGeneratorStore().images[0].status).toBe('done')
  expect(useGeneratorStore().images[1].status).toBe('error')
  expect(useGeneratorStore().progress.status).toBe('error')
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: expect.stringContaining('\u8fde\u63a5\u4e2d\u65ad'),
  }))
})

it('settles HTTP rejection through readErrorResponse without leaving spinners', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
    JSON.stringify({ error: 'provider unavailable' }),
    { status: 503, headers: { 'Content-Type': 'application/json' } },
  )))
  const report = vi.fn()
  await useGenerationRunner(report).startGenerationFlow()
  expect(useGeneratorStore().images.every(image => image.status === 'error')).toBe(true)
  expect(useGeneratorStore().progress.status).toBe('error')
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: 'provider unavailable',
  }))
})

it('settles a disconnected response body and retains already received images', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(complete))
      },
      pull(controller) {
        controller.error(new Error('connection lost'))
      },
    }),
    { headers: { 'Content-Type': 'text/event-stream' } },
  )))
  const report = vi.fn()
  await useGenerationRunner(report).startGenerationFlow()
  expect(useGeneratorStore().images[0].status).toBe('done')
  expect(useGeneratorStore().progress).toEqual({ current: 1, total: 2, status: 'error' })
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: 'connection lost',
  }))
})

it('handles a store callback exception through the actual SSE reader', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse(
    complete
    + event('complete', { index: 1, status: 'done', image_url: '/api/images/task/1.png' })
    + event('finish', { success: true, task_id: 'late', images: ['0.png', '1.png'] }),
  )))
  const store = useGeneratorStore()
  vi.spyOn(store, 'updateProgress').mockImplementationOnce(() => {
    throw new Error('callback failed')
  })
  const report = vi.fn()
  await useGenerationRunner(report).startGenerationFlow()
  expect(store.images.every(image => image.status === 'error')).toBe(true)
  expect(store.taskId).toBeNull()
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: 'callback failed',
  }))
})
