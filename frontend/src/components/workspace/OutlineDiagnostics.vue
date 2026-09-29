<script setup lang="ts">
import { onBeforeUnmount, onDeactivated, ref } from 'vue'
import { FileSearch, RefreshCw, X } from 'lucide-vue-next'
import { listOutlineRuns, type OutlineRun } from '../../api/outline'
import { getOutlineDiagnostics, type GenerationDiagnostic } from '../../api/diagnostics'
import { normalizeApiError } from '../../utils/errors'

const props = defineProps<{ recordId?: string }>()
const dialog = ref<HTMLDialogElement | null>(null)
const runs = ref<OutlineRun[]>([])
const selected = ref('')
const events = ref<GenerationDiagnostic[]>([])
const loading = ref(false)
const error = ref('')
const responseAvailable = ref(false)
const status = ref('')
let version = 0
const statusLabels: Record<string, string> = {
  prepared: '待发送', generating: '生成中', succeeded: '成功', failed: '失败', cancelled: '已取消',
}

async function loadRecord() {
  const current = ++version
  events.value = []
  error.value = ''
  responseAvailable.value = false
  if (!selected.value) { loading.value = false; return }
  loading.value = true
  try {
    const result = await getOutlineDiagnostics(selected.value)
    if (current !== version) return
    events.value = result.events
    responseAvailable.value = result.response_available
    status.value = result.status
  } catch (cause) {
    if (current === version) error.value = normalizeApiError(cause).detail
  } finally {
    if (current === version) loading.value = false
  }
}

async function open() {
  dialog.value?.showModal()
  const current = ++version
  loading.value = true
  error.value = ''
  events.value = []
  runs.value = []
  selected.value = ''
  try {
    const result = await listOutlineRuns(props.recordId)
    if (current !== version) return
    runs.value = result
    selected.value = result.find(run => run.id === props.recordId)?.id || result[0]?.id || ''
    await loadRecord()
  } catch (cause) {
    if (current === version) {
      error.value = normalizeApiError(cause).detail
      loading.value = false
    }
  }
}

function close() {
  ++version
  loading.value = false
  if (dialog.value?.open) dialog.value.close()
}
onBeforeUnmount(close)
onDeactivated(close)
</script>

<template>
  <button type="button" class="btn btn-secondary" @click="open">
    <FileSearch :size="16" />查看请求与响应
  </button>
  <dialog ref="dialog" class="outline-diagnostics" aria-labelledby="outline-diagnostics-title"
    @cancel.prevent="close" @click="($event.target === dialog) && close()">
    <header>
      <h2 id="outline-diagnostics-title">大纲请求与响应</h2>
      <button class="icon-button" aria-label="关闭大纲诊断" title="关闭" @click="close"><X :size="20" /></button>
    </header>
    <div class="diagnostic-controls">
      <label for="outline-diagnostic-record">生成记录</label>
      <select id="outline-diagnostic-record" v-model="selected" :disabled="loading || !runs.length" @change="loadRecord">
        <option v-if="!runs.length" value="">暂无记录</option>
        <option v-for="run in runs" :key="run.id" :value="run.id">
          {{ run.created_at.replace('T', ' ').slice(0, 19) }} · {{ run.model || run.provider || '未发送' }} · {{ statusLabels[run.status] || run.status }}
        </option>
      </select>
      <button class="icon-button" :disabled="loading" aria-label="刷新大纲诊断" title="刷新"
        @click="selected ? loadRecord() : open()"><RefreshCw :size="18" /></button>
    </div>
    <p v-if="loading" role="status">正在加载请求与响应…</p>
    <p v-else-if="error" class="diagnostic-error" role="alert">{{ error }}</p>
    <template v-else>
      <p v-if="!selected">暂无大纲生成记录。</p>
      <p v-else-if="!responseAvailable" role="status">
        {{ status === 'generating' || status === 'prepared' ? '尚未收到响应，请稍后刷新。' : '该次生成未保存响应，仅能查看已保存的请求快照。' }}
      </p>
      <article v-for="(event, index) in events" :key="`${event.at}-${index}`">
        <h3>{{ event.source === 'upstream' ? '上游接口' : event.source === 'snapshot' ? '历史快照' : '本地记录' }} · {{ event.event === 'request' ? '请求' : '响应' }}</h3>
        <pre>{{ JSON.stringify(event, null, 2) }}</pre>
      </article>
    </template>
  </dialog>
</template>

<style scoped>
.outline-diagnostics { box-sizing:border-box; width:min(840px,calc(100% - 24px)); max-height:calc(100dvh - 32px); overflow:auto; margin:auto; padding:20px; border:1px solid var(--border-color,#e2e5eb); border-radius:8px; background:#fff; color:var(--text-main,#20242c); }
.outline-diagnostics::backdrop { background:#151d3266; }
header { display:flex; align-items:center; justify-content:space-between; gap:12px; }
h2 { margin:0; font-size:18px; }
h3 { margin:0 0 8px; font-size:14px; }
.diagnostic-controls { display:grid; grid-template-columns:auto minmax(0,1fr) 36px; align-items:center; gap:8px; margin:18px 0; }
select { width:100%; min-width:0; height:36px; padding:0 8px; border:1px solid var(--border-color,#e2e5eb); border-radius:4px; background:#fff; }
.icon-button { display:inline-flex; align-items:center; justify-content:center; width:36px; height:36px; flex-shrink:0; }
article { border-top:1px solid var(--border-color,#e2e5eb); padding-top:14px; margin-top:14px; }
pre { max-height:360px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; font:12px/1.5 ui-monospace,Consolas,monospace; }
.diagnostic-error { color:#b42318; overflow-wrap:anywhere; }
@media (max-width:480px) { .outline-diagnostics { padding:12px; } .diagnostic-controls { grid-template-columns:minmax(0,1fr) 36px; } .diagnostic-controls label { grid-column:1 / -1; } }
</style>
