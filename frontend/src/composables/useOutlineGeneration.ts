import { getCurrentScope, onScopeDispose, ref } from 'vue'
import { cancelCurrentGeneration, generateOutline } from '../api'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'

export function useOutlineGeneration() {
  const store = useGeneratorStore()
  const generating = ref(false)
  const cancelling = ref(false)
  const error = ref<AppError | null>(null)
  let controller: AbortController | null = null
  let version = 0
  let previousStatus = store.outlineStatus
  let cancellation: Promise<void> | null = null

  async function start(): Promise<boolean> {
    if (generating.value || cancelling.value) return false
    error.value = null
    if (!store.topic.trim() || !store.outlineModelName.trim()) {
      error.value = normalizeApiError(
        !store.topic.trim() ? '请先输入主题' : '请选择可用的大纲模型', '无法生成大纲',
      )
      return false
    }
    const ownedVersion = ++version
    const requestController = new AbortController()
    controller = requestController
    previousStatus = store.outlineStatus
    generating.value = true
    store.setOutlineStatus('generating')
    try {
      const response = await generateOutline(
        store.topic.trim(), [...store.userImages], requestController.signal,
        store.outlinePromptName, store.referenceContent, store.outlineModelName,
      )
      if (ownedVersion !== version) return false
      if (!response.success) throw response.error || response.error_message || '大纲生成失败'
      if (!response.outline?.trim() || !response.pages?.length) throw new Error('返回的大纲为空，请重试')
      store.setOutline(response.outline, response.pages)
      return true
    } catch (cause) {
      if (ownedVersion !== version) return false
      error.value = normalizeApiError(cause, '大纲生成失败')
      store.setOutlineStatus('error')
      return false
    } finally {
      // A cancelled request must not release ownership of its successor.
      if (ownedVersion === version) {
        generating.value = false
        controller = null
      }
    }
  }

  function cancel(): Promise<void> {
    if (cancellation) return cancellation
    if (!generating.value) return Promise.resolve()
    ++version
    controller?.abort()
    controller = null
    cancelling.value = true
    error.value = null
    cancellation = (async () => {
      try {
        await cancelCurrentGeneration()
      } catch (cause) {
        error.value = normalizeApiError(cause, '取消请求未确认')
      } finally {
        generating.value = false
        cancelling.value = false
        store.setOutlineStatus(previousStatus === 'generating' ? 'idle' : previousStatus)
        cancellation = null
      }
    })()
    return cancellation
  }

  if (getCurrentScope()) onScopeDispose(cancel)
  return { generating, cancelling, error, start, cancel }
}
