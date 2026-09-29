import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateImagesPost, cancelCurrentGeneration } from '../api'
import { normalizeApiError, type AppError } from '../utils/errors'
import { useGenerationRestore } from './useGenerationRestore'
import type { Page } from '../api'
import { contentSource } from '../utils/contentSource'
import { styleChoice, resolveImageStyle, type ImageStyle } from '../features/styles/catalog'
import { readLayout } from '../features/generationOptions'
import { resolvePromptValue } from '../features/promptCatalog'

export interface ImageGenerationInput {
  topic: string
  raw: string
  pages: Page[]
  userImages: File[]
  referenceRoles?: string[]
  imagePromptName: string
  imageModelName: string
  imageStyle?: ImageStyle
  useCoverAsReference: boolean
  imageResolution: string
  imageAspectRatio: string
  imageQuality: string
  imageOutputFormat: string
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
      topic: store.topic, raw: contentSource(store.topic, store.outline.pages).outline,
      pages: store.outline.pages.map(page => ({ ...page })),
      userImages: [...store.userImages],
        referenceRoles: [...store.referenceRoles],
      imagePromptName: store.imagePromptName, imageModelName: store.imageModelName,
      imageStyle: { ...store.imageStyle },
      useCoverAsReference: store.useCoverAsReference,
      imageResolution: store.imageResolution, imageAspectRatio: store.imageAspectRatio,
      imageQuality: store.imageQuality, imageOutputFormat: store.imageOutputFormat,
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
      input.imageStyle = resolveImageStyle(input.imageStyle || store.imageStyle)
      for (const page of input.pages) resolvePromptValue('image', 'layout', readLayout(page.content))
      const recordId = await ensureRecord()
      if (!acceptsEvents()) return
      store.startGeneration()
      store.imageStyle.applied = styleChoice(input.imageStyle || store.imageStyle)
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
          const pageError = normalizeApiError(event.error || event.message || '图片生成失败', '图片生成失败')
          store.updateProgress(
            event.index,
            'error',
            undefined,
            `${pageError.title}：${pageError.detail}`,
          )
          setError(pageError)
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
        input.imageStyle,
        input.useCoverAsReference,
        { resolution: input.imageResolution, aspect_ratio: input.imageAspectRatio,
          quality: input.imageQuality, output_format: input.imageOutputFormat },
        input.referenceRoles,
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
