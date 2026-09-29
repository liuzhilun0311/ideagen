import { computed, getCurrentInstance, onActivated, onDeactivated, onScopeDispose, ref, watch, type Ref } from 'vue'
import { copyLibraryItem, getLibraryOrder, saveLibraryOrder, type LibraryResource } from '../api/library'
import { useAuthStore } from '../stores/auth'
import { normalizeApiError } from '../utils/errors'

function copyRequestId() {
  // LAN HTTP on phones does not expose randomUUID; getRandomValues remains available.
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('')
}

export function useLibraryOrder(resource: LibraryResource, kind: Ref<string>, ids: Ref<string[]>) {
  const auth = useAuthStore()
  const stored = ref<string[]>([])
  const revision = ref<number | null>(null)
  const busy = ref(false)
  const error = ref('')
  let epoch = 0
  let active = true
  let request = 0
  let retryCopy: { source: string; id: string; revision: number } | null = null
  const order = computed(() => {
    const visible = new Set(ids.value)
    const present = stored.value.filter(id => visible.has(id))
    const known = new Set(present)
    return [...present, ...ids.value.filter(id => !known.has(id))]
  })
  function scope() {
    const owner = epoch, category = kind.value, token = auth.token
    return { category, valid: () => active && owner === epoch && category === kind.value && token === auth.token }
  }
  async function refresh() {
    if (!active || busy.value) return false
    const owner = scope(), sequence = ++request
    try {
      const result = await getLibraryOrder(resource, owner.category)
      if (!owner.valid() || sequence !== request) return false
      stored.value = result.order
      revision.value = result.revision
      error.value = ''
      return true
    } catch (cause) {
      if (owner.valid() && sequence === request) error.value = normalizeApiError(cause, '读取排序失败').detail
      return false
    }
  }
  async function move(source: string, target: string) {
    if (busy.value || source === target) return false
    const owner = scope()
    if (revision.value === null && !await refresh()) return false
    if (!owner.valid() || busy.value) return false
    const previous = [...order.value]
    const from = previous.indexOf(source), to = previous.indexOf(target)
    if (from < 0 || to < 0) return false
    const next = [...previous]
    next.splice(from, 1)
    next.splice(to, 0, source)
    stored.value = next
    busy.value = true
    error.value = ''
    ++request
    try {
      const result = await saveLibraryOrder(resource, owner.category, revision.value!, next)
      if (!owner.valid()) return false
      stored.value = result.order
      revision.value = result.revision
      retryCopy = null
      return true
    } catch (cause) {
      if (owner.valid()) {
        stored.value = previous
        revision.value = null
        error.value = normalizeApiError(cause, '排序保存失败').detail
      }
      return false
    } finally { if (owner.valid()) busy.value = false }
  }
  async function copy(source: string) {
    if (busy.value) return null
    const owner = scope()
    if (revision.value === null && !await refresh()) return null
    if (!owner.valid() || busy.value || !ids.value.includes(source)) return null
    if (!retryCopy || retryCopy.source !== source) retryCopy = { source, id: copyRequestId(), revision: revision.value! }
    const attempt = retryCopy
    busy.value = true
    error.value = ''
    ++request
    try {
      const result = await copyLibraryItem(resource, owner.category, source, attempt.revision, attempt.id)
      if (!owner.valid()) return null
      stored.value = result.order
      revision.value = result.revision
      retryCopy = null
      return result.created
    } catch (cause) {
      if (owner.valid()) {
        const problem = normalizeApiError(cause, '复制失败')
        error.value = problem.detail
        if (problem.status === 409 || problem.status === 400) {
          retryCopy = null
          revision.value = null
        }
      }
      return null
    } finally { if (owner.valid()) busy.value = false }
  }
  function invalidate() {
    ++epoch
    ++request
    busy.value = false
    stored.value = []
    revision.value = null
    error.value = ''
    retryCopy = null
  }
  watch([kind, () => auth.token, () => auth.user?.id, () => auth.sessionRevision], () => {
    invalidate()
    if (active) void refresh()
  }, { immediate: true, flush: 'sync' })
  if (getCurrentInstance()) {
    onDeactivated(() => { active = false; invalidate() })
    onActivated(() => { if (!active) { active = true; void refresh() } })
  }
  onScopeDispose(() => { active = false; invalidate() })
  return { order, busy, error, refresh, move, copy, invalidate }
}
