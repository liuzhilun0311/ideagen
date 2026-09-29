<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { FileSearch, Copy, X } from 'lucide-vue-next'
import { useGeneratorStore } from '../../stores/generator'
import { getToken } from '../../api/token'
import { outlineRequest } from '../../features/outlineRequest'
import { previewOutlinePrompt, listOutlineRuns, type OutlineRun } from '../../api/outline'
import { normalizeApiError } from '../../utils/errors'
const props = defineProps<{ busy?: boolean; home?: boolean }>()
const store = useGeneratorStore()
const dialog = ref<HTMLDialogElement>()
const textArea = ref<HTMLTextAreaElement>()
const mode = ref<'preview' | 'records'>('preview')
const loading = ref(false)
const error = ref('')
const copied = ref(false)
const preview = ref('')
const records = ref<OutlineRun[]>([])
const selected = ref('')
const previews = ref<string[]>([])
let revision = 0
const current = computed(() => records.value.find(item => item.id === selected.value))
const prompt = computed(() => mode.value === 'preview' ? preview.value : current.value?.prompt || '')
const pictures = computed(() => mode.value === 'preview' ? previews.value : current.value?.references.map(item => item.thumbnail) || [])
const statuses: Record<string, string> = { prepared: '请求已准备', generating: '生成中', succeeded: '成功', failed: '失败', cancelled: '已取消' }
function release() { previews.value.forEach(URL.revokeObjectURL); previews.value = [] }
function close() { ++revision; release(); dialog.value?.close() }
async function open(nextMode: 'preview' | 'records') {
  const ticket = ++revision
  const token = getToken()
  mode.value = nextMode
  error.value = ''
  copied.value = false
  preview.value = ''
  records.value = []
  selected.value = ''
  release()
  loading.value = true
  await nextTick()
  dialog.value?.showModal()
  try {
    if (nextMode === 'preview') {
      const request = outlineRequest(store, props.home)
      const input = { ...request.preferences, topic: request.topic, reference_content: request.reference_content,
        image_count: request.image_count, reference_roles: request.reference_roles }
      previews.value = request.images.map(file => URL.createObjectURL(file))
      const result = await previewOutlinePrompt(input)
      if (ticket === revision && token === getToken()) preview.value = result.prompt
    } else {
      const result = await listOutlineRuns(store.outline.generation_record_id)
      if (ticket === revision && token === getToken()) {
        records.value = result
        selected.value = result.some(run => run.id === store.outline.generation_record_id)
          ? store.outline.generation_record_id! : result[0]?.id || ''
      }
    }
  } catch (cause) {
    if (ticket === revision && token === getToken()) error.value = normalizeApiError(cause, '提示词加载失败').detail
  } finally { if (ticket === revision) loading.value = false }
}
async function copy() {
  try { await navigator.clipboard.writeText(prompt.value); copied.value = true }
  catch {
    textArea.value?.focus()
    textArea.value?.select()
    copied.value = document.execCommand('copy')
    if (!copied.value) error.value = '浏览器未允许复制，文本已选中。'
  }
}
onBeforeUnmount(() => { ++revision; release() })
</script>

<template>
  <div class="prompt-inspector">
    <button type="button" class="btn btn-secondary" :disabled="!store.topic.trim() && !store.outline.generation_record_id" @click="open(busy || store.outline.generation_record_id ? 'records' : 'preview')"><FileSearch :size="16" />查看本次提示词</button>
    <dialog ref="dialog" aria-labelledby="outline-inspector-heading" @cancel="close" @click="($event.target === dialog) && close()">
      <header><h2 id="outline-inspector-heading">{{ mode === 'preview' ? '本次大纲提示词 · 预览' : '大纲生成记录' }}</h2><button class="icon-button" title="关闭" aria-label="关闭提示词查看" @click="close"><X :size="20" /></button></header>
      <div class="inspector-tabs" role="tablist" aria-label="提示词来源">
        <button role="tab" :aria-selected="mode === 'preview'" :disabled="busy || !store.topic.trim()" @click="open('preview')">下次生成预览</button>
        <button role="tab" :aria-selected="mode === 'records'" @click="open('records')">生成请求记录</button>
      </div>
      <p v-if="loading" role="status">正在加载…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="!loading">
        <label v-if="mode === 'records' && records.length">生成记录
          <select v-model="selected" class="field" @change="copied = false">
            <option v-for="run in records" :key="run.id" :value="run.id">{{ new Date(run.created_at).toLocaleString() }} · {{ statuses[run.status] || run.status }} · {{ run.provider || run.model }}</option>
          </select>
        </label>
        <p v-if="mode === 'records' && !records.length && !error">暂无记录；功能上线前的请求未保存。</p>
        <p v-if="current && mode === 'records'">{{ current.sent ? '已提交模型调用' : '尚未提交模型调用' }} · {{ current.model || current.provider }} · {{ statuses[current.status] }}</p>
        <div v-if="pictures.length" class="references"><span>参考图片 · {{ pictures.length }} 张</span><img v-for="(src, index) in pictures" :key="index" :src="src" :alt="`第 ${index + 1} 张参考图`" /></div>
        <textarea v-if="prompt" ref="textArea" readonly :value="prompt" aria-label="完整大纲生成提示词"></textarea>
        <footer v-if="prompt"><span>{{ prompt.length }} 字符</span><button class="btn btn-primary" @click="copy"><Copy :size="16" />{{ copied ? '已复制' : '复制完整提示词' }}</button></footer>
      </template>
    </dialog>
  </div>
</template>

<style scoped>
.prompt-inspector { display:flex; gap:8px; flex-wrap:wrap; margin-block:12px; }
.prompt-inspector>.btn { width:100%; justify-content:center; font-size:13px; padding:8px 12px; min-height:44px; }
.inspector-tabs { display:flex; gap:12px; margin-top:12px; border-bottom:1px solid var(--border-color); }
.inspector-tabs button { border:0; border-bottom:2px solid transparent; padding:10px 0; background:transparent; font-size:14px; }
.inspector-tabs button[aria-selected="true"] { color:var(--primary); border-bottom-color:var(--primary); }
dialog { width:min(860px,calc(100% - 24px)); max-height:calc(100dvh - 32px); overflow:auto; border:1px solid var(--border-color); border-radius:8px; padding:20px; margin:auto; color:var(--text-main); }
dialog::backdrop { background:#0006; }
header, footer { display:flex; justify-content:space-between; align-items:center; gap:12px; }
h2 { font-size:18px; margin:0; }
label { display:grid; gap:8px; margin:16px 0; }
textarea { width:100%; height:45dvh; resize:vertical; margin:12px 0; padding:12px; font-size:14px; line-height:1.65; border:1px solid var(--border-color); border-radius:4px; }
.references { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.references img { width:64px; height:64px; object-fit:contain; }
p { margin:12px 0; }
@media(max-width:700px) { dialog { padding:14px; } textarea,.field { font-size:16px; } h2 { font-size:16px; } }
</style>
