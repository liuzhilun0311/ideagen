import { computed, ref } from 'vue'
import { useGeneratorStore } from '../stores/generator'
import { createHistory, updateHistory } from '../api/history'
import { normalizeApiError, type AppError } from '../utils/errors'
import { useStudioSession } from '../stores/studioSession'
import { creationInputs, encodeReferences } from '../features/creationInputs'

const confirmedSnapshots = new WeakMap<object, { recordId: string; payload: string }>()

export function useDraftSave() {
  const store = useGeneratorStore()
  const session = useStudioSession()
  const saving = ref(false)
  const error = ref<AppError | null>(null)
  const snapshot = () => ({
    image_style: { ...store.imageStyle, ...(store.imageStyle.applied ? { applied: { ...store.imageStyle.applied } } : {}) },
    title: store.topic,
    outline: { raw: store.outline.raw, organization: store.outline.organization,
      creation_inputs: creationInputs(store),
      requested_preferences: store.outline.requested_preferences,
      growth_recommendation: store.outline.growth_recommendation,
      copy_preferences: store.outline.copy_preferences,
      generation_preferences: store.outline.generation_preferences, generation_record_id: store.outline.generation_record_id,
      pages: store.outline.pages.map(page => ({ ...page })) },
    content: {
      diagnostic_record_id: store.content.diagnostic_record_id,
      ...(store.content.source ? { source: { ...store.content.source } } : {}),
      titles: [...store.content.titles],
      selected_title_index: store.content.selectedTitleIndex,
      copywriting: store.content.copywriting,
      tags: [...store.content.tags],
    },
    analysis_snapshots: store.analysisSnapshots.map(snapshot => ({
      ...snapshot,
      parts: [...snapshot.parts],
      content: { ...snapshot.content },
      layout: { ...snapshot.layout },
      visual_style: { ...snapshot.visual_style },
    })),
  })
  const confirmed = confirmedSnapshots.get(store)
  // A record ID alone does not prove that the current local draft reached the server.
  const saved = ref<string | null>(confirmed?.recordId === store.recordId ? confirmed.payload : null)
  const dirty = computed(() => JSON.stringify(snapshot()) !== saved.value)
  let pending: Promise<boolean> | null = null

  function save(): Promise<boolean> {
    if (pending) return pending
    const revision = session.revision
    const payload = snapshot()
    const references = [...store.userImages]
    let recordId = store.recordId
    saving.value = true
    error.value = null
    pending = (async () => {
      try {
        if (session.referenceLoading || (store.referenceImageKey && !references.length)) {
          throw new Error('参考图片尚未恢复，请先完成恢复或重新添加图片后保存。')
        }
        if (!payload.title.trim() || !payload.outline.pages.length) {
          throw new Error('请先填写主题并生成大纲')
        }
        if (references.length) payload.outline.creation_inputs.reference_images = await encodeReferences(references)
        if (session.revision !== revision || store.recordId !== recordId) return false
        if (!recordId) {
          const created = await createHistory(payload.title, payload.outline, store.taskId || undefined)
          if (!created.success || !created.record_id) {
            throw created.error || created.error_message || '创建作品记录失败'
          }
          recordId = created.record_id
          if (session.revision !== revision) return false
          store.setRecordId(recordId)
        }
        const updated = await updateHistory(recordId, payload)
        if (!updated.success) throw updated.error || updated.error_message || '保存失败'
        if (session.revision !== revision || store.recordId !== recordId) return false
        // Only the sent snapshot is saved; later edits must remain dirty.
        saved.value = JSON.stringify(payload)
        confirmedSnapshots.set(store, { recordId, payload: saved.value })
        store.markSaved()
        return true
      } catch (cause) {
        error.value = normalizeApiError(cause, '无法保存作品')
        return false
      } finally {
        saving.value = false
      }
    })().finally(() => { pending = null })
    return pending
  }

  function resetBaseline() {
    saved.value = null
    error.value = null
  }

  return { saving, error, dirty, save, resetBaseline }
}
