import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../../src/stores/generator'
import { usePageTrials } from '../../src/composables/usePageTrials'
import { generateCandidate, adoptCandidate, type ImageCandidate } from '../../src/api/candidates'
import { setToken } from '../../src/api/token'
import { imageParameters } from '../../src/features/generationOptions'
import { fallbackItems, usePromptCatalogStore } from '../../src/features/promptCatalog'

vi.mock('../../src/api/candidates', () => ({
  generateCandidate: vi.fn(), adoptCandidate: vi.fn(), listCandidates: vi.fn(async () => []),
}))
const candidate: ImageCandidate = {
  id: 'candidate', index: 1, style: { preset: 'sketch-note', notes: '' },
  prompt: 'Hand drawn', provider: 'model', status: 'ready', image_url: '/candidate.png',
  adopted: false, stale: false, created_at: '',
}
beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  vi.clearAllMocks()
  const store = useGeneratorStore()
  store.topic = 'Desk'
  store.recordId = 'record'
  store.setOutline('', [{ index: 0, type: 'cover', content: 'Desk' }, { index: 1, type: 'content', content: 'Tips' }])
  store.recordId = 'record'
  store.imageStyle = { preset: 'comic', notes: '' }
  vi.mocked(generateCandidate).mockResolvedValue(candidate)
  vi.mocked(adoptCandidate).mockResolvedValue({ candidate, task_id: 'task', image_url: '/api/images/task/version_new.png' })
})
it('generates a single trial before any image exists without publishing or changing set style', async () => {
  const store = useGeneratorStore()
  const trials = usePageTrials(vi.fn(async () => true), vi.fn())
  await trials.trial(1, candidate.style)
  expect(generateCandidate).toHaveBeenCalledWith('record', 1, candidate.style, '', '', [], imageParameters(store), false, store.referenceRoles)
  expect(adoptCandidate).not.toHaveBeenCalled()
  expect(store.images).toEqual([])
  expect(store.imageStyle.preset).toBe('comic')
})
it('sends only the resolved recommendation or explicit trial choice, without changing set preference', async () => {
  const store = useGeneratorStore()
  store.imageStyle = { preset: 'auto', notes: '', recommendation: { preset: 'ink', reason: '文化', alternatives: ['pencil'] } }
  const trials = usePageTrials(vi.fn(async () => true), vi.fn())
  await trials.trial(1, { preset: 'auto', notes: '' })
  expect(generateCandidate).toHaveBeenLastCalledWith('record', 1, { preset: 'ink', notes: '' }, '', '', [], imageParameters(store), false, store.referenceRoles)
  await trials.trial(1, { preset: 'clay', notes: 'soft' })
  expect(generateCandidate).toHaveBeenLastCalledWith('record', 1, { preset: 'clay', notes: 'soft' }, '', '', [], imageParameters(store), false, store.referenceRoles)
  expect(store.imageStyle.preset).toBe('auto')
})
it('adopts explicitly and creates the current page image', async () => {
  const store = useGeneratorStore()
  const trials = usePageTrials(vi.fn(async () => true), vi.fn())
  await trials.adopt(candidate)
  expect(adoptCandidate).toHaveBeenCalledWith('record', 'candidate', '')
  expect(store.images[0]?.index).toBe(1)
  expect(store.images[0]?.status).toBe('done')
  expect(store.progress.current).toBe(1)
  expect(store.progress.total).toBe(2)
})
it('uses the same recommended automatic style for batch requests as for single-page trials', async () => {
  const store = useGeneratorStore()
  store.imageStyle = { preset: 'auto', notes: '', recommendation: {
    preset: 'high-contrast-promo', reason: '平台适配', alternatives: [],
  } }
  const trials = usePageTrials(vi.fn(async () => true), vi.fn())
  await trials.batch()
  expect(generateCandidate).toHaveBeenCalled()
  for (const call of vi.mocked(generateCandidate).mock.calls) {
    expect(call[2]).toEqual({ preset: 'high-contrast-promo', notes: '' })
  }
  expect(store.imageStyle.preset).toBe('auto')
})
it('generates only remaining pages and leaves adopted ones unchanged', async () => {
  const store = useGeneratorStore()
  store.images = [{ index: 0, url: '/api/images/task/0.png', status: 'done' }]
  const trials = usePageTrials(vi.fn(async () => true), vi.fn())
  await trials.batch()
  expect(generateCandidate).toHaveBeenCalledTimes(1)
  expect(generateCandidate).toHaveBeenCalledWith('record', 1, store.imageStyle, '', '', [], imageParameters(store), false, store.referenceRoles)
  expect(store.images[0]?.url).toBe('/api/images/task/0.png')
})
it('generates a remaining page whose layout is stored as a Chinese display name', async () => {
  const store = useGeneratorStore()
  store.updatePage(1, '单页布局：数据结论\n保留页面事实')
  store.images = [{ index: 0, url: '/api/images/task/0.png', status: 'done' }]
  usePromptCatalogStore().catalog = {
    'image.style': fallbackItems('image.style'),
    'image.layout': [{
      id: 'image.layout.data-conclusion', name: '数据结论', legacyValue: 'data-conclusion',
      builtin: true, description: '', metadata: {},
    }],
  }
  const report = vi.fn()
  await usePageTrials(vi.fn(async () => true), report).batch()
  expect(generateCandidate).toHaveBeenCalledOnce()
  expect(adoptCandidate).toHaveBeenCalledOnce()
  expect(report).toHaveBeenLastCalledWith(null)
  expect(store.outline.pages[1].content).toBe('单页布局：数据结论\n保留页面事实')
  expect(store.images[0].url).toBe('/api/images/task/0.png')
})
it('leaves existing images untouched when generation fails', async () => {
  const store = useGeneratorStore()
  store.images = [{ index: 1, url: '/old.png', status: 'done' }]
  vi.mocked(generateCandidate).mockRejectedValueOnce(new Error('Failed'))
  const report = vi.fn()
  await usePageTrials(vi.fn(async () => true), report).trial(1, candidate.style)
  expect(store.images[0]?.url).toBe('/old.png')
  expect(adoptCandidate).not.toHaveBeenCalled()
  expect(report).toHaveBeenLastCalledWith(expect.objectContaining({ title: expect.any(String) }))
})

it('forwards the cover switch for single trials and adopts the first batch page before the second request', async () => {
  const store = useGeneratorStore()
  store.useCoverAsReference = true
  const trials = usePageTrials(vi.fn(async () => true), vi.fn())
  await trials.trial(1, candidate.style)
  expect(generateCandidate).toHaveBeenLastCalledWith('record', 1, candidate.style, '', '', [], imageParameters(store), true, store.referenceRoles)
  vi.mocked(generateCandidate).mockImplementation(async (_record, index) => {
    if (index === 1) expect(store.images.some(image => image.index === 0 && image.status === 'done')).toBe(true)
    return { ...candidate, id: `version-${index}`, index }
  })
  await trials.batch()
  expect(generateCandidate).toHaveBeenLastCalledWith('record', 1, store.imageStyle, '', '', [], imageParameters(store), true, store.referenceRoles)
})
it('applying style saves the default without generating or adopting', async () => {
  const save = vi.fn(async () => true)
  await usePageTrials(save, vi.fn()).applyStyle(candidate)
  expect(useGeneratorStore().imageStyle.preset).toBe('sketch-note')
  expect(save).toHaveBeenCalled()
  expect(generateCandidate).not.toHaveBeenCalled()
  expect(adoptCandidate).not.toHaveBeenCalled()
})

it('does not start full regeneration when confirmation is cancelled', async () => {
  const confirm = vi.fn(() => false)
  vi.stubGlobal('window', { confirm })
  await usePageTrials(vi.fn(async () => true), vi.fn()).batch(true)
  expect(confirm).toHaveBeenCalled()
  expect(generateCandidate).not.toHaveBeenCalled()
  vi.unstubAllGlobals()
})

it('discards a late generation result after an account change', async () => {
  setToken('synthetic-old')
  let resolve!: (candidate: ImageCandidate) => void
  vi.mocked(generateCandidate).mockImplementationOnce(() => new Promise(done => { resolve = done }))
  const trials = usePageTrials(vi.fn(async () => true), vi.fn())
  const pending = trials.batch()
  await vi.waitFor(() => expect(generateCandidate).toHaveBeenCalledOnce())
  setToken('synthetic-new')
  resolve(candidate)
  await pending
  expect(adoptCandidate).not.toHaveBeenCalled()
  expect(useGeneratorStore().images).toEqual([])
})
