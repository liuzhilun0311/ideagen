<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { FileSearch, RefreshCw, X } from 'lucide-vue-next'
import { useGeneratorStore } from '../../stores/generator'
import { getGenerationDiagnostics, type GenerationDiagnostic } from '../../api/diagnostics'
import { getHistory } from '../../api/history'
import { getToken } from '../../api/token'
const props = defineProps<{ pageIndex?: number; generationId?: string }>()
const store = useGeneratorStore()
const dialog = ref<HTMLDialogElement>()
const events = ref<GenerationDiagnostic[]>([])
const loading = ref(false)
const error = ref('')
const page = ref('all')
let version = 0
const pages = computed(() => [...new Set(events.value.map(item => item.page_index).filter((value): value is number => typeof value === 'number'))].sort((a,b) => a-b))
const groups = computed(() => {
  const result = new Map<string, GenerationDiagnostic[]>()
  for (const event of events.value) {
    if (page.value !== 'all' && String(event.page_index) !== page.value) continue
    const key = `${event.page_index ?? 'unknown'}:${event.generation_id || 'legacy'}`
    result.set(key, [...(result.get(key) || []), event])
  }
  return [...result.entries()].reverse()
})
function close() { version++; loading.value = false; dialog.value?.close?.() }
async function load() {
  const ticket = ++version
  const record = store.recordId
  const token = getToken()
  const active = () => ticket === version && token === getToken() && record === store.recordId
  events.value = []
  error.value = ''
  loading.value = true
  try {
    // A failed first candidate may have a server task before the draft adopts any image.
    let task = store.taskId
    if (record) {
      const history = await getHistory(record)
      if (!active()) return
      if (!history.success || !history.record) throw new Error('无法读取作品记录')
      task = history.record.images?.task_id || task
    }
    if (!task) return
    const result = props.pageIndex === undefined
      ? await getGenerationDiagnostics(task)
      : await getGenerationDiagnostics(task, props.pageIndex, props.generationId)
    if (active()) events.value = result.events
  } catch {
    if (active()) error.value = '请求与响应加载失败，请重试。'
  } finally { if (active()) loading.value = false }
}
function open() { page.value = 'all'; dialog.value?.showModal(); void load() }
function text(event: GenerationDiagnostic) {
  const { headers, ...safe } = event
  return JSON.stringify(safe, null, 2)
}
onBeforeUnmount(() => { version++ })
watch(() => [store.recordId, props.pageIndex, props.generationId], () => {
  close()
  events.value = []
}, { flush: 'sync' })
</script>
<template>
  <button type="button" class="btn btn-secondary suite-diagnostics-button" @click="open"><FileSearch :size="16" />查看请求与响应</button>
    <dialog ref="dialog" :aria-label="pageIndex === undefined ? '整套图片请求与响应' : '本页图片请求与响应'" @cancel.prevent="close" @click="($event.target === dialog) && close()">
      <header><h2>{{ pageIndex === undefined ? '整套图片请求与响应' : `第 ${pageIndex + 1} 页 · 请求与响应` }}</h2><button class="icon-button" aria-label="关闭请求与响应" @click="close"><X :size="20" /></button></header>
      <div class="filters">
        <label v-if="pageIndex === undefined">页面 <select v-model="page" aria-label="记录页面"><option value="all">全部页面</option><option v-for="index in pages" :key="index" :value="String(index)">第 {{ index + 1 }} 页</option></select></label>
        <button class="icon-button" title="刷新记录" aria-label="刷新记录" :disabled="loading" @click="load"><RefreshCw :size="18" /></button>
      </div>
      <p>实际执行记录，按页面及生成记录分组；修改当前设置不会改变历史请求。</p>
      <p v-if="loading" role="status">正在加载…</p>
      <p v-else-if="error" role="alert">{{ error }}</p>
      <p v-else-if="!groups.length">暂无图片生成记录。</p>
      <section v-for="[key, items] in groups" :key="key">
        <h3>{{ items[0].page_index === undefined ? '任务' : `第 ${items[0].page_index + 1} 页` }} · {{ items[0].at }}</h3>
        <small v-if="items[0].generation_id">生成记录：{{ items[0].generation_id }}</small>
        <details v-for="(event, index) in items" :key="index">
          <summary>{{ event.source === 'upstream' ? '上游' : '本地' }} · {{ event.event === 'request' ? '请求' : '响应' }} · {{ event.http_status || event.status || event.at }}</summary>
          <pre>{{ text(event) }}</pre>
        </details>
      </section>
    </dialog>
</template>
<style scoped>
dialog { width:min(900px,calc(100% - 24px)); max-height:calc(100dvh - 32px); margin:auto; padding:20px; border:1px solid var(--border-color); border-radius:8px; overflow:auto; }
dialog::backdrop { background:#0006; }
header,.filters { display:flex; align-items:center; justify-content:space-between; gap:12px; }
h2 { font-size:18px; } h3 { font-size:14px; } p,small { font-size:12px; color:var(--text-sub); }
select { min-height:40px; max-width:100%; }
section { border-top:1px solid var(--border-color); padding-block:12px; }
summary { cursor:pointer; padding:10px 0; overflow-wrap:anywhere; font-size:13px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; max-height:360px; overflow:auto; font-size:12px; }
</style>
