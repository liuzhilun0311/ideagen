import { watch, onScopeDispose, getCurrentScope } from 'vue'
import { useGeneratorStore } from '../stores/generator'
import { useStudioSession } from '../stores/studioSession'
import { useAuthStore } from '../stores/auth'
import { referenceDraftStorage, type ReferenceDraftStorage } from '../features/referenceDraftStorage'
import { validateReferenceImages } from '../features/referenceImages'

export function useReferenceDraftPersistence(storage: ReferenceDraftStorage = referenceDraftStorage) {
  const store = useGeneratorStore()
  const session = useStudioSession()
  const auth = useAuthStore()
  let version = 0
  let restoring = false
  let disposed = false
  let failedRestore = false
  let queue: Promise<void> = Promise.resolve()
  const owner = () => auth.user?.id || 'anonymous'

  async function restore() {
    const ticket = ++version
    const key = store.referenceImageKey
    const user = owner()
    const revision = session.revision
    failedRestore = false
    if (!key || store.userImages.length) return
    session.referenceLoading = true
    session.referenceStorageError = ''
    try {
      const result = await storage.read(user)
      if (disposed || ticket !== version || owner() !== user || session.revision !== revision
        || store.referenceImageKey !== key || store.userImages.length) return
      if (!result || result.key !== key || !result.files.length) throw new Error('图片草稿与当前内容不匹配。')
      const files = result.files.map(file => new File([file.blob], file.name, {
        type: file.type, lastModified: file.lastModified,
      }))
      validateReferenceImages(files)
      restoring = true
      store.userImages = files
      restoring = false
    } catch {
      if (!disposed && ticket === version && owner() === user && session.revision === revision) {
        failedRestore = true
        session.referenceStorageError = '参考图片恢复失败。请重试，或重新添加图片；文字草稿已保留。'
      }
    } finally {
      if (ticket === version) session.referenceLoading = false
    }
  }

  function persist(): Promise<void> {
    const files = [...store.userImages]
    const user = owner()
    const ticket = ++version
    session.referenceLoading = false
    failedRestore = false
    const key = crypto.randomUUID?.()
      || Array.from(crypto.getRandomValues(new Uint32Array(4)), value => value.toString(16)).join('-')
    store.referenceImageKey = files.length ? key : ''
    store.saveToStorage()
    session.referenceSaving = true
    session.referenceStorageError = ''
    const value = { key, files: files.map(file => ({
      name: file.name, type: file.type, lastModified: file.lastModified, blob: file,
    })) }
    // Serialize writes so a slow previous upload cannot overwrite a later deletion.
    queue = queue.catch(() => {}).then(async () => {
      if (disposed || owner() !== user) return
      await storage.write(user, value)
    }).catch(() => {
      if (!disposed && ticket === version && owner() === user) {
        session.referenceStorageError = '参考图片尚未保存到本机，请重试。刷新或关闭页面可能丢失这些图片。'
      }
    }).finally(() => {
      if (ticket === version) session.referenceSaving = false
    })
    return queue
  }

  const stopImages = watch(() => [...store.userImages], () => {
    if (!restoring) void persist()
  }, { flush: 'sync' })
  const stopOwner = watch(() => auth.user?.id, () => {
    version++
    failedRestore = false
    session.referenceLoading = false
    session.referenceSaving = false
    session.referenceStorageError = ''
    restoring = true
    store.userImages = []
    store.referenceImageKey = ''
    restoring = false
    store.saveToStorage()
  }, { flush: 'sync' })
  const ready = restore()
  function stop() {
    disposed = true
    version++
    stopImages()
    stopOwner()
  }
  if (getCurrentScope()) onScopeDispose(stop)
  return { ready, retry: () => failedRestore ? restore() : persist(), stop }
}
