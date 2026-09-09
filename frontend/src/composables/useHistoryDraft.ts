import { ref } from 'vue'
import type { Router } from 'vue-router'
import { getHistory } from '../api/history'
import { getImageUrl } from '../api/image'
import { useGeneratorStore } from '../stores/generator'
import { useStudioSession } from '../stores/studioSession'
import { useAuthStore } from '../stores/auth'
import { getToken } from '../api/token'
import { normalizeApiError, type AppError } from '../utils/errors'

export function useHistoryDraft(
  router: Pick<Router, 'push'>,
  confirmReplacement: (message: string) => boolean = message => window.confirm(message),
) {
  const store = useGeneratorStore()
  const session = useStudioSession()
  const auth = useAuthStore()
  const error = ref<AppError | null>(null)
  let request = 0

  function cancelPending() {
    request += 1
  }

  function refuse(message: string) {
    error.value = normalizeApiError(message, '无法打开作品')
    return false
  }

  async function loadRecord(id: string): Promise<boolean> {
    const currentRequest = ++request
    const token = auth.token
    const authRevision = auth.sessionRevision
    const userId = auth.user?.id
    const ownsRead = () => currentRequest === request
      && auth.token === token
      && auth.sessionRevision === authRevision
      && auth.user?.id === userId
      && getToken() === token
    error.value = null
    try {
      // Resuming never reads history, even if local edits removed every page.
      if (store.recordId === id) {
        await router.push(store.outline.pages.length ? '/workspace' : '/')
        return true
      }
      if (session.busy) return refuse('创作任务正在进行，请等待任务结束后再替换当前草稿。')

      const revision = session.revision
      const recordId = store.recordId
      const dirty = session.dirty
      const snapshot = JSON.stringify(store.$state)
      const userImages = [...store.userImages]
      const unchanged = () => session.revision === revision
        && store.recordId === recordId
        && session.dirty === dirty
        && JSON.stringify(store.$state) === snapshot
        && store.userImages.length === userImages.length
        && store.userImages.every((image, index) => image === userImages[index])
      const hasDraft = session.dirty || store.recordId || store.topic || store.referenceContent
        || store.outline.raw || store.outline.pages.length || store.images.length
        || store.userImages.length || store.content.titles.length
        || store.content.copywriting || store.content.tags.length
      if (hasDraft && !confirmReplacement('打开此作品将替换当前草稿，未保存的修改将丢失。确定继续吗？')) {
        return false
      }
      if (!ownsRead()) return false
      if (session.busy || !unchanged()) return refuse('当前草稿已变化，请确认后重新打开作品。')

      const response = await getHistory(id)
      // Only the active view selection and auth session own navigation and feedback.
      if (!ownsRead()) return false
      if (session.busy) return refuse('创作任务正在进行，请等待任务结束后再替换当前草稿。')
      if (!unchanged()) return refuse('读取期间当前草稿已变化，已保留修改。请重新打开作品。')
      if (!response.success || !response.record) {
        throw response.error || response.error_message || '打开历史记录失败'
      }
      const record = response.record
      if (record.id !== id) return refuse('返回的作品与所选记录不一致，请刷新列表后重试。')

      // Prepare independent values before obtaining permission to mutate the draft.
      const pages = record.outline.pages.map(page => ({ ...page }))
      const titles = [...(record.content?.titles || [])]
      const tags = [...(record.content?.tags || [])]
      const taskId = record.images.task_id
      const generated = record.images.generated || []
      const images = generated.some(Boolean) ? pages.map((page, index) => {
        const filename = generated[page.index] || generated[index] || ''
        return {
          index: page.index,
          url: filename ? getImageUrl(taskId || '', filename, false) : '',
          status: filename ? 'done' as const : 'error' as const,
          retryable: !filename,
        }
      }) : []

      if (!session.replaceDraft()) return refuse('创作任务正在进行，无法替换当前草稿。')
      store.setTopic(record.title)
      store.referenceContent = ''
      store.userImages = []
      store.setOutline(record.outline.raw, pages)
      store.setRecordId(record.id)
      store.lastSavedAt = record.updated_at || null
      if (record.content) store.setContent(titles, record.content.copywriting || '', tags)
      store.taskId = taskId
      store.images = images
      store.syncImageProgress()
      store.setEntrySource('history')
      await router.push('/workspace')
      return true
    } catch (cause) {
      if (ownsRead()) error.value = normalizeApiError(cause, '打开历史记录失败')
      return false
    }
  }

  return { error, loadRecord, cancelPending }
}
