<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { FileSearch, Copy, X } from 'lucide-vue-next'
import { useGeneratorStore } from '../../stores/generator'
import { getToken } from '../../api/token'
import { imageParameters } from '../../features/generationOptions'
import { resolveImageStyle, type StyleChoice } from '../../features/styles/catalog'
import { previewImagePrompt, type ImagePromptPreview } from '../../api/imagePrompt'

const props = defineProps<{ index: number; style: StyleChoice; disabled?: boolean; suite?: boolean }>()
const selectedPage = ref(props.index)
const headingId = useId()
const store = useGeneratorStore()
const dialog = ref<HTMLDialogElement>()
const textArea = ref<HTMLTextAreaElement>()
const result = ref<ImagePromptPreview>()
const loading = ref(false)
const error = ref('')
const copied = ref(false)
const mounted = ref(false)
const thumbnails = ref<string[]>([])
const provider = ref('')
let version = 0
function cleanup() { thumbnails.value.forEach(URL.revokeObjectURL); thumbnails.value = [] }
function close() { version++; cleanup(); dialog.value?.close?.() }
async function open() {
  const page = store.outline.pages.find(page => page.index === (props.suite ? selectedPage.value : props.index))
    || (props.suite ? store.outline.pages[0] : undefined)
  if (!page) return
  selectedPage.value = page.index
  const token = getToken()
  const recordId = store.recordId
  const ticket = ++version
  const active = () => ticket === version && token === getToken() && recordId === store.recordId
  result.value = undefined
  error.value = ''
  copied.value = false
  loading.value = true
  cleanup()
  thumbnails.value = store.userImages.map(file => URL.createObjectURL(file))
  provider.value = store.imageModelName || '默认图片模型'
  mounted.value = true
  await nextTick()
  dialog.value?.showModal?.()
  try {
    // Use the same automatic-style resolution as batch and single-page generation.
    const input = { page: { ...page }, topic: store.topic,
      image_style: resolveImageStyle(props.style, store.imageStyle.recommendation),
      image_parameters: imageParameters(store), reference_count: store.userImages.length,
      record_id: recordId, use_reference: store.useCoverAsReference, reference_roles: [...store.referenceRoles],
      generation_preferences: store.outline.generation_preferences, provider_name: store.imageModelName }
    const preview = await previewImagePrompt(input)
    if (active()) result.value = preview
  } catch {
    if (active()) error.value = '预览加载失败，请检查本页内容、图片参数或网络后重试。'
  } finally { if (ticket === version) loading.value = false }
}
async function copy() {
  if (!result.value) return
  try { await navigator.clipboard.writeText(result.value.prompt); copied.value = true }
  catch {
    textArea.value?.focus(); textArea.value?.select()
    copied.value = document.execCommand('copy')
    if (!copied.value) error.value = '浏览器未允许复制，文本已选中。'
  }
}
onBeforeUnmount(() => { version++; cleanup() })
watch(() => store.recordId, close, { flush: 'sync' })
</script>

<template>
  <button type="button" class="btn btn-secondary prompt-preview-button" :disabled="disabled" @click="open"><FileSearch :size="16" />{{ suite ? '预览提示词' : '预览本页提示词' }}</button>
  <Teleport v-if="mounted" to="body">
  <dialog ref="dialog" :aria-labelledby="headingId" @cancel="close" @click="($event.target === dialog) && close()">
    <header><h2 :id="headingId">{{ suite ? '整套图片提示词 · 按页预览' : '本页图片提示词 · 预览' }}</h2><button class="icon-button" aria-label="关闭图片提示词预览" title="关闭" @click="close"><X :size="20" /></button></header>
    <label v-if="suite">页面
      <select v-model="selectedPage" aria-label="预览页面" @change="open">
        <option v-for="page in store.outline.pages" :key="page.index" :value="page.index">第 {{ page.index + 1 }} 页</option>
      </select>
    </label>
    <p v-if="suite">当前整套设置的生成预览，不代表历史实际请求；单页试用设置请在当前页预览。</p>
    <p v-if="loading" role="status">正在加载…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="result">
      <p>{{ provider }} · 本次 1 张</p>
      <dl>
        <div><dt>分辨率 / 比例</dt><dd>{{ result.parameters.resolution }} / {{ result.parameters.aspect_ratio }}</dd></div>
        <div><dt>质量 / 保存格式</dt><dd>{{ result.provider?.quality_applied === false ? '接口默认' : result.parameters.quality }} / {{ result.parameters.output_format.toUpperCase() }}</dd></div>
        <div v-if="result.provider?.gpt_images"><dt>上游请求尺寸</dt><dd>{{ result.gpt_images_parameters.size }}</dd></div>
        <div><dt>参考图片</dt><dd>{{ result.references.count }} 张 · 用户上传 {{ result.references.user_count }} 张 · 首图参考：{{ result.references.cover_count ? '已使用' : '未使用' }}</dd></div>
      </dl>
      <div v-if="thumbnails.length" class="references"><img v-for="(src, index) in thumbnails" :key="index" :src="src" :alt="`参考图片 ${index + 1}`" /></div>
      <textarea ref="textArea" readonly :value="result.prompt" aria-label="完整图片生成提示词"></textarea>
      <footer><span>{{ result.prompt.length }} 字符</span><button class="btn btn-primary" @click="copy"><Copy :size="16" />{{ copied ? '已复制' : '复制完整提示词' }}</button></footer>
    </template>
  </dialog>
  </Teleport>
</template>

<style scoped>
.prompt-preview-button { width:100%; margin-top:8px; min-height:44px; font-size:13px; }
dialog { width:min(860px,calc(100% - 24px)); max-height:calc(100dvh - 32px); overflow:auto; margin:auto; padding:20px; border:1px solid var(--border-color); border-radius:8px; color:var(--text-main); }
dialog::backdrop { background:#0006; }
header,footer { display:flex; align-items:center; justify-content:space-between; gap:12px; }
h2 { font-size:18px; margin:0; }
p { margin:12px 0; }
dl { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; font-size:13px; }
dt { color:var(--text-sub); } dd { margin:4px 0 0; overflow-wrap:anywhere; }
textarea { display:block; width:100%; height:42dvh; padding:12px; margin:14px 0; border:1px solid var(--border-color); border-radius:4px; line-height:1.65; font-size:14px; resize:vertical; }
.references { display:flex; gap:8px; flex-wrap:wrap; }
.references img { width:64px; height:64px; object-fit:contain; }
@media(max-width:700px) { dialog { padding:14px; } textarea { font-size:16px; } h2 { font-size:16px; } dl { grid-template-columns:1fr; } }
</style>
