import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

const actions = vi.hoisted(() => ({
  outlineStart: vi.fn(),
  outlineCancel: vi.fn(),
  imageStart: vi.fn(),
  imageCancel: vi.fn(),
  retry: vi.fn(),
}))
vi.mock('../../src/api', () => ({
  generateContent: vi.fn(),
  cancelCurrentGeneration: vi.fn(),
  getConfig: vi.fn(),
  getPrompts: vi.fn(),
}))
vi.mock('../../src/api/history', () => ({
  createHistory: vi.fn(),
  updateHistory: vi.fn(),
}))
vi.mock('../../src/composables/useOutlineGeneration', () => ({
  useOutlineGeneration: () => ({
    start: actions.outlineStart, cancel: actions.outlineCancel, error: ref(null),
  }),
}))
vi.mock('../../src/composables/useGenerationRunner', () => ({
  useGenerationRunner: () => ({
    startGenerationFlow: actions.imageStart, cancelGenerationFlow: actions.imageCancel,
  }),
}))
vi.mock('../../src/composables/useImageRetry', () => ({
  useImageRetry: () => ({ retrySingleImage: actions.retry }),
}))

import { cancelCurrentGeneration, generateContent, getConfig, getPrompts, type ContentResponse } from '../../src/api'
import { createHistory, updateHistory } from '../../src/api/history'
import { useStudio } from '../../src/composables/useStudio'
import { inspirations } from '../../src/features/templates/catalog'
import { useGeneratorStore } from '../../src/stores/generator'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

const content: ContentResponse = {
  success: true, titles: ['New title'], copywriting: 'New copy', tags: ['new'],
}
let studio: ReturnType<typeof useStudio>

beforeEach(async () => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  vi.mocked(getConfig).mockResolvedValue({
    success: true,
    config: {
      text_generation: {
        active_provider: 'text',
        providers: {
          text: { display_name: 'Editorial writer', model: 'internal-text-model' },
          fallback: { model: 'Fallback model' },
          plain: {},
        },
      },
      image_generation: {
        active_provider: 'image',
        providers: { image: { display_name: 'Photo studio', model: 'internal-image-model' } },
      },
    },
  })
  vi.mocked(getPrompts).mockResolvedValue({
    success: true, prompts: { outline: [], image: [], content: [] },
  })
  vi.mocked(createHistory).mockResolvedValue({ success: true, record_id: 'record' })
  vi.mocked(updateHistory).mockResolvedValue({ success: true })
  vi.mocked(generateContent).mockResolvedValue(content)
  vi.mocked(cancelCurrentGeneration).mockResolvedValue(undefined)
  actions.outlineStart.mockResolvedValue(true)
  actions.outlineCancel.mockResolvedValue(undefined)
  actions.imageStart.mockResolvedValue(undefined)
  actions.imageCancel.mockResolvedValue(undefined)
  actions.retry.mockResolvedValue(undefined)
  const store = useGeneratorStore()
  store.topic = 'City walk'
  store.setOutline('Cover', [{ index: 0, type: 'cover', content: 'Cover' }])
  store.setContent(['Saved title'], 'Saved copy', ['saved'])
  studio = useStudio()
  await studio.options.load()
})

describe('studio generation', () => {
  it.each(['images', 'content'] as const)('does not generate %s when record creation fails', async kind => {
    vi.mocked(createHistory).mockResolvedValue({ success: false, error: 'Creation failed' })
    await studio.run(kind)
    expect(updateHistory).not.toHaveBeenCalled()
    expect(generateContent).not.toHaveBeenCalled()
    expect(actions.imageStart).not.toHaveBeenCalled()
    expect(studio.error.value?.detail).toBe('Creation failed')
    expect(studio.phase.value).toBeNull()
    expect(studio.busy.value).toBe(false)
    expect(studio.store.content.copywriting).toBe('Saved copy')
  })

  it.each(['images', 'content'] as const)('does not generate %s when saving the draft fails', async kind => {
    vi.mocked(updateHistory).mockResolvedValue({ success: false, error: 'Save failed' })
    await studio.run(kind)
    expect(generateContent).not.toHaveBeenCalled()
    expect(actions.imageStart).not.toHaveBeenCalled()
    expect(studio.error.value?.detail).toBe('Save failed')
    expect(studio.saver.dirty.value).toBe(true)
    expect(studio.busy.value).toBe(false)
  })

  it.each(['images', 'content'] as const)('waits for saving before starting %s', async kind => {
    const saved = deferred<{ success: boolean }>()
    vi.mocked(updateHistory).mockReturnValue(saved.promise)
    const pending = studio.run(kind)
    await vi.waitFor(() => expect(updateHistory).toHaveBeenCalledOnce())
    expect(studio.busy.value).toBe(true)
    expect(generateContent).not.toHaveBeenCalled()
    expect(actions.imageStart).not.toHaveBeenCalled()
    saved.resolve({ success: true })
    await pending
    if (kind === 'images') expect(actions.imageStart).toHaveBeenCalledWith(true)
    else {
      expect(generateContent).toHaveBeenCalledWith('City walk', 'Cover', '', expect.any(AbortSignal), 'text')
      expect(studio.store.content).toMatchObject({
        titles: content.titles, copywriting: content.copywriting, tags: content.tags, status: 'done',
      })
    }
    expect(studio.busy.value).toBe(false)
  })

  it.each(['outline', 'images', 'content'] as const)('blocks every restart while %s cancellation is pending', async kind => {
    const generated = deferred<ContentResponse>()
    const outlineResult = deferred<boolean>()
    const imageResult = deferred<void>()
    const cancellation = deferred<void>()
    vi.mocked(generateContent).mockReturnValue(generated.promise)
    actions.outlineStart.mockReturnValue(outlineResult.promise)
    actions.imageStart.mockReturnValue(imageResult.promise)
    vi.mocked(cancelCurrentGeneration).mockReturnValue(cancellation.promise)
    actions.outlineCancel.mockReturnValue(cancellation.promise)
    actions.imageCancel.mockReturnValue(cancellation.promise)
    const pending = studio.run(kind)
    const starter = kind === 'outline' ? actions.outlineStart : kind === 'images' ? actions.imageStart : generateContent
    await vi.waitFor(() => expect(starter).toHaveBeenCalledOnce())
    const cancelled = studio.cancel()
    expect(studio.cancelling.value).toBe(true)
    expect(studio.busy.value).toBe(true)
    expect(studio.editingLocked.value).toBe(true)
    generated.resolve(content)
    outlineResult.resolve(false)
    imageResult.resolve()
    await pending
    expect(studio.phase.value).toBe(kind)
    for (const next of ['outline', 'images', 'content'] as const) await studio.run(next)
    await studio.retryPage(0)
    expect(actions.retry).not.toHaveBeenCalled()
    expect(actions.outlineStart).toHaveBeenCalledTimes(kind === 'outline' ? 1 : 0)
    expect(actions.imageStart).toHaveBeenCalledTimes(kind === 'images' ? 1 : 0)
    expect(generateContent).toHaveBeenCalledTimes(kind === 'content' ? 1 : 0)
    cancellation.resolve()
    await cancelled
    expect(studio.busy.value).toBe(false)
    expect(studio.editingLocked.value).toBe(false)
    await studio.run('content')
    expect(generateContent).toHaveBeenCalledTimes(kind === 'content' ? 2 : 1)
  })

  it('ignores content arriving during cancellation and retains previous content', async () => {
    const generated = deferred<ContentResponse>()
    const cancellation = deferred<void>()
    vi.mocked(generateContent).mockReturnValue(generated.promise)
    vi.mocked(cancelCurrentGeneration).mockReturnValue(cancellation.promise)
    const pending = studio.run('content')
    await vi.waitFor(() => expect(generateContent).toHaveBeenCalledOnce())
    const signal = vi.mocked(generateContent).mock.calls[0][3]
    const cancelled = studio.cancel()
    expect(signal?.aborted).toBe(true)
    generated.resolve(content)
    await pending
    expect(studio.store.content).toMatchObject({
      titles: ['Saved title'], copywriting: 'Saved copy', tags: ['saved'], status: 'done',
    })
    expect(studio.cancelling.value).toBe(true)
    expect(studio.error.value).toBeNull()
    cancellation.resolve()
    await cancelled
  })

  it.each(['images', 'content'] as const)('does not start %s if cancelled while saving', async kind => {
    const saved = deferred<{ success: boolean }>()
    vi.mocked(updateHistory).mockReturnValue(saved.promise)
    const pending = studio.run(kind)
    await vi.waitFor(() => expect(updateHistory).toHaveBeenCalledOnce())
    await studio.cancel()
    expect(studio.busy.value).toBe(true)
    saved.resolve({ success: true })
    await pending
    expect(generateContent).not.toHaveBeenCalled()
    expect(actions.imageStart).not.toHaveBeenCalled()
    expect(studio.busy.value).toBe(false)
  })

  it('handles cancellation API rejection without exposing a rejected promise to the caller', async () => {
    const generated = deferred<ContentResponse>()
    const cancellation = deferred<void>()
    vi.mocked(generateContent).mockReturnValue(generated.promise)
    vi.mocked(cancelCurrentGeneration).mockReturnValue(cancellation.promise)
    const pending = studio.run('content')
    await vi.waitFor(() => expect(generateContent).toHaveBeenCalledOnce())
    const cancelled = studio.cancel()
    const settled = expect(cancelled).resolves.toBeUndefined()
    cancellation.reject(new Error('Cancellation unavailable'))
    // Settle both requests even when the regression assertion fails.
    generated.reject(new Error('Aborted request'))
    await pending
    await settled
    expect(studio.error.value).toMatchObject({
      detail: 'Cancellation unavailable', title: '远端取消未确认',
    })
    expect(studio.cancelling.value).toBe(false)
    expect(studio.phase.value).toBeNull()
    expect(studio.busy.value).toBe(false)
    expect(studio.store.content.copywriting).toBe('Saved copy')
  })
})

describe('creation display details', () => {
  it('prefers display_name for text and image model labels without changing provider IDs', () => {
    expect(studio.options.textModels.value[0]).toEqual({ name: 'text', label: 'Editorial writer' })
    expect(studio.options.imageModels.value[0]).toEqual({ name: 'image', label: 'Photo studio' })
    expect(studio.store.outlineModelName).toBe('text')
    expect(studio.store.imageModelName).toBe('image')
  })

  it('retains model and provider-name fallbacks when display_name is absent', () => {
    expect(studio.options.textModels.value.slice(1)).toEqual([
      { name: 'fallback', label: 'fallback · Fallback model' },
      { name: 'plain', label: 'plain' },
    ])
  })

  it('describes the coffee inspiration photo as coffee pouring into a cup', () => {
    expect(inspirations.find(item => item.id === 'quiet-cafe')?.alt).toBe('咖啡倒入杯中')
  })
})
