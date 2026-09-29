import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { getProcessingState, updatePostprocessing, type ProcessingState } from '../../src/api/postprocessing'
import { usePostprocessing } from '../../src/composables/usePostprocessing'
import { useAuthStore } from '../../src/stores/auth'

vi.mock('../../src/api/postprocessing', () => ({ getProcessingState: vi.fn(), updatePostprocessing: vi.fn() }))
vi.mock('../../src/api/image', () => ({ withToken: (url: string) => `${url}?token=test` }))

const fixture = (revision = 'source-a'): ProcessingState => ({
  success: true, preferences: { automatic: false, strength: 'light' },
  pages: [{ index: 0, source_revision: revision, original_url: '/original.png', processed_url: '/processed.png',
    strength: 'light', status: 'done', error: '', adopted: 'processed' }],
})
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (cause: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
let scope: ReturnType<typeof effectScope>
function setup(id: string | null = 'record-a') {
  const record = ref(id)
  scope = effectScope()
  const processing = scope.run(() => usePostprocessing(record))!
  return { record, ...processing }
}
beforeEach(() => {
  vi.useFakeTimers()
  vi.resetAllMocks()
  setActivePinia(createPinia())
  vi.mocked(getProcessingState).mockResolvedValue(fixture())
  vi.mocked(updatePostprocessing).mockResolvedValue(fixture())
})
afterEach(() => { scope?.stop(); vi.useRealTimers() })

describe('record-owned postprocessing', () => {
  it.each([401, 403, 404])('clears previously displayed image versions when access fails with %s', async status => {
    const p = setup()
    await p.refresh()
    expect(p.pages.value).toHaveLength(1)
    vi.mocked(getProcessingState).mockRejectedValue({
      code: 'ACCESS_DENIED', title: 'No access', detail: 'Sharing revoked', status,
    })
    await p.refresh()
    expect(p.pages.value).toEqual([])
    expect(p.error.value?.status).toBe(status)
    const reads = vi.mocked(getProcessingState).mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(getProcessingState).toHaveBeenCalledTimes(reads)
  })
  it('restores server preference/adoption and authenticates display URLs only', async () => {
    const p = setup()
    await p.refresh()
    expect(p.state.value).toEqual(fixture())
    expect(p.pages.value[0].processed_url).toBe('/processed.png?token=test')
    expect(p.state.value?.pages[0].processed_url).toBe('/processed.png')
    expect(p.loading.value).toBe(false)
  })

  it.each(['success', 'failure'] as const)('ignores late %s from another record and clears state immediately', async kind => {
    const old = deferred<ProcessingState>()
    vi.mocked(getProcessingState).mockReturnValueOnce(old.promise)
    const p = setup()
    p.record.value = 'record-b'
    expect(p.state.value).toBeNull()
    await p.refresh()
    if (kind === 'success') old.resolve(fixture('old'))
    else old.reject(new Error('Old error'))
    await Promise.resolve()
    expect(p.state.value?.pages[0].source_revision).toBe('source-a')
    expect(p.error.value).toBeNull()
    expect(p.loading.value).toBe(false)
  })

  it('never lets an earlier GET undo an explicit adoption', async () => {
    const read = deferred<ProcessingState>()
    vi.mocked(getProcessingState).mockReturnValueOnce(read.promise)
    const p = setup()
    const adopted = fixture()
    adopted.pages[0].adopted = 'original'
    vi.mocked(updatePostprocessing).mockResolvedValue(adopted)
    await p.adopt(0, 'original', 'source-a')
    read.resolve(fixture())
    await Promise.resolve()
    expect(p.state.value?.pages[0].adopted).toBe('original')
    expect(updatePostprocessing).toHaveBeenCalledWith('record-a', {
      action: 'adopt', index: 0, version: 'original', source_revision: 'source-a',
    })
  })

  it('submits immutable indices and defaults medium/skip; preferences do not process', async () => {
    const p = setup()
    const indices = [0]
    const action = p.process(indices)
    indices.push(1)
    await action
    expect(updatePostprocessing).toHaveBeenLastCalledWith('record-a', { action: 'process', indices: [0], strength: 'medium', force: false })
    await p.preferences(true, 'medium')
    expect(updatePostprocessing).toHaveBeenLastCalledWith('record-a', { action: 'preferences', automatic: true, strength: 'medium' })
  })

  it('serializes mutations and discards queued operations after record replacement', async () => {
    const action = deferred<ProcessingState>()
    vi.mocked(updatePostprocessing).mockReturnValueOnce(action.promise)
    const p = setup()
    const first = p.adopt(0, 'original', 'source-a')
    const second = p.adopt(0, 'processed', 'source-a')
    await Promise.resolve()
    expect(updatePostprocessing).toHaveBeenCalledTimes(1)
    p.record.value = 'record-b'
    await p.refresh()
    action.resolve(fixture('old'))
    await Promise.all([first, second])
    expect(updatePostprocessing).toHaveBeenCalledTimes(1)
    expect(p.state.value?.pages[0].source_revision).toBe('source-a')
  })

  it('keeps previous usable results on request failure and exposes partial page failures', async () => {
    const p = setup()
    await p.refresh()
    vi.mocked(updatePostprocessing).mockRejectedValueOnce(new Error('Unavailable'))
    expect(await p.process([0], 'heavy', true)).toBeNull()
    expect(p.pages.value[0].processed_url).toBeTruthy()
    expect(p.error.value).not.toBeNull()
    const result = fixture()
    result.pages.push({ ...result.pages[0], index: 1, processed_url: null, status: 'error', error: 'Conversion failed' })
    vi.mocked(getProcessingState).mockResolvedValue(result)
    await p.refresh()
    expect(p.pages.value.map(page => page.status)).toEqual(['done', 'error'])
  })

  it('polls idle records for generation publication and stops after disposal', async () => {
    const p = setup()
    await p.refresh()
    vi.mocked(getProcessingState).mockClear()
    await vi.advanceTimersByTimeAsync(2500)
    expect(getProcessingState).toHaveBeenCalledTimes(1)
    scope.stop()
    await vi.advanceTimersByTimeAsync(10000)
    expect(getProcessingState).toHaveBeenCalledTimes(1)
    expect(p.state.value).toBeNull()
  })

  it('rejects stale results after an auth session change', async () => {
    const read = deferred<ProcessingState>()
    vi.mocked(getProcessingState).mockReturnValueOnce(read.promise)
    const p = setup()
    useAuthStore().sessionRevision++
    await p.refresh()
    read.resolve(fixture('old'))
    await Promise.resolve()
    expect(p.state.value?.pages[0].source_revision).toBe('source-a')
    expect(p.error.value).toBeNull()
  })

  it('does not request or submit without a record', async () => {
    const p = setup(null)
    expect(await p.process([0])).toBeNull()
    expect(await p.refresh()).toBeNull()
    expect(getProcessingState).not.toHaveBeenCalled()
    expect(updatePostprocessing).not.toHaveBeenCalled()
  })
})
