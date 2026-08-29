import { useGeneratorStore } from '../stores/generator'
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
    store.setRecordId(record.id)
    // 恢复已生成的文案（标题/文案/标签）
    const c = record.content
    if (c && ((c.titles && c.titles.length) || c.copywriting)) {
      store.setContent(c.titles || [], c.copywriting || '', c.tags || [])
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

  async function ensureRecord() {
    if (store.recordId) return

    console.warn('警告: recordId 不存在，尝试创建历史记录作为兜底')
    try {
      const result = await createHistory(store.topic, {
        raw: store.outline.raw,
        pages: store.outline.pages
      })
      if (result.success && result.record_id) {
        store.setRecordId(result.record_id)
        console.log('兜底创建历史记录成功:', store.recordId)
      }
    } catch (e) {
      console.error('兜底创建历史记录失败:', e)
    }
  }

  return {
    ensureRecord,
    restoreFromHistory
  }
}
