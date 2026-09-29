import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { effectScope } from 'vue'
import { useStructureRevision } from '../../src/composables/useStructureRevision'
import { useGeneratorStore } from '../../src/stores/generator'
import { generateOutline } from '../../src/api/outline'
import { contentStructureLabel } from '../../src/features/contentStructure'
vi.mock('../../src/api/outline', () => ({ generateOutline: vi.fn() }))
let scope = effectScope()
const response = { success: true, outline: 'New content', organization: '问题解决',
  pages: [{ index: 0, type: 'cover' as const, content: 'New content' }] }
beforeEach(() => {
  setActivePinia(createPinia())
  scope = effectScope()
  vi.mocked(generateOutline).mockReset().mockResolvedValue(response)
  const store = useGeneratorStore()
  store.topic = 'Topic'
  store.setOutline('Original', [{ index: 0, type: 'cover', content: 'Original' }])
  store.recordId = 'original'
  store.outlineModelName = 'model'
  store.images = [{ index: 0, status: 'done', url: '/original.png' }]
  store.content.copywriting = 'Original copy'
})
afterEach(() => scope.stop())
function setup(save = vi.fn(async () => true)) {
  return { action: scope.run(() => useStructureRevision(save))!, save, store: useGeneratorStore() }
}
it('previews without modifying the draft and sends original material and fixed page count', async () => {
  const { action, store } = setup()
  const before = JSON.stringify(store.$state)
  await action.generate('问题解决')
  expect(action.preview.value).toEqual(response)
  expect(JSON.stringify(store.$state)).toBe(before)
  const call = vi.mocked(generateOutline).mock.calls[0]!
  expect(call[4]).toContain('Original')
  expect(call[7]).toMatchObject({ organization: '问题解决', page_count: 1 })
})
it('saves original assets before creating a new draft', async () => {
  const { action, store, save } = setup()
  await action.generate('问题解决')
  expect(await action.adopt()).toBe(true)
  expect(save).toHaveBeenCalledOnce()
  expect(store.recordId).toBeNull()
  expect(store.outline.raw).toBe('New content')
  expect(store.outline.generation_preferences?.organization).toBe('问题解决')
  expect(store.images).toEqual([])
  expect(store.content.copywriting).toBe('')
})
it('keeps all original data when saving the original fails', async () => {
  const { action, store } = setup(vi.fn(async () => false))
  await action.generate('问题解决')
  const before = JSON.stringify(store.$state)
  expect(await action.adopt()).toBe(false)
  expect(JSON.stringify(store.$state)).toBe(before)
  expect(action.error.value).toContain('保存失败')
})
it('rejects adopting a stale preview', async () => {
  const { action, store, save } = setup()
  await action.generate('问题解决')
  store.updatePage(0, 'Manually changed')
  expect(await action.adopt()).toBe(false)
  expect(save).not.toHaveBeenCalled()
  expect(store.outline.raw).toBe('Manually changed')
})
it('ignores results after cancellation', async () => {
  let resolve!: (value: typeof response) => void
  vi.mocked(generateOutline).mockReturnValue(new Promise(done => { resolve = done }))
  const { action } = setup()
  const pending = action.generate('问题解决')
  action.cancel()
  resolve(response)
  await pending
  expect(action.preview.value).toBeNull()
  expect(action.loading.value).toBe(false)
})
it('rejects wrong page counts and keeps the original', async () => {
  vi.mocked(generateOutline).mockResolvedValue({ ...response, pages: [...response.pages, { ...response.pages[0]!, index: 1 }] })
  const { action, store } = setup()
  await action.generate('问题解决')
  expect(action.preview.value).toBeNull()
  expect(action.error.value).toContain('页数')
  expect(store.outline.raw).toBe('Original')
})
it('renders old internal structure identifiers in Chinese', () => {
  expect(contentStructureLabel('hook_problem_value_follow')).toBe('吸引注意 → 提出问题 → 提供价值 → 引导关注')
  expect(contentStructureLabel('自定义中文顺序')).toBe('自定义中文顺序')
})
