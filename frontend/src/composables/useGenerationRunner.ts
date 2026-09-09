import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateImagesPost, cancelCurrentGeneration } from '../api'
import { formatErrorMessage, normalizeApiError, type AppError } from '../utils/errors'
import { useGenerationRestore } from './useGenerationRestore'
import type { Page } from '../api'

export interface ImageGenerationInput {
  topic: string
  raw: string
  pages: Page[]
  userImages: File[]
  imagePromptName: string
  imageModelName: string
}

export function useGenerationRunner(
  setError: (error: AppError | null) => void
) {
  const router = useRouter()
  const store = useGeneratorStore()
  const { ensureRecord } = useGenerationRestore()

  let active: { controller: AbortController; started: boolean; finished: boolean } | null = null
  let cancelPending = false

  async function startGenerationFlow(force = false, snapshot?: ImageGenerationInput): Promise<void> {
    if (active || cancelPending) return
    if (store.outline.pages.length === 0) {
      await router.push('/')
      return
    }
    const input = snapshot || {
      topic: store.topic, raw: store.outline.raw,
      pages: store.outline.pages.map(page => ({ ...page })),
      userImages: [...store.userImages],
      imagePromptName: store.imagePromptName, imageModelName: store.imageModelName,
    }

    // Claim ownership before saving; terminal events release it even if EOF stalls.
    const run = { controller: new AbortController(), started: false, finished: false }
    active = run
    const acceptsEvents = () => active === run && !run.controller.signal.aborted && !run.finished
    const settle = () => {
      run.finished = true
      if (active === run) active = null
      run.controller.abort()
    }
    const fail = (error: unknown, title: string) => {
      if (!acceptsEvents()) return
      run.finished = true
      try {
        if (run.started) store.stopGeneration('连接中断，请重试未完成图片')
        setError(normalizeApiError(error, title))
      } finally {
        settle()
      }
    }
    // The shared SSE parser swallows handler exceptions, so settle them here.
    const consume = (handler: () => void) => {
      if (!acceptsEvents()) return
      try {
        handler()
      } catch (error) {
        fail(error, '图片生成中断')
      }
    }

    try {
      setError(null)
      const recordId = await ensureRecord()
      if (!acceptsEvents()) return
      store.startGeneration()
      run.started = true
      await generateImagesPost(
        input.pages,
        null,
        input.raw,
        () => {},
        event => consume(() => {
          if (event.image_url) {
            store.updateProgress(event.index, 'done', event.image_url)
          }
        }),
        event => consume(() => {
          store.updateProgress(
            event.index,
            'error',
            undefined,
            formatErrorMessage(event.error || event.message || '图片生成失败', '图片生成失败'),
          )
        }),
        event => consume(() => {
          store.finishGeneration(event.task_id)
          settle()
        }),
        error => fail(error, '图片生成失败'),
        input.userImages.length > 0 ? input.userImages : undefined,
        input.topic,
        recordId,
        force,
        input.imagePromptName,
        run.controller.signal,
        input.imageModelName,
      )
      fail('连接中断，未收到完成确认', '图片生成中断')
    } catch (error) {
      fail(error, run.started ? '图片生成中断' : '无法开始生成')
    } finally {
      // An older cancelled request must not release a newer request's ownership.
      if (active === run) active = null
    }
  }

  function cancelGenerationFlow(): Promise<void> {
    if (!active || active.finished) return Promise.resolve()
    const run = active
    active = null
    cancelPending = true
    run.controller.abort()
    if (run.started) store.stopGeneration('本地已取消，未完成图片可重试')
    // This user-wide endpoint is best effort, not confirmation of a remote stop.
    return cancelCurrentGeneration()
      .catch(error => setError(normalizeApiError(error, '远端取消未确认')))
      .finally(() => { cancelPending = false })
  }

  return {
    startGenerationFlow,
    cancelGenerationFlow
  }
}
