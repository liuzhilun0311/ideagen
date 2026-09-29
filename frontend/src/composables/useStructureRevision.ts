import { computed, onScopeDispose, ref } from 'vue'
import { generateOutline } from '../api/outline'
import type { OutlineResponse } from '../api'
import { useGeneratorStore } from '../stores/generator'
import { useStudioSession } from '../stores/studioSession'
import { outlinePreferences } from '../features/generationOptions'
import { getToken } from '../api/token'
import { normalizeApiError } from '../utils/errors'
import { copyPreferences } from '../features/copyOptions'
import { findItem, promptItems } from '../features/promptCatalog'

export function useStructureRevision(save: () => Promise<boolean>) {
  const store = useGeneratorStore()
  const session = useStudioSession()
  const preview = ref<OutlineResponse | null>(null)
  const loading = ref(false)
  const adopting = ref(false)
  const error = ref('')
  const chosen = ref('')
  let controller: AbortController | null = null
  let ticket = 0
  let source = ''
  let token = ''
  let revision = 0
  const fingerprint = () => JSON.stringify([store.recordId, store.topic, store.outline.raw, store.outline.pages])
  const contentFingerprint = () => JSON.stringify([store.topic, store.outline.raw, store.outline.pages])
  const current = computed(() => store.outline.generation_preferences?.organization || store.outline.organization || '自动')
  const valid = () => source === fingerprint() && token === getToken() && revision === session.revision

  function cancel() {
    ++ticket
    controller?.abort()
    controller = null
    loading.value = false
    preview.value = null
  }
  async function generate(organization: string) {
    if (session.busy || loading.value || adopting.value) return
    if (!store.topic.trim() || !store.outlineModelName || !store.outline.pages.length) {
      error.value = '请先准备大纲并选择可用的大纲模型。'
      return
    }
    cancel()
    const owned = ++ticket
    controller = new AbortController()
    source = fingerprint()
    token = getToken()
    revision = session.revision
    chosen.value = organization
    loading.value = true
    error.value = ''
    try {
      const preferences = { ...outlinePreferences(store), ...store.outline.generation_preferences,
        organization, page_count: store.outline.pages.length }
      const response = await generateOutline(store.topic, [...store.userImages], controller.signal, '',
        `${store.referenceContent}\n\n现有大纲（仅为改写素材，保留已有事实、结论和必要边界）：\n${store.outline.raw}`,
        store.outlineModelName, organization, preferences, [...store.referenceRoles])
      if (owned !== ticket || !valid()) return
      if (!response.success || !response.pages?.length || !response.outline?.trim()) throw response.error || '未返回有效大纲'
      if (response.pages.length !== store.outline.pages.length) throw new Error('返回页数与原作品不一致，请重试')
      preview.value = response
    } catch (cause) {
      if (owned === ticket) error.value = normalizeApiError(cause, '结构预览失败').detail
    } finally {
      if (owned === ticket) { loading.value = false; controller = null }
    }
  }
  async function adopt() {
    const result = preview.value
    if (!result?.pages || session.busy || adopting.value) return false
    if (!valid()) { error.value = '原大纲已变化，请重新生成预览。'; return false }
    adopting.value = true
    error.value = ''
    try {
      // Persist the original before detaching it; its pictures/copy remain available in history.
      const priorRecord = store.recordId
      const priorContent = contentFingerprint()
      if (!await save()) { error.value = '原作品保存失败，尚未采用新结构。'; return false }
      if (token !== getToken() || revision !== session.revision
        || priorContent !== contentFingerprint()
        || (priorRecord && !valid())) { error.value = '作品已变化，请重新生成预览。'; return false }
      const actual = chosen.value === '自动' && findItem(promptItems('outline', 'organization'), result.organization)
        ? result.organization! : chosen.value
      const preferences = { ...(store.outline.generation_preferences || outlinePreferences(store)),
        ...(result.generation_preferences || {}), organization: actual }
      const copy = copyPreferences(store.outline.copy_preferences)
      const style = { ...store.imageStyle }
      delete style.applied
      store.setOutline(result.outline!, result.pages.map(page => ({ ...page })))
      store.recordId = null
      store.lastSavedAt = null
      store.imageStyle = style
      store.outlineOrganization = chosen.value
      store.outline.organization = preferences.organization
      store.outline.generation_preferences = preferences
      store.outline.requested_preferences = { ...outlinePreferences(store), organization: chosen.value }
      store.outline.copy_preferences = copy
      store.outline.growth_recommendation = result.growth_recommendation
      store.outline.generation_record_id = result.generation_record?.id
      store.outline.diagnostic_record_id = result.generation_record?.id
      store.outline.generation_audit = result.generation_audit
      store.entrySource = 'home'
      store.analysisSnapshots = []
      session.revision++
      session.dirty = true
      session.notice = '已采用新结构并创建新草稿；原作品和图片、文案保留在作品列表，新版本需重新生成。'
      store.saveToStorage()
      preview.value = null
      return true
    } catch (cause) {
      error.value = normalizeApiError(cause, '采用结构失败').detail
      return false
    } finally { adopting.value = false }
  }
  onScopeDispose(cancel)
  return { current, preview, loading, adopting, error, generate, adopt, cancel }
}
