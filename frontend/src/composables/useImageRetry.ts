import { ref } from 'vue'
import { useGeneratorStore } from '../stores/generator'
import {
  regenerateImage as apiRegenerateImage
} from '../api'
import {
  formatErrorMessage,
  type AppError
} from '../utils/errors'


export function useImageRetry(_setError: (error: AppError | null) => void) {
  const store = useGeneratorStore()
  const regeneratingIndices = ref(new Set<number>())


  function finishIfAllImagesDone() {
    if (store.taskId && store.images.length > 0 && store.images.every(img => img.status === 'done')) {
      store.finishGeneration(store.taskId)
    }
  }


  function retrySingleImage(index: number) {
    if (!store.taskId || regeneratingIndices.value.has(index)) return

    const page = store.outline.pages.find(p => p.index === index)
    if (!page) return

    regeneratingIndices.value.add(index)
    store.setImageRetrying(index)

    const context = {
      fullOutline: store.outline.raw || '',
      userTopic: store.topic || '',
      recordId: store.recordId
    }

    return apiRegenerateImage(store.taskId, page, true, context, store.imagePromptName, store.imageModelName)
      .then(result => {
        if (result.success && result.image_url) {
          store.updateImage(index, result.image_url)
          finishIfAllImagesDone()
        } else {
          store.updateProgress(
            index,
            'error',
            undefined,
            formatErrorMessage(result.error || result.error_message || '重绘失败', '重绘失败')
          )
        }
      })
      .catch(e => {
        store.updateProgress(index, 'error', undefined, formatErrorMessage(e, '重绘失败'))
      })
      .finally(() => {
        regeneratingIndices.value.delete(index)
      })
  }


  function regenerateImage(index: number) {
    retrySingleImage(index)
  }


  return {
    regenerateImage,
    retrySingleImage
  }
}
