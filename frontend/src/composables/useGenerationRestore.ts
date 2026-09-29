import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError } from '../utils/errors'
import { normalizeImageStyle } from '../features/styles/catalog'
import { selectedTitleIndex } from '../utils/publicationContent'
import { restoreCreationInputs } from '../features/creationInputs'
import {
  createHistory,
  getHistory,
  getImageUrl,
  type HistoryDetail
} from '../api'

export function useGenerationRestore() {
  const store = useGeneratorStore()

  function hasGeneratedImages(record: HistoryDetail): boolean {
    return !!record.images?.task_id && (record.images.generated || []).some(Boolean)
  }

  function hydrateFromHistory(record: HistoryDetail) {
    const taskId = record.images.task_id
    const generated = record.images.generated || []
    const pages = record.outline.pages || []
    const doneCount = pages.reduce((count, page, idx) => {
      const filename = generated[page.index] || generated[idx]
      return filename ? count + 1 : count
    }, 0)

    store.setTopic(record.title)
    store.setOutline(record.outline.raw, pages)
    restoreCreationInputs(store, record.outline.creation_inputs)
    store.outline.organization = record.outline.organization
    store.outline.generation_preferences = record.outline.generation_preferences
    store.outline.requested_preferences = record.outline.requested_preferences
    store.outline.copy_preferences = record.outline.copy_preferences
    store.outline.generation_record_id = record.outline.generation_record_id
    store.outline.generation_audit = record.generation_audit
    store.outline.growth_recommendation = record.outline.growth_recommendation
    const requested = record.outline.requested_preferences || record.outline.generation_preferences
    store.outlineAudience = requested?.audience || '自动判断'
    store.outlineAudienceDetail = requested?.audience_detail || ''
    store.outlineTone = requested?.tone || '自动匹配'
    store.outlineOrganization = requested?.organization || record.outline.organization || '自动'
    store.outlinePageCount = requested?.page_count || 'auto'
    store.outlineContentForm = requested?.content_form || 'auto'
    store.outlineInformationDensity = requested?.information_density || 'auto'
    store.outlinePlatform = (record.outline.requested_preferences || record.outline.generation_preferences)?.platform || 'auto'
    store.outlineGoal = (record.outline.requested_preferences || record.outline.generation_preferences)?.goal || 'auto'
    store.setRecordId(record.id)
    store.analysisSnapshots = (record.analysis_snapshots || []).map(snapshot => ({
      ...snapshot,
      parts: [...snapshot.parts],
      content: { ...snapshot.content },
      layout: { ...snapshot.layout },
      visual_style: { ...snapshot.visual_style },
    }))
    store.imageStyle = normalizeImageStyle(record.image_style, record.outline.growth_recommendation)
    // 恢复已生成的文案（标题/文案/标签）
    const c = record.content
    if (c && ((c.titles && c.titles.length) || c.copywriting)) {
      store.setContent(c.titles || [], c.copywriting || '', c.tags || [])
      store.content.diagnostic_record_id = c.diagnostic_record_id
      store.content.selectedTitleIndex = selectedTitleIndex(c.titles || [], c.selected_title_index)
      if (c.source) store.content.source = { ...c.source }
    }
    store.taskId = taskId
    store.images = pages.map((page, idx) => {
      const filename = generated[page.index] || generated[idx] || ''
      return {
        index: page.index,
        url: filename && taskId ? getImageUrl(taskId, filename) : '',
        status: filename ? 'done' : 'error',
        retryable: !filename
      }
    })
    store.progress.total = pages.length
    store.progress.current = doneCount
    store.progress.status = doneCount >= pages.length ? 'done' : 'error'
    store.stage = doneCount >= pages.length ? 'result' : 'generating'
  }

  async function restoreFromHistory(): Promise<boolean> {
    if (!store.recordId) return false

    const res = await getHistory(store.recordId)
    if (!res.success || !res.record) {
      // 记录不存在或无权限（如切换用户后残留的 recordId），清掉以便重新创建
      store.setRecordId(null)
      return false
    }

    if (!hasGeneratedImages(res.record)) return false

    hydrateFromHistory(res.record)
    return true
  }

  async function ensureRecord(): Promise<string> {
    if (store.recordId) return store.recordId

    try {
      const result = await createHistory(store.topic, {
        raw: store.outline.raw,
        pages: store.outline.pages
      }, undefined, store.outline.generation_audit)
      if (!result.success || !result.record_id) {
        throw normalizeApiError(
          result.error || result.error_message || '历史记录未返回 ID',
          '无法创建作品记录'
        )
      }
      store.setRecordId(result.record_id)
      return result.record_id
    } catch (error) {
      throw normalizeApiError(error, '无法创建作品记录')
    }
  }

  return {
    ensureRecord,
    restoreFromHistory
  }
}
