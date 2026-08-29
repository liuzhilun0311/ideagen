import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateImagesPost, cancelCurrentGeneration } from '../api'
import { formatErrorMessage, normalizeApiError, type AppError } from '../utils/errors'
import { useGenerationRestore } from './useGenerationRestore'

/** 判断是否为主动取消（AbortError / CanceledError） */
function isAbortError(err: unknown): boolean {
  const e = err as any
  return !!(
    e?.name === 'AbortError' ||
    e?.name === 'CanceledError' ||
    e?.code === 'ERR_CANCELED' ||
    e?.code === 20   // DOMException AbortError
  )
}

export function useGenerationRunner(
  setError: (error: AppError | null) => void
) {
  const router = useRouter()
  const store = useGeneratorStore()
  const { ensureRecord } = useGenerationRestore()

  // 当前图片生成请求的中断控制器（用于"取消生成"）
  let abortController: AbortController | null = null

  async function startGenerationFlow(force = false) {
    if (store.outline.pages.length === 0) {
      router.push('/')
      return
    }

    await ensureRecord()

    // 发起前取消上一次未结束的请求（避免并发）
    if (abortController) {
      abortController.abort()
      abortController = null
    }

    store.startGeneration()

    abortController = new AbortController()
    const signal = abortController.signal

    generateImagesPost(
      store.outline.pages,
      null,
      store.outline.raw,
      (event) => {
        console.log('Progress:', event)
      },
      (event) => {
        console.log('Complete:', event)
        if (event.image_url) {
          store.updateProgress(event.index, 'done', event.image_url)
        }
      },
      (event) => {
        console.error('Error:', event)
        store.updateProgress(
          event.index,
          'error',
          undefined,
          formatErrorMessage(event.error || event.message || '图片生成失败', '图片生成失败')
        )
      },
      (event) => {
        console.log('Finish:', event)
        store.finishGeneration(event.task_id)
      },
      (err) => {
        // 主动取消不当作错误
        if (isAbortError(err)) {
          console.log('图片生成已取消')
          return
        }
        console.error('Stream Error:', err)
        setError(normalizeApiError(err, '图片生成失败'))
      },
      store.userImages.length > 0 ? store.userImages : undefined,
      store.topic,
      store.recordId,
      force,
      store.imagePromptName,
      signal,
      store.imageModelName
    )
  }

  /**
   * 取消当前图片生成
   */
  function cancelGenerationFlow() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    // 通知后端真正取消（停止调度、作废未完成结果）
    cancelCurrentGeneration().catch(() => {})
    // 把仍处于生成中的图片标记为"已取消"，并把进度复位
    store.images.forEach((img) => {
      if (img.status === 'generating' || img.status === 'retrying') {
        img.status = 'error'
        img.error = '已取消'
        img.retryable = true
      }
    })
    store.progress = { current: 0, total: 0, status: 'idle' }
  }

  return {
    startGenerationFlow,
    cancelGenerationFlow
  }
}
