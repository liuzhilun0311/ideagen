import { computed, ref } from 'vue'
import { useGeneratorStore } from '../stores/generator'
import { createHistory, updateHistory } from '../api/history'
import { normalizeApiError, type AppError } from '../utils/errors'

const confirmedSnapshots = new WeakMap<object, { recordId: string; payload: string }>()

export function useDraftSave() {
  const store = useGeneratorStore()
  const saving = ref(false)
  const error = ref<AppError | null>(null)
  const snapshot = () => ({
    title: store.topic,
    outline: { raw: store.outline.raw, pages: store.outline.pages.map(page => ({ ...page })) },
    content: {
      titles: [...store.content.titles],
      copywriting: store.content.copywriting,
      tags: [...store.content.tags],
    },
  })
  const confirmed = confirmedSnapshots.get(store)
  // A record ID alone does not prove that the current local draft reached the server.
  const saved = ref<string | null>(confirmed?.recordId === store.recordId ? confirmed.payload : null)
  const dirty = computed(() => JSON.stringify(snapshot()) !== saved.value)
  let pending: Promise<boolean> | null = null

  function save(): Promise<boolean> {
    if (pending) return pending
    const payload = snapshot()
    saving.value = true
    error.value = null
    pending = (async () => {
      try {
        if (!payload.title.trim() || !payload.outline.pages.length) {
          throw new Error('请先填写主题并生成大纲')
        }
        let recordId = store.recordId
        if (!recordId) {
          const created = await createHistory(payload.title, payload.outline, store.taskId || undefined)
          if (!created.success || !created.record_id) {
            throw created.error || created.error_message || '创建作品记录失败'
          }
          recordId = created.record_id
          store.setRecordId(recordId)
        }
        const updated = await updateHistory(recordId, payload)
        if (!updated.success) throw updated.error || updated.error_message || '保存失败'
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

  return { saving, error, dirty, save }
}
