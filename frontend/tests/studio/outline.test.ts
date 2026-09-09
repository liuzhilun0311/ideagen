import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../src/api', () => ({ generateOutline: vi.fn(), cancelCurrentGeneration: vi.fn() }))
import { cancelCurrentGeneration, generateOutline, type OutlineResponse } from '../../src/api'
import { useGeneratorStore } from '../../src/stores/generator'
import { useOutlineGeneration } from '../../src/composables/useOutlineGeneration'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const result: OutlineResponse = {
  success: true, outline: 'Cover', pages: [{ index: 0, type: 'cover', content: 'Cover' }],
}
beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(generateOutline).mockReset()
  vi.mocked(cancelCurrentGeneration).mockReset().mockResolvedValue(undefined)
  useGeneratorStore().topic = 'A city walk'
  useGeneratorStore().outlineModelName = 'text'
})

it('passes every reference input and updates status without preparing a new draft', async () => {
  const store = useGeneratorStore()
  const image = new File(['image'], 'ref.png', { type: 'image/png' })
  store.userImages = [image]
  store.referenceContent = 'Calm tone'
  store.outlinePromptName = 'editorial'
  const prepare = vi.spyOn(store, 'prepareNewOutline')
  const request = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  const action = useOutlineGeneration()
  const pending = action.start()
  expect(action.generating.value).toBe(true)
  expect(store.outlineStatus).toBe('generating')
  expect(generateOutline).toHaveBeenCalledWith(
    'A city walk', [image], expect.any(AbortSignal), 'editorial', 'Calm tone', 'text',
  )
  request.resolve(result)
  expect(await pending).toBe(true)
  expect(store.outline.pages).toEqual(result.pages)
  expect(store.outlineStatus).toBe('done')
  expect(action.generating.value).toBe(false)
  expect(prepare).not.toHaveBeenCalled()
})

it('aborts and ignores a cancelled response without clearing inputs', async () => {
  const store = useGeneratorStore()
  const request = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  const action = useOutlineGeneration()
  const pending = action.start()
  const signal = vi.mocked(generateOutline).mock.calls[0][2]
  await action.cancel()
  expect(signal?.aborted).toBe(true)
  expect(store.outlineStatus).toBe('idle')
  request.resolve(result)
  expect(await pending).toBe(false)
  expect(store.outline.pages).toEqual([])
  expect(store.topic).toBe('A city walk')
  expect(action.error.value).toBeNull()
})

it('prevents duplicate requests', async () => {
  const request = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  const action = useOutlineGeneration()
  const pending = action.start()
  expect(await action.start()).toBe(false)
  expect(generateOutline).toHaveBeenCalledOnce()
  request.resolve(result)
  await pending
})

it('does not let an old rejection reset a newer request', async () => {
  const old = deferred<OutlineResponse>()
  const next = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValueOnce(old.promise).mockReturnValueOnce(next.promise)
  const action = useOutlineGeneration()
  const first = action.start()
  await action.cancel()
  const second = action.start()
  old.reject(new Error('late'))
  expect(await first).toBe(false)
  expect(action.generating.value).toBe(true)
  expect(action.error.value).toBeNull()
  next.resolve(result)
  expect(await second).toBe(true)
})

it('blocks starts until backend cancellation settles and coalesces cancellation', async () => {
  const request = deferred<OutlineResponse>()
  const cancellation = deferred<void>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  vi.mocked(cancelCurrentGeneration).mockReturnValue(cancellation.promise)
  const action = useOutlineGeneration()
  const pending = action.start()
  const cancelled = action.cancel()
  const again = action.cancel()
  expect(action.cancelling.value).toBe(true)
  expect(await action.start()).toBe(false)
  expect(cancelCurrentGeneration).toHaveBeenCalledOnce()
  request.resolve(result)
  expect(await pending).toBe(false)
  expect(action.cancelling.value).toBe(true)
  cancellation.resolve()
  await Promise.all([cancelled, again])
  expect(action.cancelling.value).toBe(false)
  expect(action.generating.value).toBe(false)
  expect(useGeneratorStore().outlineStatus).toBe('idle')
})

it.each([
  { success: false, error_message: 'Unavailable' },
  { success: true, outline: 'Empty', pages: [] },
])('rejects failed or empty responses and preserves existing outline', async response => {
  const store = useGeneratorStore()
  store.setOutline('Existing', [{ index: 0, type: 'cover', content: 'Existing' }])
  vi.mocked(generateOutline).mockResolvedValue(response)
  const action = useOutlineGeneration()
  expect(await action.start()).toBe(false)
  expect(store.outline.raw).toBe('Existing')
  expect(store.outlineStatus).toBe('error')
  expect(action.error.value?.detail).toBeTruthy()
})

it.each(['topic', 'outlineModelName'] as const)('rejects missing %s before requesting', async field => {
  useGeneratorStore()[field] = ' '
  const action = useOutlineGeneration()
  expect(await action.start()).toBe(false)
  expect(generateOutline).not.toHaveBeenCalled()
  expect(action.error.value).not.toBeNull()
})
