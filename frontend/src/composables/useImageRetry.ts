import { ref } from 'vue'
import { useGeneratorStore } from '../stores/generator'
import { contentSource } from '../utils/contentSource'
import { imageParameters, readLayout } from '../features/generationOptions'
import { resolveImageStyle, imageStyleChanged } from '../features/styles/catalog'
import { resolvePromptValue } from '../features/promptCatalog'
import { normalizeApiError } from '../utils/errors'
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
    let imageStyle
    try {
      imageStyle = resolveImageStyle(store.imageStyle)
      resolvePromptValue('image', 'layout', readLayout(page.content))
    } catch (cause) {
      _setError(normalizeApiError(cause, '提示词选项不可用'))
      return
    }
    if (imageStyleChanged(store.imageStyle)) {
      _setError({
        type: '', code: 'STYLE_CHANGED', title: '图片风格已变化',
        detail: '请先按新风格重新生成整套图片，再进行单页重绘。',
        suggestion: '使用“生成全部图片”统一画风，现有图片不会自动覆盖。',
        status: 409, retryable: false,
      })
      return
    }

    regeneratingIndices.value.add(index)
    store.setImageRetrying(index)

    const context = {
      fullOutline: contentSource(store.topic, store.outline.pages).outline,
      userTopic: store.topic || '',
      recordId: store.recordId,
      imageStyle,
      referenceRoles: [...store.referenceRoles],
      userImages: [...store.userImages],
    }

    return apiRegenerateImage(store.taskId, page, store.useCoverAsReference, context, store.imagePromptName, store.imageModelName, imageParameters(store))
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
