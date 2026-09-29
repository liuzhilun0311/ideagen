import { getCurrentScope, onScopeDispose, ref } from 'vue'
import axios from 'axios'
import { cancelCurrentGeneration, generateOutline } from '../api'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
import { normalizeImageStyle } from '../features/styles/catalog'
import { readLayout, withLayout } from '../features/generationOptions'
import { findItem, promptItems } from '../features/promptCatalog'
import { recommendCopyPreferences } from '../features/copyOptions'
import { outlineRequest } from '../features/outlineRequest'
import { useStudioSession } from '../stores/studioSession'
import { getToken } from '../api/token'
import { palettes } from '../features/styles/palette'

export function useOutlineGeneration(options: { home?: boolean } = {}) {
  const store = useGeneratorStore()
  const session = useStudioSession()
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
    const revision = session.revision
    const token = getToken()
    const ownsDraft = () => ownedVersion === version && revision === session.revision && token === getToken()
    const requestController = new AbortController()
    controller = requestController
    previousStatus = store.outlineStatus
    generating.value = true
    store.setOutlineStatus('generating')
    try {
      const input = outlineRequest(store, options.home)
      const preferences = input.preferences
      const previousCopy = store.outline.copy_preferences ? { ...store.outline.copy_preferences } : undefined
      const requestPreferences: Partial<typeof preferences> = { ...preferences }
      if (requestPreferences.platform === 'auto') delete requestPreferences.platform
      if (requestPreferences.goal === 'auto') delete requestPreferences.goal
      const response = await generateOutline(
        input.topic, input.images, requestController.signal,
        '', input.reference_content, input.provider,
        preferences.organization,
        requestPreferences,
        input.reference_roles,
      )
      if (!ownsDraft()) return false
      if (response.generation_record?.id) {
        store.outline.diagnostic_record_id = response.generation_record.id
      }
      if (!response.success) throw response.error || response.error_message || '大纲生成失败'
      if (!response.outline?.trim() || !response.pages?.length) throw new Error('返回的大纲为空，请重试')
      const requestedPageCount = preferences.page_count
      if (requestedPageCount !== 'auto' && response.pages.length !== requestedPageCount) {
        throw new Error('模型未按指定页数生成，请重试')
      }
      const pages = response.pages.map(page => ({ ...page }))
      const generationPreferences = { ...(response.generation_preferences || preferences) }
      if (response.organization && response.organization !== '自动'
        && findItem(promptItems('outline', 'organization'), response.organization)) {
        generationPreferences.organization = response.organization
      }
      const imageStyle = normalizeImageStyle(
        { ...store.imageStyle, recommendation: response.style_recommendation },
        response.growth_recommendation,
      )
      // Initialize a new outline once; restoring a draft keeps later manual edits.
      if (imageStyle.recommendation) imageStyle.preset = imageStyle.recommendation.preset
      const growth = response.growth_recommendation
      if (growth?.layout) {
        for (const page of pages) {
          if ((!page.layout || page.layout === '自动') && readLayout(page.content) === '自动') {
            page.layout = growth.layout
            page.content = withLayout(page.content, growth.layout)
          }
        }
      }
      const recommendation = response.generation_recommendation || {}
      if (imageStyle.palette) {
        delete imageStyle.palette.recommendation
        delete imageStyle.palette.reason
      }
      if (palettes.some(item => item.id === recommendation.palette)) {
        imageStyle.palette = { ...imageStyle.palette, mode: imageStyle.palette?.mode || 'auto',
          recommendation: recommendation.palette, reason: recommendation.palette_reason || '' }
      }
      const nextCopy = recommendCopyPreferences(previousCopy, recommendation)
      // Commit only validated results; failed/cancelled requests leave the previous work intact.
      store.setOutline(response.outline, pages)
      store.outline.organization = response.organization || preferences.organization
      store.outline.generation_preferences = generationPreferences
      store.outline.requested_preferences = { ...preferences }
      store.outline.generation_record_id = response.generation_record?.id
      store.outline.diagnostic_record_id = response.generation_record?.id
      store.outline.generation_audit = response.generation_audit
      store.outline.growth_recommendation = growth
      store.outline.copy_preferences = nextCopy
      store.imageStyle = imageStyle
      if (growth?.aspect_ratio) store.imageAspectRatio = growth.aspect_ratio
      if (growth?.layout) store.syncRawFromPages()
      if (options.home) {
        store.recordId = null
        store.lastSavedAt = null
        store.analysisSnapshots = []
        store.setEntrySource('home')
        store.outlineOrganization = preferences.organization
        store.outlineTone = preferences.tone
        session.revision++
        session.workspacePath = '/workspace'
        session.dirty = true
      }
      store.saveToStorage()
      return true
    } catch (cause) {
      if (!ownsDraft()) return false
      const recordId = axios.isAxiosError(cause) ? cause.response?.data?.generation_record?.id : undefined
      if (typeof recordId === 'string') store.outline.diagnostic_record_id = recordId
      error.value = normalizeApiError(cause, '大纲生成失败')
      store.setOutlineStatus('error')
      store.saveToStorage()
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
        store.saveToStorage()
        cancellation = null
      }
    })()
    return cancellation
  }

  if (getCurrentScope()) onScopeDispose(cancel)
  return { generating, cancelling, error, start, cancel }
}
