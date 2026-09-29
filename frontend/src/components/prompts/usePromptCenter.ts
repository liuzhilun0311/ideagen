import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../../stores/auth'
import {
  copyPromptEntry, getPromptCatalog, getPromptUsers, getPromptVersions, promptDraft, promptError,
  reorderPromptEntries, restorePromptEntry, savePromptEntry,
  type PromptCategory, type PromptDraft, type PromptEntry, type PromptModule,
  type PromptOrder, type PromptUser, type PromptVersion,
} from '../../api/promptCenter'

export const modules: { id: PromptModule; name: string; categories: { id: PromptCategory; name: string }[] }[] = [
  { id: 'outline', name: '生成大纲', categories: [{ id: 'base', name: '基础规则' }, { id: 'organization', name: '组织方式' }, { id: 'audience', name: '目标受众' }, { id: 'tone', name: '表达语气' }] },
  { id: 'image', name: '生成图片', categories: [{ id: 'base', name: '基础规则' }, { id: 'layout', name: '单页布局' }, { id: 'style', name: '图片风格' }] },
  { id: 'content', name: '生成文案', categories: [{ id: 'base', name: '基础规则' }, { id: 'style', name: '文案风格' }, { id: 'structure', name: '正文结构' }, { id: 'length', name: '文案长度' }] },
]

export function usePromptCenter() {
  const auth = useAuthStore()
  const activeModule = ref<PromptModule>('outline')
  const category = ref<PromptCategory>('base')
  const legacy = ref(false)
  const entries = ref<PromptEntry[]>([])
  const orders = ref<Record<string, PromptOrder>>({})
  const search = ref('')
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  const conflict = ref(false)
  const notice = ref('')
  const draft = ref<PromptDraft | null>(null)
  const original = ref('')
  const readonly = ref(false)
  const users = ref<PromptUser[]>([])
  const usersLoading = ref(false)
  const usersError = ref('')
  const history = ref<PromptEntry | null>(null)
  const versions = ref<PromptVersion[]>([])
  const historyLoading = ref(false)
  let epoch = 0
  let active = true
  let loadSequence = 0
  let userSequence = 0
  const busy = computed(() => loading.value || saving.value || historyLoading.value)
  const dirty = computed(() => !!draft.value && !readonly.value && JSON.stringify(draft.value) !== original.value)
  const categories = computed(() => modules.find(module => module.id === activeModule.value)!.categories)
  const key = computed(() => `${activeModule.value}.${category.value}`)
  const ordered = computed(() => {
    const items = entries.value.filter(entry => entry.module === activeModule.value && entry.category === category.value)
    const ids = orders.value[key.value]?.ids || []
    const rank = new Map(ids.map((id, index) => [id, index]))
    return items.sort((a, b) => (rank.get(a.id) ?? ids.length) - (rank.get(b.id) ?? ids.length))
  })
  const filtered = computed(() => {
    const query = search.value.trim().toLowerCase()
    return ordered.value.filter(entry => `${entry.name} ${entry.description} ${entry.owner_name}`.toLowerCase().includes(query))
  })
  function editable(entry: PromptEntry) {
    return entry.can_edit && (entry.category !== 'base' || auth.isAdmin)
  }
  function report(cause: unknown) {
    const result = promptError(cause)
    error.value = result.message
    conflict.value = result.conflict
  }
  function discard() {
    if (busy.value) return false
    if (dirty.value && !window.confirm('有未保存的修改，确定放弃吗？')) return false
    draft.value = null
    history.value = null
    return true
  }
  async function load() {
    const owner = epoch
    const request = ++loadSequence
    loading.value = true
    try {
      const result = await getPromptCatalog()
      if (owner !== epoch || request !== loadSequence) return false
      entries.value = result.entries
      orders.value = result.orders || {}
      return true
    } catch (cause) {
      if (owner === epoch && request === loadSequence) report(cause)
      return false
    } finally { if (owner === epoch && request === loadSequence) loading.value = false }
  }
  async function reload() {
    if (!discard()) return
    error.value = ''
    conflict.value = false
    await load()
  }
  function switchModule(module: PromptModule | 'legacy') {
    if (!discard()) return
    legacy.value = module === 'legacy'
    if (module !== 'legacy') {
      activeModule.value = module
      category.value = 'base'
    }
    search.value = ''
    notice.value = ''
  }
  function switchCategory(value: PromptCategory) {
    if (!discard()) return
    category.value = value
    search.value = ''
    notice.value = ''
  }
  async function loadUsers() {
    if (usersLoading.value) return
    const owner = epoch
    const request = ++userSequence
    usersLoading.value = true
    usersError.value = ''
    try {
      const result = await getPromptUsers()
      if (owner === epoch && request === userSequence) users.value = result
    } catch (cause) {
      if (owner === epoch && request === userSequence) usersError.value = promptError(cause).message
    } finally { if (owner === epoch && request === userSequence) usersLoading.value = false }
  }
  function open(entry?: PromptEntry) {
    if (!discard()) return
    if (!entry && category.value === 'base') return
    readonly.value = entry ? !editable(entry) : false
    draft.value = entry ? promptDraft(entry) : {
      module: activeModule.value, category: category.value, name: '', description: '', content: '',
      metadata: {}, enabled: true, visibility: 'private', allowed_users: [],
    }
    original.value = JSON.stringify(draft.value)
    notice.value = ''
  }
  watch(() => draft.value?.visibility, value => {
    if (value === 'selected' && !readonly.value) void loadUsers()
  })
  async function mutate(operation: () => Promise<PromptEntry>, message: string, editResult = false) {
    if (busy.value || conflict.value) return
    const owner = epoch
    saving.value = true
    error.value = ''
    notice.value = ''
    try {
      const entry = await operation()
      if (owner !== epoch) return
      draft.value = null
      history.value = null
      notice.value = message
      const refreshed = await load()
      if (owner !== epoch) return
      if (!refreshed) notice.value = `${message}，但目录刷新失败。请重新加载，勿重复提交。`
      if (editResult && refreshed) {
        const current = entries.value.find(item => item.id === entry.id) || entry
        draft.value = promptDraft(current)
        original.value = JSON.stringify(draft.value)
        readonly.value = !editable(current)
      }
    } catch (cause) { if (owner === epoch) report(cause) }
    finally { if (owner === epoch) saving.value = false }
  }
  async function save() {
    if (!draft.value || readonly.value || busy.value || conflict.value) return
    const value = JSON.parse(JSON.stringify(draft.value)) as PromptDraft
    value.name = value.name.trim()
    if (!value.name || !value.content.trim()) { error.value = '请填写名称和指令正文。'; return }
    if (!value.id && ['自动', '自动选择', '自定义', '自定义受众'].includes(value.name)) {
      error.value = '该名称属于系统行为，请使用其他名称。'; return
    }
    if (value.category === 'base' && !auth.isAdmin) return
    if (value.visibility !== 'selected') value.allowed_users = []
    await mutate(() => savePromptEntry(value), '已保存')
  }
  async function copy(entry: PromptEntry) {
    if (!discard()) return
    await mutate(() => copyPromptEntry(entry.id), '副本已创建', true)
  }
  async function toggle(entry: PromptEntry) {
    if (!editable(entry) || entry.category === 'base' || !discard()) return
    await mutate(() => savePromptEntry({ ...promptDraft(entry), enabled: !entry.enabled }), entry.enabled ? '已停用' : '已启用')
  }
  async function showHistory(entry: PromptEntry) {
    if (!editable(entry) || !discard()) return
    const owner = epoch
    history.value = entry
    versions.value = []
    historyLoading.value = true
    error.value = ''
    try {
      const result = await getPromptVersions(entry.id)
      if (owner === epoch) versions.value = result
    } catch (cause) { if (owner === epoch) report(cause) }
    finally { if (owner === epoch) historyLoading.value = false }
  }
  async function restore(entry: PromptEntry, version?: number) {
    if (!editable(entry) || busy.value || conflict.value) return
    if (!window.confirm(version === undefined ? '恢复内置默认内容？将创建新版本，保留当前授权。' : `恢复版本 v${version}？将创建新版本，保留当前授权。`)) return
    await mutate(() => restorePromptEntry(entry.id, entry.revision, version), '已恢复为新版本')
  }
  async function move(id: string, target: string) {
    if (busy.value || conflict.value || category.value === 'base' || search.value.trim()) return
    const ids = ordered.value.map(entry => entry.id)
    const from = ids.indexOf(id), to = ids.indexOf(target)
    if (from < 0 || to < 0 || from === to) return
    const owner = epoch
    const orderKey = key.value
    ids.splice(to, 0, ids.splice(from, 1)[0]!)
    saving.value = true
    error.value = ''
    try {
      const revision = await reorderPromptEntries(activeModule.value, category.value, ids, orders.value[orderKey]?.revision || 0)
      if (owner === epoch) orders.value[orderKey] = { ids, revision }
    } catch (cause) { if (owner === epoch) report(cause) }
    finally { if (owner === epoch) saving.value = false }
  }
  function step(index: number, direction: -1 | 1) {
    const source = ordered.value[index], target = ordered.value[index + direction]
    if (source && target) void move(source.id, target.id)
  }
  function beforeUnload(event: BeforeUnloadEvent) {
    if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = '' }
  }
  function invalidate() {
    ++epoch
    loading.value = saving.value = historyLoading.value = usersLoading.value = false
  }
  watch([() => auth.token, () => auth.user?.id, () => auth.sessionRevision], () => {
    invalidate()
    entries.value = []
    orders.value = {}
    users.value = []
    draft.value = history.value = null
    error.value = notice.value = ''
    conflict.value = false
    if (active) void load()
  }, { flush: 'sync' })
  onMounted(() => { window.addEventListener('beforeunload', beforeUnload); void load() })
  onDeactivated(() => { active = false; invalidate() })
  onActivated(() => { if (!active) { active = true; void load() } })
  onBeforeUnmount(() => { invalidate(); window.removeEventListener('beforeunload', beforeUnload) })
  return {
    auth, activeModule, category, categories, legacy, search, entries, ordered, filtered,
    draft, readonly, users, usersLoading, usersError, history, versions, historyLoading,
    busy, saving, loading, dirty, error, conflict, notice, editable, discard, reload,
    switchModule, switchCategory, loadUsers, open, save, copy, toggle, showHistory, restore, move, step,
  }
}
