import { computed, ref, watch } from 'vue'
import axios from 'axios'
import { generateContent, cancelCurrentGeneration } from '../api'
import { useGeneratorStore } from '../stores/generator'
import { useCreationOptions } from './useCreationOptions'
import { useOutlineGeneration } from './useOutlineGeneration'
import { useGenerationRunner } from './useGenerationRunner'
import { useImageRetry } from './useImageRetry'
import { useDraftSave } from './useDraftSave'
import { normalizeApiError, type AppError } from '../utils/errors'
import { useStudioSession } from '../stores/studioSession'
import { contentSource } from '../utils/contentSource'
import { copyPreferences, resolveCopyPreferences } from '../features/copyOptions'

export function useStudio() {
  const store = useGeneratorStore()
  const session = useStudioSession()
  const options = useCreationOptions()
  const outline = useOutlineGeneration()
  const saver = useDraftSave()
  const error = ref<AppError | null>(null)
  const report = (next: AppError | null) => { error.value = next }
  const images = useGenerationRunner(report)
  const retry = useImageRetry(report)
  const phase = ref<'outline' | 'images' | 'content' | 'retry' | null>(null)
  const cancelling = ref(false)
  const busy = computed(() => phase.value !== null || saver.saving.value || cancelling.value)
  const editingLocked = computed(() => phase.value !== null || cancelling.value)
  let epoch = 0
  let contentController: AbortController | null = null

  watch(busy, value => { session.workspaceBusy = value }, { immediate: true, flush: 'sync' })
  watch(() => session.revision, () => {
    saver.resetBaseline()
    error.value = null
    session.dirty = saver.dirty.value && !!store.outline.pages.length
  })
  watch(() => saver.dirty.value && !!store.outline.pages.length, value => {
    session.dirty = value
  }, { immediate: true, flush: 'sync' })

  async function save() {
    const success = await saver.save()
    if (!success) report(saver.error.value)
    return success
  }

  async function run(kind: 'outline' | 'images' | 'content') {
    if (busy.value || session.homeBusy) return
    if (kind === 'outline' && store.images.length) return
    const models = kind === 'images' ? options.imageModels.value : options.textModels.value
    if (!models.length) {
      report(normalizeApiError('请先配置可用模型', '没有可用模型'))
      return
    }
    if (kind === 'images' && store.images.some(image => image.status === 'done')
      && !window.confirm('重新生成全部图片会替换当前图片，是否继续？')) return
    if (kind === 'outline' && store.outline.pages.length
      && !window.confirm('重新生成大纲会替换当前大纲及手动修改，是否继续？')) return
    if (kind === 'content' && (store.content.copywriting || store.content.titles.length || store.content.tags.length)
      && !window.confirm('重新生成文案成功后会替换当前文案及手动修改，是否继续？')) return
    const operation = ++epoch
    const input = {
      topic: store.topic,
      raw: contentSource(store.topic, store.outline.pages).outline,
      pages: store.outline.pages.map(page => ({ ...page })),
      userImages: [...store.userImages],
      referenceRoles: [...store.referenceRoles],
      imagePromptName: store.imagePromptName,
      imageModelName: store.imageModelName,
      imageStyle: { ...store.imageStyle },
      useCoverAsReference: store.useCoverAsReference,
      imageResolution: store.imageResolution,
      imageAspectRatio: store.imageAspectRatio,
      imageQuality: store.imageQuality,
      imageOutputFormat: store.imageOutputFormat,
      contentPromptName: store.contentPromptName,
      contentModelName: store.contentModelName,
      copyPreferences: copyPreferences(store.outline.copy_preferences),
      generationPreferences: store.outline.generation_preferences ? { ...store.outline.generation_preferences } : undefined,
    }
    phase.value = kind
    error.value = null
    session.notice = ''
    try {
      if (kind === 'outline') {
        const previousContent = {
          ...store.content, titles: [...store.content.titles], tags: [...store.content.tags],
          ...(store.content.source ? { source: { ...store.content.source } } : {}),
        }
        if (!await outline.start()) report(outline.error.value)
        else {
          store.content = previousContent
          session.notice = '大纲已更新'
        }
        return
      }
      if (!await save() || epoch !== operation) return
      if (kind === 'images') {
        await images.startGenerationFlow(true, input)
        if (operation === epoch) session.notice = error.value ? '图片生成已结束，请返回创作查看详情' : '图片生成已结束'
        return
      }
      const controller = new AbortController()
      contentController = controller
      store.startContentGeneration()
      const result = await generateContent(
        input.topic, input.raw, '', controller.signal, input.contentModelName,
        input.generationPreferences, resolveCopyPreferences(input.copyPreferences),
      )
      if (controller.signal.aborted || operation !== epoch) return
      store.content.diagnostic_record_id = result.generation_record?.id
      if (!result.success || !Array.isArray(result.titles) || typeof result.copywriting !== 'string') {
        throw result.error || result.error_message || '生成文案失败'
      }
      store.setContent(result.titles, result.copywriting, result.tags || [])
      store.content.source = { topic: input.topic.trim(), outline: input.raw }
      session.notice = result.validation?.warnings?.length
        ? `文案已生成。${result.validation.warnings.join(' ')}` : '文案已生成'
    } catch (cause) {
      if (operation !== epoch) return
      if (kind === 'content' && axios.isAxiosError(cause)) {
        const id = cause.response?.data?.generation_record?.id
        if (typeof id === 'string') store.content.diagnostic_record_id = id
      }
      const failure = normalizeApiError(cause, '生成失败')
      report(failure)
      session.notice = failure.title
      if (kind === 'content') store.setContentError(failure.detail)
    } finally {
      if (epoch === operation) {
        contentController = null
        phase.value = null
      }
    }
  }

  async function cancel() {
    if (!phase.value || cancelling.value || phase.value === 'retry') return
    const kind = phase.value
    ++epoch
    cancelling.value = true
    try {
      if (kind === 'images') await images.cancelGenerationFlow()
      else if (kind === 'outline') await outline.cancel()
      else {
        contentController?.abort()
        contentController = null
        store.content.status = store.content.copywriting || store.content.titles.length ? 'done' : 'idle'
        await cancelCurrentGeneration()
      }
    } catch (cause) {
      report(normalizeApiError(cause, '远端取消未确认'))
    } finally {
      phase.value = null
      cancelling.value = false
    }
  }

  async function retryPage(index: number) {
    if (busy.value || session.homeBusy || !store.taskId) return
    phase.value = 'retry'
    try {
      await retry.retrySingleImage(index)
    } finally {
      phase.value = null
    }
  }

  return { store, options, saver, error, phase, cancelling, busy, editingLocked, run, cancel, save, retryPage }
}
