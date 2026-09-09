import { ref } from 'vue'
import { getConfig, getPrompts, type Config, type PromptItem } from '../api'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'

export interface ModelOption { name: string; label: string }

function enabledModels(section: Config['text_generation']): ModelOption[] {
  return Object.entries(section.providers)
    .filter(([, provider]) => provider && provider.enabled !== false)
    .map(([name, provider]) => ({
      name,
      label: provider.display_name || (provider.model ? `${name} · ${provider.model}` : name),
    }))
}

export function useCreationOptions() {
  const store = useGeneratorStore()
  const loading = ref(false)
  const error = ref<AppError | null>(null)
  const textModels = ref<ModelOption[]>([])
  const imageModels = ref<ModelOption[]>([])
  const prompts = ref<{ outline: PromptItem[]; image: PromptItem[]; content: PromptItem[] }>({
    outline: [], image: [], content: [],
  })
  let pending: Promise<void> | null = null

  function load(): Promise<void> {
    if (pending) return pending
    loading.value = true
    error.value = null
    pending = (async () => {
      try {
        const [configuration, promptResponse] = await Promise.all([getConfig(), getPrompts()])
        if (!configuration.success || !configuration.config) {
          throw configuration.error || configuration.error_message || '无法加载模型配置'
        }
        if (!promptResponse.success) throw new Error('无法加载提示词')
        const config = configuration.config
        const text = enabledModels(config.text_generation)
        const image = enabledModels(config.image_generation)
        const nextPrompts = promptResponse.prompts
        const select = (current: string, models: ModelOption[], active: string) =>
          models.some(m => m.name === current) ? current
            : models.find(m => m.name === active)?.name || models[0]?.name || ''

        textModels.value = text
        imageModels.value = image
        prompts.value = nextPrompts
        store.outlineModelName = select(store.outlineModelName, text, config.text_generation.active_provider)
        store.contentModelName = select(store.contentModelName, text, config.text_generation.active_provider)
        store.imageModelName = select(store.imageModelName, image, config.image_generation.active_provider)
        for (const kind of ['outline', 'image', 'content'] as const) {
          const key = `${kind}PromptName` as const
          if (store[key] && !nextPrompts[kind].some(p => p.name === store[key])) store[key] = ''
        }
      } catch (cause) {
        error.value = normalizeApiError(cause, '创作选项加载失败')
      } finally {
        loading.value = false
        pending = null
      }
    })()
    return pending
  }

  return { loading, error, textModels, imageModels, prompts, load }
}
