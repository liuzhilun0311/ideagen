import { computed, getCurrentInstance, onActivated, onDeactivated, onScopeDispose, ref, watch, type Ref } from 'vue'
import { getProcessingState, updatePostprocessing, type ProcessingAction, type ProcessingState, type ProcessingStrength, type ProcessingVersion } from '../api/postprocessing'
import { withToken } from '../api/image'
import { getToken } from '../api/token'
import { useAuthStore } from '../stores/auth'
import { normalizeApiError, type AppError } from '../utils/errors'

export function usePostprocessing(recordId: Ref<string | null>) {
  const auth = useAuthStore()
  const state = ref<ProcessingState | null>(null)
  const error = ref<AppError | null>(null)
  const pending = ref(0)
  const loading = computed(() => pending.value > 0)
  // Keep authenticated display URLs out of persisted/server metadata.
  const pages = computed(() => (state.value?.pages || []).map(page => ({
    ...page,
    original_url: withToken(page.original_url),
    processed_url: page.processed_url ? withToken(page.processed_url) : null,
  })))
  let epoch = 0
  let readSequence = 0
  let active = true
  let disposed = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let mutationQueue: Promise<unknown> = Promise.resolve()
  let mutationCount = 0

  function clearTimer() {
    if (timer !== undefined) clearTimeout(timer)
    timer = undefined
  }
  function owner() {
    const id = recordId.value
    const revision = epoch
    const token = getToken()
    return { id, valid: () => !disposed && active && revision === epoch && id === recordId.value && token === getToken() }
  }
  function schedule() {
    clearTimer()
    if (active && !disposed && recordId.value && ![401, 403, 404].includes(error.value?.status || 0)) {
      timer = setTimeout(() => { void refresh() }, 2500)
    }
  }
  async function refresh(): Promise<ProcessingState | null> {
    const scope = owner()
    if (!scope.id || !scope.valid()) return null
    if (mutationCount) { schedule(); return null }
    clearTimer()
    const sequence = ++readSequence
    pending.value += 1
    try {
      const response = await getProcessingState(scope.id)
      if (!scope.valid() || sequence !== readSequence) return null
      state.value = response
      error.value = null
      return response
    } catch (cause) {
      if (scope.valid() && sequence === readSequence) {
        error.value = normalizeApiError(cause, '读取图片处理状态失败')
        if ([401, 403, 404].includes(error.value.status)) state.value = null
      }
      return null
    } finally {
      if (scope.valid()) {
        pending.value -= 1
        if (sequence === readSequence) schedule()
      }
    }
  }
  function mutate(action: ProcessingAction): Promise<ProcessingState | null> {
    const scope = owner()
    if (!scope.id || !scope.valid()) return Promise.resolve(null)
    clearTimer()
    ++readSequence
    ++mutationCount
    pending.value += 1
    // Serialize user choices so a slow adoption cannot overwrite a later choice.
    const task = mutationQueue.then(async () => {
      if (!scope.valid()) return null
      try {
        const response = await updatePostprocessing(scope.id!, action)
        if (!scope.valid()) return null
        state.value = response
        error.value = null
        return response
      } catch (cause) {
        if (scope.valid()) {
          error.value = normalizeApiError(cause, '图片后处理操作失败')
          if ([401, 403, 404].includes(error.value.status)) state.value = null
        }
        return null
      } finally {
        if (scope.valid()) {
          --mutationCount
          pending.value -= 1
          if (!mutationCount) schedule()
        }
      }
    })
    mutationQueue = task
    return task
  }
  function reset() {
    ++epoch
    ++readSequence
    clearTimer()
    pending.value = 0
    mutationCount = 0
    mutationQueue = Promise.resolve()
    state.value = null
    error.value = null
    if (active) void refresh()
  }
  watch([recordId, () => auth.token, () => auth.user?.id, () => auth.sessionRevision], reset, { immediate: true, flush: 'sync' })
  if (getCurrentInstance()) {
    onDeactivated(() => { active = false; reset() })
    onActivated(() => {
      if (!active) { active = true; reset() }
    })
  }
  onScopeDispose(() => { disposed = true; active = false; reset() })

  return {
    state, pages, error, loading, refresh,
    process: (indices: number[], strength: ProcessingStrength = 'medium', force = false) =>
      mutate({ action: 'process', indices: [...indices], strength, force }),
    adopt: (index: number, version: ProcessingVersion, sourceRevision: string) =>
      mutate({ action: 'adopt', index, version, source_revision: sourceRevision }),
    preferences: (automatic: boolean, strength: ProcessingStrength) =>
      mutate({ action: 'preferences', automatic, strength }),
  }
}
