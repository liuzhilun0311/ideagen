import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../src/api', () => ({ generateOutline: vi.fn(), cancelCurrentGeneration: vi.fn() }))
import { cancelCurrentGeneration, generateOutline, type OutlineResponse } from '../../src/api'
import { useGeneratorStore } from '../../src/stores/generator'
import { useOutlineGeneration } from '../../src/composables/useOutlineGeneration'
import { resolveImageStyle } from '../../src/features/styles/catalog'
import { useStudioSession } from '../../src/stores/studioSession'
import { outlineRequest } from '../../src/features/outlineRequest'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const result: OutlineResponse = {
  success: true, outline: 'Cover', pages: [{ index: 0, type: 'cover', content: 'Cover' }],
}
it.each(['auto', 'watercolor'])('uses the displayed growth recommendation as the automatic style source (%s)', async preset => {
  const store = useGeneratorStore()
  store.imageStyle = { preset, notes: 'Keep notes' }
  vi.mocked(generateOutline).mockResolvedValue({
    ...result,
    style_recommendation: { preset: 'infographic', reason: 'Legacy', alternatives: [] },
    growth_recommendation: { platform: 'douyin', goal: 'follow', layout: '清单',
      image_style: 'high-contrast-promo', aspect_ratio: '9:16', content_structure: '重点', reason: '平台适配' },
  })
  expect(await useOutlineGeneration().start()).toBe(true)
  expect(store.imageStyle.preset).toBe('high-contrast-promo')
  expect(store.imageStyle.recommendation?.preset).toBe('high-contrast-promo')
  expect(resolveImageStyle(store.imageStyle)).toEqual({
    preset: 'high-contrast-promo', notes: 'Keep notes',
  })
  expect(store.imageAspectRatio).toBe('9:16')
  expect(store.outline.pages[0]?.layout).toBe('清单')
  expect(store.outline.raw).toContain('单页布局：清单')
})
beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  vi.mocked(generateOutline).mockReset()
  vi.mocked(cancelCurrentGeneration).mockReset().mockResolvedValue(undefined)
  useGeneratorStore().topic = 'A city walk'
  useGeneratorStore().outlineModelName = 'text'
})

it.each(['auto', 'red'])('stores fresh palette recommendations without replacing %s intent', async mode => {
  const store = useGeneratorStore()
  store.imageStyle.palette = { mode, recommendation: 'blue', reason: 'old' }
  vi.mocked(generateOutline).mockResolvedValue({
    ...result, generation_recommendation: { palette: 'lavender', palette_reason: '柔和背景突出知识层级' },
  })
  expect(await useOutlineGeneration().start()).toBe(true)
  expect(store.imageStyle.palette).toEqual({ mode, recommendation: 'lavender', reason: '柔和背景突出知识层级' })
  vi.mocked(generateOutline).mockResolvedValue(result)
  expect(await useOutlineGeneration().start()).toBe(true)
  expect(store.imageStyle.palette).toEqual({ mode })
})

it('keeps reference roles when submitting the home form', async () => {
  const store = useGeneratorStore()
  store.referenceRoles = ['subject']
  store.prepareNewOutline()
  vi.mocked(generateOutline).mockResolvedValue(result)
  await useOutlineGeneration().start()
  expect(vi.mocked(generateOutline).mock.calls[0]?.[8]).toEqual(['subject'])
})

it('preserves manual copy choices and automatic platform intent on regeneration', async () => {
  const store = useGeneratorStore()
  const copy = { style: '自然分享', structure: '步骤说明', length: '适中', emoji_level: '无' }
  store.outline.copy_preferences = { ...copy }
  store.outlinePlatform = 'auto'
  vi.mocked(generateOutline).mockResolvedValue({
    ...result,
    generation_preferences: { organization: '自动', audience: '自动判断', audience_detail: '',
      tone: '自动匹配', page_count: 'auto', platform: 'douyin', goal: 'follow' },
    generation_recommendation: { copy_style: '专业科普', copy_length: '详细', emoji_level: '丰富' },
  })
  expect(await useOutlineGeneration().start()).toBe(true)
  expect(store.outline.copy_preferences).toMatchObject(copy)
  expect(store.outlinePlatform).toBe('auto')
  expect(store.outline.generation_preferences?.platform).toBe('douyin')
  expect(store.outline.requested_preferences?.platform).toBe('auto')
})

it('refreshes saved automatic copy choices on every successful outline', async () => {
  const store = useGeneratorStore()
  vi.mocked(generateOutline).mockResolvedValue({
    ...result, generation_recommendation: { copy_style: '自然分享', copy_length: '简短', emoji_level: '无' },
  })
  expect(await useOutlineGeneration().start()).toBe(true)
  store.outline.copy_preferences = JSON.parse(JSON.stringify(store.outline.copy_preferences))
  vi.mocked(generateOutline).mockResolvedValue({
    ...result, generation_recommendation: { copy_style: '专业科普', copy_length: '详细', emoji_level: '丰富' },
  })
  expect(await useOutlineGeneration().start()).toBe(true)
  expect(store.outline.copy_preferences).toMatchObject({
    style: '专业科普', structure: '自动', length: '详细', emoji_level: '丰富',
    modes: { style: 'auto', structure: 'auto', length: 'auto', emoji_level: 'auto' },
  })
})

it.each(['auto', 'watercolor'])('initializes the new outline style from its recommendation over %s', async preset => {
  const store = useGeneratorStore()
  store.imageStyle = { preset, notes: 'quiet' }
  const recommendation = { preset: 'sketch-note', reason: '学习结构', alternatives: ['comic', 'infographic'] }
  vi.mocked(generateOutline).mockResolvedValue({ ...result, style_recommendation: recommendation })
  expect(await useOutlineGeneration().start()).toBe(true)
  expect(store.imageStyle).toEqual({ preset: 'sketch-note', notes: 'quiet', recommendation })
  expect(store.outline.raw).not.toContain('学习结构')
  expect(JSON.parse(localStorage.getItem('generator-state')!).imageStyle.recommendation).toEqual(recommendation)
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
    'A city walk', [image], expect.any(AbortSignal), '', 'Calm tone', 'text', store.outlineOrganization,
    { organization: store.outlineOrganization, audience: store.outlineAudience,
      audience_detail: store.outlineAudienceDetail, tone: store.outlineTone, page_count: 'auto',
      content_form: 'auto', information_density: 'auto' },
    store.referenceRoles,
  )
  request.resolve(result)
  expect(await pending).toBe(true)
  expect(store.outline.pages).toEqual(result.pages)
  expect(store.outlineStatus).toBe('done')
  expect(action.generating.value).toBe(false)
  expect(prepare).not.toHaveBeenCalled()
})

it('rejects a fixed-count response without replacing the current outline', async () => {
  const store = useGeneratorStore()
  store.outlinePageCount = 5
  store.setOutline('Existing', [{ index: 0, type: 'cover', content: 'Existing' }])
  vi.mocked(generateOutline).mockResolvedValue({
    ...result,
    pages: [
      { index: 0, type: 'cover', content: 'Cover' },
      { index: 1, type: 'content', content: 'Content' },
      { index: 2, type: 'content', content: 'Content' },
      { index: 3, type: 'summary', content: 'Summary' },
    ],
  })
  const action = useOutlineGeneration()
  expect(await action.start()).toBe(false)
  expect(store.outline.raw).toBe('Existing')
  expect(action.error.value?.detail).toContain('指定页数')
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

it('keeps a failed diagnostic record without replacing successful outline provenance', async () => {
  const store = useGeneratorStore()
  store.outline.generation_record_id = 'previous-success'
  vi.mocked(generateOutline).mockRejectedValue({
    isAxiosError: true,
    response: { data: {
      generation_record: { id: 'failed-run' },
      error: { code: 'NETWORK_TIMEOUT', title: 'Timeout', detail: 'Upstream timeout' },
    } },
  })
  expect(await useOutlineGeneration().start()).toBe(false)
  expect(store.outline.diagnostic_record_id).toBe('failed-run')
  expect(store.outline.generation_record_id).toBe('previous-success')
  expect(JSON.parse(localStorage.getItem('generator-state')!).outline.diagnostic_record_id).toBe('failed-run')
})

it('keeps a record from a resolved failure and clears it on new creation', async () => {
  vi.mocked(generateOutline).mockResolvedValue({
    success: false, generation_record: { id: 'failed-run' }, error_message: 'Failure',
  } as OutlineResponse)
  expect(await useOutlineGeneration().start()).toBe(false)
  const store = useGeneratorStore()
  expect(store.outline.diagnostic_record_id).toBe('failed-run')
  store.prepareNewOutline()
  expect(store.outline.diagnostic_record_id).toBeUndefined()
})

it('persists the successful outline record for diagnostics without an image task', async () => {
  vi.mocked(generateOutline).mockResolvedValue({
    ...result, generation_record: { id: 'successful-run' },
  } as OutlineResponse)
  expect(await useOutlineGeneration().start()).toBe(true)
  const store = useGeneratorStore()
  expect(store.taskId).toBeNull()
  expect(store.outline.generation_record_id).toBe('successful-run')
  expect(store.outline.diagnostic_record_id).toBe('successful-run')
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

function existingWork() {
  const store = useGeneratorStore()
  store.setOutline('Old outline', [{ index: 0, type: 'cover', content: 'Old outline' }])
  store.recordId = 'saved-work'
  store.taskId = 'old-images'
  store.images = [{ index: 0, url: 'old.png', status: 'done' }]
  store.setContent(['Old title'], 'Old copy', [])
  return store
}

it('home generation retains old results until success and then detaches the saved work', async () => {
  const store = existingWork()
  store.outlineOrganization = '步骤教程'
  store.outlineTone = '专业简洁'
  const preview = outlineRequest(store, true)
  const request = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  const pending = useOutlineGeneration({ home: true }).start()
  expect(store.outline.raw).toBe('Old outline')
  expect(store.recordId).toBe('saved-work')
  expect(store.images[0]?.url).toBe('old.png')
  const actual = vi.mocked(generateOutline).mock.calls[0]!
  expect(actual[6]).toBe(preview.preferences.organization)
  expect(actual[7]).toMatchObject({ organization: '步骤教程', tone: '自动匹配' })
  request.resolve(result)
  expect(await pending).toBe(true)
  expect(store.recordId).toBeNull()
  expect(store.images).toEqual([])
  expect(store.content.copywriting).toBe('')
  expect(useStudioSession().revision).toBe(1)
})

it.each(['failure', 'cancel'])('home generation preserves outline, images, copy and record on %s', async kind => {
  const store = existingWork()
  const request = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  const action = useOutlineGeneration({ home: true })
  const pending = action.start()
  if (kind === 'cancel') await action.cancel()
  request.reject(new Error('Failed'))
  expect(await pending).toBe(false)
  expect(store.outline.raw).toBe('Old outline')
  expect(store.recordId).toBe('saved-work')
  expect(store.taskId).toBe('old-images')
  expect(store.images[0]?.url).toBe('old.png')
  expect(store.content.copywriting).toBe('Old copy')
  expect(useStudioSession().revision).toBe(0)
})

it('ignores a result when a different draft took ownership', async () => {
  const store = existingWork()
  const request = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  const pending = useOutlineGeneration({ home: true }).start()
  useStudioSession().revision++
  store.setOutline('Another draft', [{ index: 0, type: 'cover', content: 'Another draft' }])
  request.resolve(result)
  expect(await pending).toBe(false)
  expect(store.outline.raw).toBe('Another draft')
})

it('keeps the previous work and reports when remote cancellation fails', async () => {
  const store = existingWork()
  const request = deferred<OutlineResponse>()
  vi.mocked(generateOutline).mockReturnValue(request.promise)
  vi.mocked(cancelCurrentGeneration).mockRejectedValue(new Error('Cancel timeout'))
  const action = useOutlineGeneration({ home: true })
  const pending = action.start()
  await action.cancel()
  expect(action.error.value?.detail).toContain('Cancel timeout')
  expect(action.generating.value).toBe(false)
  expect(action.cancelling.value).toBe(false)
  request.resolve(result)
  expect(await pending).toBe(false)
  expect(store.outline.raw).toBe('Old outline')
  expect(store.recordId).toBe('saved-work')
})
