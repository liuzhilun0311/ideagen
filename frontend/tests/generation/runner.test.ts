import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mocks = vi.hoisted(() => ({ ensureRecord: vi.fn(), push: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('../../src/api', () => ({
  generateImagesPost: vi.fn(),
  cancelCurrentGeneration: vi.fn(),
}))
vi.mock('../../src/composables/useGenerationRestore', () => ({
  useGenerationRestore: () => ({ ensureRecord: mocks.ensureRecord }),
}))

import { generateImagesPost, cancelCurrentGeneration } from '../../src/api'
import { useGeneratorStore } from '../../src/stores/generator'
import { useGenerationRunner } from '../../src/composables/useGenerationRunner'

type Call = Parameters<typeof generateImagesPost>

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function complete(args: Call, index = 0) {
  args[4]({ index, status: 'done', image_url: `/api/images/task/${index}.png` })
}

function finish(args: Call, taskId = 'task') {
  args[6]({ success: true, task_id: taskId, images: ['0.png', '1.png'] })
}

async function startPending(runner = useGenerationRunner(vi.fn())) {
  const stream = deferred<void>()
  vi.mocked(generateImagesPost).mockReturnValueOnce(stream.promise)
  const pending = runner.startGenerationFlow()
  await vi.waitFor(() => expect(generateImagesPost).toHaveBeenCalled())
  const calls = vi.mocked(generateImagesPost).mock.calls
  const args = calls[calls.length - 1]
  return { runner, stream, pending, args }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(generateImagesPost).mockReset().mockResolvedValue(undefined)
  vi.mocked(cancelCurrentGeneration).mockReset().mockResolvedValue(undefined)
  mocks.ensureRecord.mockReset().mockResolvedValue('record')
  mocks.push.mockReset().mockResolvedValue(undefined)
  useGeneratorStore().setOutline('cover\n\nbody', [
    { index: 0, type: 'cover', content: 'cover' },
    { index: 1, type: 'content', content: 'body' },
  ])
})

it('reports record failure without starting images and permits another attempt', async () => {
  mocks.ensureRecord.mockRejectedValueOnce(new Error('save failed'))
  const report = vi.fn()
  const runner = useGenerationRunner(report)
  await expect(runner.startGenerationFlow()).resolves.toBeUndefined()
  expect(generateImagesPost).not.toHaveBeenCalled()
  expect(useGeneratorStore().images).toEqual([])
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({ detail: 'save failed' }))
  await runner.startGenerationFlow()
  expect(generateImagesPost).toHaveBeenCalledOnce()
})

it('passes the returned record ID and preserves API argument positions', async () => {
  const store = useGeneratorStore()
  store.topic = 'topic'
  store.imagePromptName = 'prompt'
  store.imageModelName = 'model'
  await useGenerationRunner(vi.fn()).startGenerationFlow(true)
  const args = vi.mocked(generateImagesPost).mock.calls[0]
  expect(args.slice(9, 13)).toEqual(['topic', 'record', true, 'prompt'])
  expect(args[13]).toBeInstanceOf(AbortSignal)
  expect(args[14]).toBe('model')
})

it('blocks duplicate starts while the record is being created', async () => {
  const record = deferred<string>()
  mocks.ensureRecord.mockReturnValue(record.promise)
  const runner = useGenerationRunner(vi.fn())
  const pending = runner.startGenerationFlow()
  const duplicate = runner.startGenerationFlow(true)
  expect(mocks.ensureRecord).toHaveBeenCalledOnce()
  record.resolve('record')
  await Promise.all([pending, duplicate])
  expect(generateImagesPost).toHaveBeenCalledOnce()
})

it('awaits the stream and blocks duplicate starts while it is open', async () => {
  const { runner, stream, pending } = await startPending()
  const settled = vi.fn()
  void pending.then(settled)
  await runner.startGenerationFlow(true)
  expect(generateImagesPost).toHaveBeenCalledOnce()
  expect(settled).not.toHaveBeenCalled()
  stream.resolve()
  await pending
})

it('settles EOF without finish, preserves partial success and ignores late callbacks', async () => {
  const report = vi.fn()
  const { stream, pending, args } = await startPending(useGenerationRunner(report))
  complete(args)
  stream.resolve()
  await pending
  const store = useGeneratorStore()
  expect(store.progress).toEqual({ current: 1, total: 2, status: 'error' })
  expect(store.images[1]).toMatchObject({ status: 'error', retryable: true })
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: expect.stringContaining('连接中断'),
  }))
  const snapshot = JSON.stringify(store.$state)
  complete(args, 1)
  finish(args, 'late')
  args[7](new Error('late'))
  expect(JSON.stringify(store.$state)).toBe(snapshot)
  expect(report).toHaveBeenCalledTimes(2)
})

it('accepts successful finish and ignores duplicate or contradictory terminal callbacks', async () => {
  const report = vi.fn()
  vi.mocked(generateImagesPost).mockImplementation(async (...args) => {
    complete(args)
    complete(args, 1)
    finish(args)
    args[5]({ index: 0, status: 'error', error: 'late page error' })
    args[7](new Error('late stream error'))
    finish(args, 'late')
    throw new Error('late rejection')
  })
  await useGenerationRunner(report).startGenerationFlow()
  expect(useGeneratorStore().progress).toEqual({ current: 2, total: 2, status: 'done' })
  expect(useGeneratorStore().taskId).toBe('task')
  expect(report).toHaveBeenCalledTimes(1)
  expect(report).toHaveBeenLastCalledWith(null)
})

it('does not report success when every image arrived but finish is missing', async () => {
  const report = vi.fn()
  vi.mocked(generateImagesPost).mockImplementation(async (...args) => {
    complete(args)
    complete(args, 1)
  })
  await useGenerationRunner(report).startGenerationFlow()
  expect(useGeneratorStore().progress).toEqual({ current: 2, total: 2, status: 'error' })
  expect(useGeneratorStore().images.every(image => image.status === 'done')).toBe(true)
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: expect.stringContaining('连接中断'),
  }))
})

it('keeps page failures local and finishes with partial success', async () => {
  const report = vi.fn()
  vi.mocked(generateImagesPost).mockImplementation(async (...args) => {
    args[5]({ index: 1, status: 'error', error: 'page failed' })
    expect(useGeneratorStore().images[0].status).toBe('generating')
    complete(args)
    args[6]({ success: false, task_id: 'partial', images: ['0.png'] })
  })
  await useGenerationRunner(report).startGenerationFlow()
  expect(useGeneratorStore().progress).toEqual({ current: 1, total: 2, status: 'error' })
  expect(useGeneratorStore().images[1]).toMatchObject({ status: 'error', retryable: true })
  expect(useGeneratorStore().taskId).toBe('partial')
  expect(report).toHaveBeenCalledTimes(1)
  expect(report).toHaveBeenLastCalledWith(null)
})

it.each(['callback', 'rejection'] as const)('settles stream %s errors once with partial results', async mode => {
  const report = vi.fn()
  vi.mocked(generateImagesPost).mockImplementation(async (...args) => {
    complete(args)
    if (mode === 'rejection') throw new Error('stream failed')
    args[7](new Error('stream failed'))
    complete(args, 1)
    finish(args, 'late')
    args[7](new Error('duplicate error'))
  })
  await useGenerationRunner(report).startGenerationFlow()
  expect(useGeneratorStore().progress).toEqual({ current: 1, total: 2, status: 'error' })
  expect(useGeneratorStore().images[1].retryable).toBe(true)
  expect(useGeneratorStore().taskId).toBeNull()
  expect(report).toHaveBeenCalledTimes(2)
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({ detail: 'stream failed' }))
})

it('aborts locally, preserves results and ignores every late callback after cancel', async () => {
  const report = vi.fn()
  const { runner, stream, pending, args } = await startPending(useGenerationRunner(report))
  complete(args)
  runner.cancelGenerationFlow()
  runner.cancelGenerationFlow()
  expect(args[13]?.aborted).toBe(true)
  expect(cancelCurrentGeneration).toHaveBeenCalledOnce()
  const store = useGeneratorStore()
  expect(store.progress).toEqual({ current: 1, total: 2, status: 'error' })
  expect(store.images[1].error).toContain('本地已取消')
  const snapshot = JSON.stringify(store.$state)
  args[3]({ index: 1, status: 'generating' })
  complete(args, 1)
  args[5]({ index: 0, status: 'error', error: 'late' })
  finish(args, 'old')
  args[7](new Error('late'))
  stream.resolve()
  await pending
  expect(JSON.stringify(store.$state)).toBe(snapshot)
  expect(report).toHaveBeenCalledTimes(1)
  expect(report).toHaveBeenLastCalledWith(null)
})

it('blocks starts during cancellation then isolates a new run from old callbacks and cleanup', async () => {
  const cancellation = deferred<void>()
  vi.mocked(cancelCurrentGeneration).mockReturnValue(cancellation.promise)
  const report = vi.fn()
  const old = await startPending(useGenerationRunner(report))
  old.runner.cancelGenerationFlow()
  await old.runner.startGenerationFlow()
  expect(generateImagesPost).toHaveBeenCalledOnce()
  cancellation.resolve()
  await cancellation.promise
  // Allow the cancellation catch/finally chain to release the start gate.
  await Promise.resolve()
  const newStream = deferred<void>()
  vi.mocked(generateImagesPost).mockReturnValue(newStream.promise)
  const newPending = old.runner.startGenerationFlow()
  await vi.waitFor(() => expect(generateImagesPost).toHaveBeenCalledTimes(2))
  const current = vi.mocked(generateImagesPost).mock.calls[1]
  complete(old.args)
  finish(old.args, 'old')
  old.args[7](new Error('old'))
  old.stream.reject(new Error('old rejection'))
  await old.pending
  expect(useGeneratorStore().progress.status).toBe('generating')
  expect(useGeneratorStore().images[0].url).toBe('')
  await old.runner.startGenerationFlow()
  expect(generateImagesPost).toHaveBeenCalledTimes(2)
  complete(current)
  complete(current, 1)
  finish(current, 'new')
  newStream.resolve()
  await newPending
  expect(useGeneratorStore().taskId).toBe('new')
  expect(report).toHaveBeenLastCalledWith(null)
})

it('does not launch images when cancelled during record creation', async () => {
  const record = deferred<string>()
  mocks.ensureRecord.mockReturnValue(record.promise)
  const runner = useGenerationRunner(vi.fn())
  const pending = runner.startGenerationFlow()
  runner.cancelGenerationFlow()
  record.resolve('record')
  await pending
  expect(generateImagesPost).not.toHaveBeenCalled()
  expect(useGeneratorStore().images).toEqual([])
})

it('reports rejected cancellation without preventing a later start', async () => {
  vi.mocked(cancelCurrentGeneration).mockRejectedValue(new Error('cancel failed'))
  const report = vi.fn()
  const old = await startPending(useGenerationRunner(report))
  old.runner.cancelGenerationFlow()
  await vi.waitFor(() => expect(report).toHaveBeenLastCalledWith(expect.objectContaining({
    detail: 'cancel failed',
  })))
  await old.runner.startGenerationFlow()
  expect(generateImagesPost).toHaveBeenCalledTimes(2)
  old.stream.resolve()
  await old.pending
})

it('redirects an empty outline without creating a record or calling cancellation', async () => {
  useGeneratorStore().setOutline('', [])
  const runner = useGenerationRunner(vi.fn())
  await runner.startGenerationFlow()
  runner.cancelGenerationFlow()
  expect(mocks.push).toHaveBeenCalledWith('/')
  expect(mocks.ensureRecord).not.toHaveBeenCalled()
  expect(cancelCurrentGeneration).not.toHaveBeenCalled()
})

it.each(['updateProgress', 'finishGeneration'] as const)(
  'settles an exception from the %s callback through the API stream-error handler',
  async action => {
    const store = useGeneratorStore()
    vi.spyOn(store, action).mockImplementationOnce(() => { throw new Error('callback failed') })
    const report = vi.fn()
    vi.mocked(generateImagesPost).mockImplementation(async (...args) => {
      try {
        if (action === 'updateProgress') complete(args)
        else finish(args)
      } catch (error) {
        args[7](error)
      }
    })
    await useGenerationRunner(report).startGenerationFlow()
    expect(store.progress.status).toBe('error')
    expect(store.images.every(image => image.status === 'error' && image.retryable)).toBe(true)
    expect(report).toHaveBeenLastCalledWith(expect.objectContaining({ detail: 'callback failed' }))
  },
)

it('closes a finished transport without calling remote cancellation and permits a new run', async () => {
  const { runner, stream, pending, args } = await startPending()
  complete(args)
  complete(args, 1)
  finish(args)
  runner.cancelGenerationFlow()
  expect(cancelCurrentGeneration).not.toHaveBeenCalled()
  expect(args[13]?.aborted).toBe(true)
  expect(useGeneratorStore().stage).toBe('result')
  await runner.startGenerationFlow()
  expect(generateImagesPost).toHaveBeenCalledTimes(2)
  stream.resolve()
  await pending
})
