<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { listUsers, type AuthUser } from '../../api/auth'
import { getHistorySharing, setHistorySharing } from '../../api/history'
import { useAuthStore } from '../../stores/auth'
import { normalizeApiError } from '../../utils/errors'

const props = defineProps<{ record: { id: string; title: string; owner?: { id: string; username: string } } }>()
const emit = defineEmits<{ close: []; saved: [id: string, userIds: string[]] }>()
const auth = useAuthStore()
const users = ref<AuthUser[]>([])
const selected = ref<string[]>([])
const keyword = ref('')
const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)
const error = ref('')
const panel = ref<HTMLElement>()
let previousFocus: HTMLElement | null = null
let epoch = 0
let active = true
const filteredUsers = computed(() => users.value.filter(user =>
  user.id !== props.record.owner?.id && user.username.toLocaleLowerCase().includes(keyword.value.trim().toLocaleLowerCase())))
function invalidate() {
  ++epoch
  users.value = []
  selected.value = []
  loaded.value = false
  saving.value = false
}
function close() { active = false; invalidate(); emit('close') }
async function load() {
  invalidate()
  const request = epoch
  loading.value = true
  error.value = ''
  keyword.value = ''
  try {
    const [accounts, sharing] = await Promise.all([listUsers(), getHistorySharing(props.record.id)])
    if (!active || request !== epoch) return
    if (!accounts.success || !sharing.success) throw new Error(accounts.error_message || sharing.error_message || '读取共享配置失败')
    users.value = accounts.users || []
    selected.value = sharing.user_ids.filter(id => id !== props.record.owner?.id)
    loaded.value = true
  } catch (cause) {
    if (active && request === epoch) error.value = normalizeApiError(cause, '读取共享配置失败').detail
  } finally { if (active && request === epoch) loading.value = false }
}
async function save() {
  if (saving.value || !loaded.value || !active) return
  const request = epoch
  const id = props.record.id
  saving.value = true
  error.value = ''
  try {
    const result = await setHistorySharing(id, [...selected.value])
    if (!active || request !== epoch) return
    if (!result.success) throw new Error(result.error_message || normalizeApiError(result.error, '保存共享配置失败').detail)
    emit('saved', id, result.user_ids)
  } catch (cause) {
    if (active && request === epoch) error.value = normalizeApiError(cause, '保存共享配置失败').detail
  } finally { if (active && request === epoch) saving.value = false }
}
watch(() => props.record.id, load, { immediate: true, flush: 'sync' })
watch([() => auth.token, () => auth.user?.id, () => auth.user?.is_admin, () => auth.sessionRevision], close, { flush: 'sync' })
onDeactivated(() => { active = false; invalidate() })
onMounted(async () => {
  previousFocus = document.activeElement as HTMLElement | null
  await nextTick()
  if (active) panel.value?.focus()
})
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.stopPropagation(); close(); return }
  if (event.key !== 'Tab') return
  const controls = panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)')
  if (!controls?.length) return
  const first = controls[0]!
  const last = controls[controls.length - 1]!
  if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.value)) {
    event.preventDefault(); last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault(); first.focus()
  }
}
onBeforeUnmount(() => { active = false; invalidate(); previousFocus?.focus?.() })
</script>

<template>
  <div class="sharing-mask" @click.self="close">
    <section ref="panel" class="sharing-dialog" role="dialog" aria-modal="true" aria-labelledby="sharing-title" tabindex="-1" @keydown="keydown">
      <header><h2 id="sharing-title">配置用户</h2><button class="icon-button" aria-label="关闭共享配置" @click="close"><X :size="20" /></button></header>
      <p class="work-title">{{ record.title }}</p>
      <p v-if="record.owner" class="owner">作者：{{ record.owner.username }}</p>
      <input v-model="keyword" class="field" type="search" aria-label="搜索用户名" placeholder="搜索用户名" :disabled="loading || saving" />
      <p v-if="loading" role="status">正在读取共享配置</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div v-if="loaded" class="users">
        <label v-for="user in filteredUsers" :key="user.id" class="user">
          <input v-model="selected" type="checkbox" :value="user.id" :disabled="saving" />
          <span>{{ user.username }}</span>
        </label>
        <p v-if="!filteredUsers.length">暂无匹配用户</p>
      </div>
      <footer>
        <span>已选择 {{ selected.length }} 人</span>
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" :disabled="!loaded || loading || saving" @click="save">{{ saving ? '保存中...' : '保存' }}</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.sharing-mask { position: fixed; inset: 0; z-index: 1400; background: #10182066; display: grid; place-items: center; padding: 16px; }
.sharing-dialog { width: 100%; max-width: 460px; max-height: calc(100dvh - 32px); overflow: auto; background: white; border-radius: 8px; padding: 24px; }
header, footer { display: flex; align-items: center; gap: 12px; }
header { justify-content: space-between; }
h2 { font-size: 20px; margin: 0; }
.work-title, .owner, .user span { overflow-wrap: anywhere; }
.owner { color: #666; font-size: 13px; }
.field { width: 100%; min-height: 44px; }
.users { max-height: 320px; overflow: auto; margin: 12px 0; }
.user { display: flex; gap: 10px; align-items: center; min-height: 44px; }
footer { margin-top: 20px; flex-wrap: wrap; justify-content: flex-end; }
footer span { margin-right: auto; font-size: 13px; }
.error { color: #b42335; }
</style>
