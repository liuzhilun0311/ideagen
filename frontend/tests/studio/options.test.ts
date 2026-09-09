import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../src/api', () => ({ getConfig: vi.fn(), getPrompts: vi.fn() }))
import { getConfig, getPrompts, type Config, type PromptItem } from '../../src/api'
import { useGeneratorStore } from '../../src/stores/generator'
import { useCreationOptions } from '../../src/composables/useCreationOptions'

const config: Config = {
  text_generation: {
    active_provider: 'active',
    providers: { disabled: { enabled: false }, first: { model: 'Writer' }, active: { enabled: true, model: 'Editor' } },
  },
  image_generation: { active_provider: 'missing', providers: { photo: { model: 'Image' } } },
}
const custom: PromptItem = { name: 'custom', type: 'outline', content: 'Draft', is_base: false }
beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(getConfig).mockReset().mockResolvedValue({ success: true, config })
  vi.mocked(getPrompts).mockReset().mockResolvedValue({
    success: true, prompts: { outline: [custom], image: [], content: [] },
  })
})

it('filters disabled models and falls back to active then first enabled provider', async () => {
  const store = useGeneratorStore()
  store.outlineModelName = 'disabled'
  store.contentModelName = 'deleted'
  store.imageModelName = 'deleted'
  store.outlinePromptName = 'deleted'
  const options = useCreationOptions()
  await options.load()
  expect(options.textModels.value.map(m => m.name)).toEqual(['first', 'active'])
  expect(options.textModels.value.every(m => !!m.label)).toBe(true)
  expect(store.outlineModelName).toBe('active')
  expect(store.contentModelName).toBe('active')
  expect(store.imageModelName).toBe('photo')
  expect(store.outlinePromptName).toBe('')
  expect(options.prompts.value.outline).toEqual([custom])
  expect(options.loading.value).toBe(false)
  expect(options.error.value).toBeNull()
})

it('keeps valid saved choices and default prompts', async () => {
  const store = useGeneratorStore()
  store.outlineModelName = 'first'
  store.outlinePromptName = 'custom'
  await useCreationOptions().load()
  expect(store.outlineModelName).toBe('first')
  expect(store.outlinePromptName).toBe('custom')
  expect(store.contentPromptName).toBe('')
})

it('clears invalid choices when no enabled models exist', async () => {
  vi.mocked(getConfig).mockResolvedValue({
    success: true, config: {
      text_generation: { active_provider: 'off', providers: { off: { enabled: false } } },
      image_generation: { active_provider: '', providers: {} },
    },
  })
  const store = useGeneratorStore()
  store.outlineModelName = 'old'
  const options = useCreationOptions()
  await options.load()
  expect(options.textModels.value).toEqual([])
  expect(options.imageModels.value).toEqual([])
  expect(store.outlineModelName).toBe('')
})

it('coalesces concurrent loads and permits a later refresh', async () => {
  const options = useCreationOptions()
  const first = options.load()
  const second = options.load()
  expect(options.loading.value).toBe(true)
  await Promise.all([first, second])
  expect(getConfig).toHaveBeenCalledOnce()
  expect(getPrompts).toHaveBeenCalledOnce()
  await options.load()
  expect(getConfig).toHaveBeenCalledTimes(2)
})

it.each(['config', 'prompts', 'network'])('reports %s failure without resetting saved selections and allows retry', async source => {
  if (source === 'config') vi.mocked(getConfig).mockResolvedValueOnce({ success: false, error_message: 'Failed' })
  if (source === 'prompts') vi.mocked(getPrompts).mockResolvedValueOnce({ success: false, prompts: { outline: [], image: [], content: [] } })
  if (source === 'network') vi.mocked(getConfig).mockRejectedValueOnce(new Error('Offline'))
  const store = useGeneratorStore()
  store.outlineModelName = 'saved'
  const options = useCreationOptions()
  await options.load()
  expect(options.error.value).not.toBeNull()
  expect(options.loading.value).toBe(false)
  expect(store.outlineModelName).toBe('saved')
  await options.load()
  expect(options.error.value).toBeNull()
})
