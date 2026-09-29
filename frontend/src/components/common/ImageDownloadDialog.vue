<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Check, CheckCircle2, Copy, Download, X, ArrowLeft } from 'lucide-vue-next'
import { exportImageDownload, prepareImageDownload, type DownloadFormat, type DownloadLocation, type DownloadPage, type DownloadVersion } from '../../utils/imageDownload'
import { getToken } from '../../api/token'

const props = withDefaults(defineProps<{
  visible: boolean
  pages: DownloadPage[]
  loading?: boolean
  loadError?: string
  content?: { titles?: string[]; copywriting?: string; tags?: string[] }
  canProcess?: boolean
}>(), { canProcess: true })
const emit = defineEmits<{ close: []; process: [] }>()
const version = ref<DownloadVersion>('processed')
const format = ref<DownloadFormat>('directory')
const partial = ref(false)
const working = ref(false)
const completed = ref<'saved' | 'submitted' | null>(null)
const doneButton = ref<HTMLButtonElement>()
const savedLocation = ref<DownloadLocation | null>(null)
const copyingLocation = ref(false)
const locationCopied = ref(false)
const locationError = ref('')
const message = ref('')
const failure = ref('')
const panel = ref<HTMLElement>()
const prepared = computed(() => prepareImageDownload(props.pages, version.value))
const ready = computed(() => !props.loading && !props.loadError && prepared.value.files.length > 0
  && (!prepared.value.missing.length || partial.value))
let previousFocus: HTMLElement | null = null
let epoch = 0
watch(() => props.visible, async value => {
  ++epoch
  if (value) {
    working.value = false
    previousFocus = document.activeElement as HTMLElement | null
    version.value = 'processed'
    format.value = 'directory'
    partial.value = false
    message.value = ''
    failure.value = ''
    completed.value = null
    savedLocation.value = null
    copyingLocation.value = false
    locationCopied.value = false
    locationError.value = ''
    await nextTick()
    panel.value?.focus()
  } else previousFocus?.focus?.()
})
watch([version, () => JSON.stringify(props.pages)], () => { partial.value = false })
onBeforeUnmount(() => { ++epoch; previousFocus?.focus?.() })
function close() { if (!working.value) emit('close') }
async function copyLocation() {
  if (!savedLocation.value || copyingLocation.value) return
  const request = epoch
  const location = savedLocation.value
  copyingLocation.value = true
  locationCopied.value = false
  locationError.value = ''
  try {
    await navigator.clipboard.writeText(`${location.directoryName}/${location.relativePath}`)
    if (request === epoch) locationCopied.value = true
  } catch {
    if (request === epoch) locationError.value = '复制失败，请选中上方目录位置手动复制。'
  } finally { if (request === epoch) copyingLocation.value = false }
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.stopPropagation(); close() }
  if (event.key !== 'Tab') return
  const controls = panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]')
  if (!controls?.length) return
  const first = controls[0]!
  const last = controls[controls.length - 1]!
  if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.value)) {
    event.preventDefault(); last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault(); first.focus()
  }
}
async function download() {
  if (working.value || completed.value || !ready.value) return
  const request = epoch
  const token = getToken()
  const valid = () => request === epoch && props.visible && token === getToken()
  working.value = true
  failure.value = ''
  const files = prepared.value.files.map(file => ({ ...file }))
  const content = props.content ? JSON.parse(JSON.stringify(props.content)) : undefined
  try {
    const result = await exportImageDownload({ files, content, format: format.value, stage: value => {
      if (!valid()) throw new Error('下载已取消')
      message.value = value
    } })
    if (!valid()) return
    message.value = result.message
    if (result.status !== 'cancelled') {
      completed.value = result.status
      savedLocation.value = result.status === 'saved' ? result.location : null
      await nextTick()
      doneButton.value?.focus()
    }
  } catch (error) {
    if (!valid()) return
    message.value = ''
    failure.value = error instanceof Error ? error.message : '下载失败'
  } finally { if (valid()) working.value = false }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="download-mask" @click.self="close">
      <section ref="panel" class="download-dialog" role="dialog" aria-modal="true" aria-labelledby="download-title" tabindex="-1" @keydown="keydown">
        <header><h2 id="download-title">{{ completed === 'saved' ? '保存完成' : completed === 'submitted' ? '已提交浏览器下载' : '下载图片' }}</h2><button class="icon-button" aria-label="关闭下载" :disabled="working" @click="close"><X :size="20" /></button></header>
        <div v-if="completed" class="download-success" role="status">
          <CheckCircle2 :size="36" aria-hidden="true" />
          <p>{{ message }}</p>
          <div v-if="savedLocation" class="saved-location">
            <label for="download-location">保存位置（目录名 / 子目录，非完整磁盘路径）</label>
            <div class="location-control">
              <input id="download-location" class="field" readonly :value="`${savedLocation.directoryName}/${savedLocation.relativePath}`" />
              <button type="button" class="icon-button" title="复制目录位置" aria-label="复制目录位置" :disabled="copyingLocation" @click="copyLocation">
                <Check v-if="locationCopied" :size="18" /><Copy v-else :size="18" />
              </button>
            </div>
            <p v-if="locationCopied">目录位置已复制</p>
          </div>
          <p v-if="locationError" class="download-error" role="alert">{{ locationError }}</p>
        </div>
        <template v-else>
        <label class="version-label" for="download-version">图片版本</label>
        <select id="download-version" v-model="version" class="field" :disabled="working">
          <option value="processed">去AI化后的图片（默认）</option>
          <option value="original">原图</option>
          <option value="both">两种都下载</option>
        </select>
        <label class="version-label" for="download-format">保存方式</label>
        <select id="download-format" v-model="format" class="field" :disabled="working">
          <option value="directory">直接保存文件夹（无需解压）</option>
          <option value="zip">ZIP 压缩包</option>
        </select>
        <p v-if="loading" role="status">正在读取图片版本</p>
        <p v-else-if="loadError" role="alert" class="download-error">{{ loadError }}</p>
        <template v-else>
          <p v-if="!pages.length">暂无可下载图片</p>
          <p v-if="prepared.missing.length" class="missing" role="status">第 {{ prepared.missing.map(index => index + 1).join('、') }} 页尚无可用处理图。</p>
          <label v-if="prepared.missing.length && prepared.files.length" class="partial-choice">
            <input v-model="partial" type="checkbox" :disabled="working" />
            {{ version === 'both' ? '仅下载可用原图和已完成处理图' : '仅下载已完成的处理图' }}
          </label>
          <p v-if="prepared.files.length">本次 {{ prepared.files.length }} 张图片</p>
        </template>
        <p v-if="message" role="status">{{ message }}</p>
        <p v-if="failure" role="alert" class="download-error">{{ failure }}</p>
        </template>
        <footer>
          <button v-if="completed" ref="doneButton" class="btn btn-primary" @click="close">完成</button>
          <template v-else>
            <button v-if="canProcess && prepared.missing.length" class="btn btn-secondary" :disabled="working" @click="emit('process')"><ArrowLeft :size="17" />返回图片制作</button>
            <button class="btn btn-primary" :disabled="!ready || working" @click="download"><Download :size="17" />{{ working ? '正在下载' : failure ? '重试下载' : '下载' }}</button>
          </template>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.download-mask { position:fixed; inset:0; z-index:1500; background:#10182066; display:grid; place-items:center; padding:16px; }
.download-dialog { width:100%; max-width:460px; max-height:calc(100dvh - 32px); overflow:auto; padding:24px; background:white; border-radius:8px; color:#252935; }
header,footer { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
h2 { font-size:20px; margin:0; }
.version-label { display:block; margin:20px 0 8px; }
select { width:100%; min-height:44px; }
p,.partial-choice { font-size:14px; line-height:1.7; overflow-wrap:anywhere; }
.partial-choice { display:flex; align-items:flex-start; gap:8px; margin-top:12px; }
input { margin-top:5px; }
footer { margin-top:24px; justify-content:flex-end; }
.missing { color:#825717; }
.download-error { color:#b42335; }
.download-success { padding-top:24px; color:#17634e; }
.download-success p { color:#252935; overflow-wrap:anywhere; }
.saved-location { margin-top:16px; color:#252935; }
.saved-location label { display:block; font-size:13px; line-height:1.6; }
.location-control { display:flex; align-items:center; gap:8px; margin-top:8px; }
.location-control input { width:100%; min-width:0; min-height:44px; margin:0; }
.location-control button { flex:0 0 44px; min-height:44px; }
.btn { min-height:44px; white-space:normal; }
@media(max-width:480px) { .download-dialog { padding:18px; } }
</style>
