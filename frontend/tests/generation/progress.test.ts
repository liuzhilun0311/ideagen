import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../../src/stores/generator'

beforeEach(() => setActivePinia(createPinia()))

function draft() {
  const store = useGeneratorStore()
  store.setOutline('cover\n\nbody', [
    { index: 0, type: 'cover', content: 'cover' },
    { index: 1, type: 'content', content: 'body' },
  ])
  store.startGeneration()
  return store
}

it('counts duplicate completion only once and ignores unknown indices', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.updateProgress(9, 'done', '/api/images/task/9.png')
  expect(store.progress.current).toBe(1)
})

it('keeps partial success on interruption and allows retry', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.stopGeneration('interrupted')
  expect(store.progress).toEqual({ current: 1, total: 2, status: 'error' })
  expect(store.images[0].status).toBe('done')
  expect(store.images[1]).toMatchObject({
    status: 'error', error: 'interrupted', retryable: true,
  })
})

it('does not mark a partially failed finish as successful', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.finishGeneration('task')
  expect(store.progress.status).toBe('error')
  expect(store.progress.current).toBe(1)
  expect(store.taskId).toBe('task')
})

it('recounts redraw and clears old errors when retry succeeds', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.setImageRetrying(0)
  expect(store.progress.current).toBe(0)
  store.updateProgress(0, 'error', undefined, 'failure')
  store.updateImage(0, '/api/images/task/0-new.png')
  expect(store.images[0].error).toBeUndefined()
  expect(store.progress.current).toBe(1)
})

it('clears a previous error on stream completion', () => {
  const store = draft()
  store.updateProgress(0, 'error', undefined, 'failure')
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  expect(store.images[0].error).toBeUndefined()
  expect(store.images[0].retryable).toBeUndefined()
})

it('keeps successful images and existing failures when stopping', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.updateProgress(1, 'error', undefined, 'provider failure')
  store.stopGeneration('cancelled')
  expect(store.images[0].url).toBe('/api/images/task/0.png')
  expect(store.images[1].error).toBe('provider failure')
  expect(store.progress.current).toBe(1)
})

it('does not keep a successful task status after a failed redraw', () => {
  const store = draft()
  store.updateProgress(0, 'done', '/api/images/task/0.png')
  store.updateProgress(1, 'done', '/api/images/task/1.png')
  store.finishGeneration('task')
  store.setImageRetrying(0)
  store.updateProgress(0, 'error', undefined, 'redraw failed')
  expect(store.progress).toEqual({ current: 1, total: 2, status: 'error' })
})
