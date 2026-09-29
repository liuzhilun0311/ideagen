<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Copy, Download, Maximize2, RotateCw, WandSparkles } from 'lucide-vue-next'
import type { ProcessingPage, ProcessingStrength, ProcessingVersion } from '../../api/postprocessing'
import ImageDownloadDialog from '../common/ImageDownloadDialog.vue'
import { fetchDownloadFiles } from '../../utils/imageDownload'

const props = defineProps<{
  page?: ProcessingPage
  index: number
  originalUrl: string
  defaultStrength?: ProcessingStrength
  submitting?: boolean
  loading?: boolean
  loadError?: string
}>()
const emit = defineEmits<{
  preview: [src: string, version: ProcessingVersion]
  process: [strength: ProcessingStrength, force: boolean]
  adopt: [version: ProcessingVersion, sourceRevision: string]
}>()
const mode = ref<ProcessingVersion | 'compare'>(props.page?.adopted === 'processed' && props.page.processed_url ? 'processed' : 'original')
const viewChosen = ref(false)
const copying = ref(false)
const copyMessage = ref('')
const mobileVersion = ref<ProcessingVersion>('original')
const strength = ref<ProcessingStrength>(props.defaultStrength || 'medium')
const chosenStrength = ref(false)
const downloading = ref(false)
const downloadPages = computed(() => [{
  index: props.index,
  original_url: props.page?.original_url || props.originalUrl,
  processed_url: props.page?.processed_url || null,
}])
watch(() => props.defaultStrength, value => { if (!chosenStrength.value && value) strength.value = value })
watch([() => props.index, () => props.page?.source_revision], () => {
  mode.value = props.page?.adopted === 'processed' && props.page.processed_url ? 'processed' : 'original'
  viewChosen.value = false
  copyMessage.value = ''
  mobileVersion.value = 'original'
  downloading.value = false
})
watch(() => props.page?.processed_url, value => {
  if (!value) { mode.value = 'original'; mobileVersion.value = 'original' }
})
watch([() => props.page?.adopted, () => props.page?.processed_url], () => {
  if (!viewChosen.value) mode.value = props.page?.adopted === 'processed' && props.page.processed_url ? 'processed' : 'original'
})
function view(version: ProcessingVersion | 'compare') {
  mode.value = version
  viewChosen.value = true
}
async function copy(url: string, version: ProcessingVersion) {
  if (copying.value) return
  copying.value = true
  copyMessage.value = ''
  const revision = props.page?.source_revision
  const index = props.index
  try {
    const [file] = await fetchDownloadFiles([{ index, version, url, name: 'image.png' }])
    await navigator.clipboard.write([new ClipboardItem({ [file!.blob.type]: file!.blob })])
    if (index === props.index && revision === props.page?.source_revision) copyMessage.value = version === 'original' ? '原图已复制' : '处理图已复制'
  } catch {
    if (index === props.index && revision === props.page?.source_revision) copyMessage.value = '复制失败，浏览器未提供剪贴板权限，可使用下载保存图片。'
  } finally { copying.value = false }
}
const strengths = { light: '轻度', medium: '中度', heavy: '重度' }
const statuses = { idle: '未处理', queued: '排队中', processing: '处理中', done: '已处理', error: '处理失败' }
const running = computed(() => props.page && ['queued', 'processing'].includes(props.page.status))
const versions = computed(() => [
  { version: 'original' as const, label: '原图', url: props.page?.original_url || props.originalUrl },
  { version: 'processed' as const, label: '处理图', url: props.page?.processed_url },
].filter(item => item.url && (mode.value === 'compare' || mode.value === item.version)))
function process() {
  if (!props.page || running.value || props.submitting) return
  emit('process', strength.value, !!props.page.processed_url)
}
</script>

<template>
  <div class="image-versions">
    <div class="version-header">
      <div class="version-tabs" role="group" aria-label="查看图片版本">
        <button :aria-pressed="mode === 'original'" @click="view('original')">原图</button>
        <button :disabled="!page?.processed_url" :aria-pressed="mode === 'processed'" @click="view('processed')">处理图</button>
        <button :disabled="!page?.processed_url" :aria-pressed="mode === 'compare'" @click="view('compare')">对比</button>
      </div>
      <span class="adopted">当前采用：{{ page?.adopted === 'processed' ? '处理图' : '原图' }}<template v-if="page?.adopted === 'processed' && page.strength"> · {{ strengths[page.strength] }}</template></span>
      <button class="icon-button" title="下载当前图片" aria-label="下载当前图片" @click="downloading = true"><Download :size="17" /></button>
    </div>
    <div v-if="mode === 'compare'" class="mobile-version-tabs" role="group" aria-label="对比图片切换">
      <button :aria-pressed="mobileVersion === 'original'" @click="mobileVersion = 'original'">原图</button>
      <button :aria-pressed="mobileVersion === 'processed'" @click="mobileVersion = 'processed'">处理图</button>
    </div>
    <div class="version-canvases" :class="{ comparing: mode === 'compare' }">
      <figure v-for="item in versions" :key="item.version" :class="{ 'mobile-inactive': mode === 'compare' && mobileVersion !== item.version }">
        <button class="version-image" :aria-label="`放大第 ${index + 1} 页${item.label}`" @click="emit('preview', item.url!, item.version)">
          <img :src="item.url!" :alt="`第 ${index + 1} 页${item.label}`" />
        </button>
        <figcaption>
          <span>{{ item.label }}<template v-if="item.version === 'processed' && page?.strength"> · {{ strengths[page.strength] }}</template></span>
          <div class="version-actions">
            <button class="icon-button" :title="`复制${item.label}`" :aria-label="`复制${item.label}`" :disabled="copying" @click="copy(item.url!, item.version)"><Copy :size="17" /></button>
            <button class="icon-button" :title="`预览${item.label}`" :aria-label="`预览${item.label}`" @click="emit('preview', item.url!, item.version)"><Maximize2 :size="17" /></button>
            <button v-if="page" class="adopt-button" :disabled="page.adopted === item.version"
              :aria-label="`采用${item.label}`" @click="emit('adopt', item.version, page.source_revision)">
              <Check :size="15" />{{ page.adopted === item.version ? '已采用' : '采用' }}
            </button>
          </div>
        </figcaption>
      </figure>
    </div>
    <div class="single-processing">
      <p v-if="copyMessage" class="copy-message" role="status">{{ copyMessage }}</p>
      <label>处理强度
        <select v-model="strength" aria-label="当前图片处理强度" @change="chosenStrength = true">
          <option value="light">轻度</option><option value="medium">中度</option><option value="heavy">重度</option>
        </select>
      </label>
      <button class="btn btn-secondary" :disabled="!page || running || submitting" @click="process">
        <RotateCw v-if="page?.processed_url" :size="16" /><WandSparkles v-else :size="16" />
        {{ page?.processed_url ? '重新处理' : page?.status === 'error' ? '重试处理' : '处理当前图片' }}
      </button>
      <span role="status" :class="{ failed: page?.status === 'error' }">{{ submitting ? '正在提交' : page ? statuses[page.status] : '正在读取版本' }}<template v-if="page?.status === 'done' && page.strength"> · {{ strengths[page.strength] }}</template></span>
      <p v-if="page?.error" class="processing-error" role="alert">{{ page.error }}</p>
    </div>
    <ImageDownloadDialog :visible="downloading" :pages="downloadPages" :loading="loading" :load-error="loadError"
      @close="downloading = false" @process="downloading = false" />
  </div>
</template>

<style scoped>
.image-versions { min-width:0; }
.version-header { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; padding:14px 20px; background:#fff; }
.version-tabs,.mobile-version-tabs { display:flex; gap:0; }
.version-tabs button,.mobile-version-tabs button { min-height:36px; min-width:56px; border:1px solid #d8dde5; background:#fff; color:#485469; font:inherit; font-size:13px; padding:7px 10px; }
.version-tabs button+button,.mobile-version-tabs button+button { border-left:0; }
button[aria-pressed=true] { background:#e7f2ef; color:#17634e; }
.adopted { font-size:12px; color:#4e635b; overflow-wrap:anywhere; }
.version-canvases { display:grid; grid-template-columns:minmax(0,1fr); background:#f0f2f5; padding:20px; gap:16px; }
.version-canvases.comparing { grid-template-columns:repeat(2,minmax(0,1fr)); }
figure { min-width:0; margin:0; }
.version-image { width:100%; height:420px; padding:0; border:0; background:transparent; display:flex; justify-content:center; align-items:center; }
.version-image img { display:block; max-width:100%; max-height:100%; object-fit:contain; }
figcaption { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; min-height:44px; margin-top:8px; font-size:12px; }
.version-actions { display:flex; align-items:center; gap:6px; }
.version-actions .icon-button { background:transparent; border:0; }
.adopt-button { display:flex; gap:4px; align-items:center; min-height:36px; padding:5px 8px; border:1px solid #b9cfc7; border-radius:4px; color:#17634e; background:#fff; font:inherit; }
.single-processing { display:flex; align-items:center; flex-wrap:wrap; gap:10px 14px; padding:16px 20px; border-bottom:1px solid var(--border-color); font-size:13px; }
.single-processing label { display:flex; align-items:center; gap:8px; }
select { min-height:36px; border:1px solid var(--border-color); border-radius:5px; background:#fff; padding:6px 22px 6px 8px; font:inherit; }
.single-processing .btn { font-size:13px; padding:7px 12px; min-height:38px; height:auto; }
.single-processing>span { color:var(--text-sub); }
.processing-error,.single-processing>.failed { color:#af352e; }
.processing-error { flex-basis:100%; margin:0; line-height:1.7; overflow-wrap:anywhere; }
.copy-message { flex-basis:100%; margin:0; overflow-wrap:anywhere; }
.mobile-version-tabs { display:none; }
@media(max-width:700px) {
  .version-header,.single-processing { padding:14px 16px; }
  .version-canvases,.version-canvases.comparing { grid-template-columns:minmax(0,1fr); padding:16px; }
  .version-image { height:360px; }
  .mobile-version-tabs { display:flex; padding:0 16px 12px; }
  .mobile-inactive { display:none; }
}
</style>
