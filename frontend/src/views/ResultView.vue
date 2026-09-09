<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Check, Copy, Download, ImageOff, RefreshCw, ZoomIn } from 'lucide-vue-next'
import { useGeneratorStore, type GeneratedImage } from '../stores/generator'
import ContentDisplay from '../components/result/ContentDisplay.vue'
import ImageViewer from '../components/common/ImageViewer.vue'
import { runDeaiDownload, downloadAsZip } from '../composables/useDeaiDownload'
import { authHeaders } from '../api/client'
import { getToken } from '../api/token'
import { getOriginalImageUrl, isAuthenticatedImageUrl } from '../utils/imageUrl'

const store = useGeneratorStore()
const router = useRouter()
const selectedIndex = ref<number | null>(null)
const pages = computed(() => {
  const indices = new Set([...store.outline.pages.map(p => p.index), ...store.images.map(i => i.index)])
  return [...indices].sort((a, b) => a - b).map(index => ({
    index,
    image: store.images.find(i => i.index === index),
  }))
})
const selected = computed(() => pages.value.find(p => p.index === selectedIndex.value) ?? pages.value[0])
const generatedImages = computed(() => store.images.filter(i => i.status === 'done' && i.url))
const failedCount = computed(() => pages.value.filter(p => p.image?.status === 'error').length)
const deaiStrength = ref<'light' | 'medium' | 'heavy'>('medium')
const downloadWorking = ref(false)
const downloadStage = ref('')
const downloadMessage = ref('')
const downloadError = ref('')
const imageWorking = ref(false)
const imageMessage = ref('')
const imageError = ref('')
const copiedImageIndex = ref<number | null>(null)
const failedImageAction = ref<{ image: GeneratedImage; action: 'copy' | 'download' } | null>(null)
const brokenUrls = ref(new Set<string>())
const viewerVisible = ref(false)
const viewerSrc = ref('')
const viewerAlt = ref('')
let copyTimer: ReturnType<typeof setTimeout> | undefined
onUnmounted(() => clearTimeout(copyTimer))

function goEdit() { void router.push('/workspace') }
function statusLabel(image?: GeneratedImage) {
  if (image?.status === 'error') return '生成失败'
  if (image?.status === 'generating' || image?.status === 'retrying') return '生成中'
  return image?.url ? '已生成' : '尚未生成'
}
function imageAlt(index: number) {
  return `${store.topic || '作品'} · 第 ${index + 1} 页`
}
function openImage(image: GeneratedImage) {
  imageError.value = ''
  viewerSrc.value = originalUrl(image)
  viewerAlt.value = imageAlt(image.index)
  viewerVisible.value = true
}
function originalUrl(image: GeneratedImage) {
  return getOriginalImageUrl(image.url, getToken())
}
async function originalBlob(image: GeneratedImage) {
  const url = originalUrl(image)
  const authenticated = isAuthenticatedImageUrl(url)
  const response = await fetch(url, {
    headers: authenticated ? authHeaders() : undefined,
    credentials: authenticated ? 'same-origin' : 'omit',
  })
  if (!response.ok) throw new Error(`图片读取失败（${response.status}）`)
  const blob = await response.blob()
  if (!blob.type.startsWith('image/')) throw new Error('返回内容不是图片')
  return blob
}
async function imageAction(image: GeneratedImage, action: 'copy' | 'download') {
  if (!image.url || imageWorking.value) return
  imageWorking.value = true
  imageError.value = ''
  imageMessage.value = action === 'copy' ? '正在复制图片…' : '正在准备图片…'
  copiedImageIndex.value = null
  failedImageAction.value = null
  try {
    if (action === 'copy') {
      const blob = await originalBlob(image)
      await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
      copiedImageIndex.value = image.index
      clearTimeout(copyTimer)
      copyTimer = setTimeout(() => { copiedImageIndex.value = null }, 2000)
      imageMessage.value = `第 ${image.index + 1} 页图片已复制`
    } else {
      const blob = await originalBlob(image)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `rednote_page_${image.index + 1}.${blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png'}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 10000)
      imageMessage.value = `第 ${image.index + 1} 页已提交浏览器下载`
    }
  } catch (error) {
    imageMessage.value = ''
    imageError.value = error instanceof Error ? error.message : '图片操作失败'
    failedImageAction.value = { image, action }
  } finally {
    imageWorking.value = false
  }
}
async function downloadAll(zipOnly = false) {
  if (downloadWorking.value || !generatedImages.value.length) return
  downloadWorking.value = true
  downloadError.value = ''
  downloadMessage.value = ''
  downloadStage.value = '准备下载…'
  const images = generatedImages.value.map(({ index, url }) => ({ index, url }))
  const content = {
    titles: [...store.content.titles],
    copywriting: store.content.copywriting,
    tags: [...store.content.tags],
  }
  const taskId = store.taskId || images[0]?.url.match(/\/api\/images\/([^/]+)\//)?.[1] || ''
  const strength = deaiStrength.value
  try {
    // Keep the picker in the click handler, before asynchronous preparation.
    const picker = (window as Window & {
      showDirectoryPicker?: (options: { mode: string; startIn: string }) => Promise<unknown>
    }).showDirectoryPicker
    const dirHandle = !zipOnly && picker
      ? await picker.call(window, { mode: 'readwrite', startIn: 'downloads' })
      : null
    const options = { taskId, strength, images, content, setStage: (text: string) => { downloadStage.value = text } }
    const result = dirHandle
      ? await runDeaiDownload({ ...options, dirHandle })
      : await downloadAsZip(options)
    if (result.ok) downloadMessage.value = result.message
    else downloadError.value = result.message || '下载失败'
  } catch (error) {
    if (!(error instanceof Error && error.name === 'AbortError')) {
      downloadError.value = error instanceof Error ? error.message : '下载失败'
    }
  } finally {
    downloadWorking.value = false
    downloadStage.value = ''
  }
}
</script>

<template>
  <div class="result-view">
    <header class="result-header">
      <div class="heading">
        <h1>作品预览</h1>
        <p v-if="store.topic" class="topic">{{ store.topic }}</p>
        <p class="summary">共 {{ pages.length }} 页 · 已生成 {{ generatedImages.length }} 张<span v-if="failedCount"> · {{ failedCount }} 页失败</span></p>
      </div>
      <button type="button" class="btn btn-secondary" @click="goEdit"><ArrowLeft :size="18" aria-hidden="true" />返回工作台</button>
    </header>

    <section class="download-section" aria-label="作品下载" :aria-busy="downloadWorking">
      <div class="download-controls">
        <label class="strength-field" for="deai-strength">去AI化强度
          <select id="deai-strength" v-model="deaiStrength" class="field" :disabled="downloadWorking">
            <option value="light">轻度</option><option value="medium">中度</option><option value="heavy">重度</option>
          </select>
        </label>
        <button type="button" class="btn btn-primary" :disabled="downloadWorking || !generatedImages.length" @click="downloadAll()">
          <Download :size="18" aria-hidden="true" />{{ downloadWorking ? '处理中…' : '去AI化下载' }}
        </button>
      </div>
      <p v-if="downloadStage" role="status">{{ downloadStage }}</p>
      <p v-if="downloadMessage" class="download-message" role="status">{{ downloadMessage }}</p>
      <div v-if="downloadError" class="feedback error" role="alert">
        <p>{{ downloadError }}</p>
        <button type="button" class="btn btn-secondary" :disabled="downloadWorking" @click="downloadAll()"><RefreshCw :size="18" aria-hidden="true" />重试下载</button>
        <button type="button" class="btn btn-secondary" :disabled="downloadWorking" @click="downloadAll(true)"><Download :size="18" aria-hidden="true" />去AI化 ZIP 下载</button>
      </div>
    </section>

    <section class="image-section" aria-label="图片预览">
      <p v-if="failedCount" class="partial-note" role="status">{{ failedCount }} 页生成失败，已生成的图片仍可预览与下载。</p>
      <div v-if="!pages.length" class="empty-state">
        <ImageOff :size="32" aria-hidden="true" />
        <h2>暂无图片</h2>
        <button type="button" class="btn btn-secondary" @click="goEdit"><ArrowLeft :size="18" aria-hidden="true" />返回工作台</button>
      </div>
      <template v-else-if="selected">
        <div class="preview-toolbar">
          <h2>第 {{ selected.index + 1 }} 页 <span>{{ statusLabel(selected.image) }}</span></h2>
          <div v-if="selected.image?.url" class="image-actions">
            <button type="button" class="icon-button" title="放大图片" aria-label="放大图片" @click="openImage(selected.image)"><ZoomIn :size="20" aria-hidden="true" /></button>
            <button type="button" class="icon-button" title="复制图片" aria-label="复制图片" :disabled="imageWorking" @click="imageAction(selected.image, 'copy')"><Check v-if="copiedImageIndex === selected.index" :size="20" aria-hidden="true" /><Copy v-else :size="20" aria-hidden="true" /></button>
            <button type="button" class="icon-button" title="下载单张原图" aria-label="下载单张原图" :disabled="imageWorking" @click="imageAction(selected.image, 'download')"><Download :size="20" aria-hidden="true" /></button>
          </div>
        </div>
        <div v-if="selected.image?.status === 'error'" class="page-error error" role="status">
          <p>{{ selected.image.error || '此页生成失败' }}</p>
          <button type="button" class="btn btn-secondary" @click="goEdit"><ArrowLeft :size="18" aria-hidden="true" />返回编辑</button>
        </div>
        <button v-if="selected.image?.url && !brokenUrls.has(selected.image.url)" type="button" class="preview-image" :aria-label="`放大第 ${selected.index + 1} 页图片`" @click="openImage(selected.image)">
          <img :src="selected.image.url" :alt="imageAlt(selected.index)" @error="brokenUrls.add(selected.image.url)" />
        </button>
        <div v-else class="empty-state">
          <ImageOff :size="32" aria-hidden="true" />
          <p>{{ selected.image?.url ? '图片加载失败' : statusLabel(selected.image) }}</p>
          <button v-if="selected.image?.url" type="button" class="btn btn-secondary" @click="brokenUrls.delete(selected.image.url)"><RefreshCw :size="18" aria-hidden="true" />重新加载</button>
          <button v-else-if="selected.image?.status !== 'error'" type="button" class="btn btn-secondary" @click="goEdit"><ArrowLeft :size="18" aria-hidden="true" />返回工作台</button>
        </div>
        <p v-if="imageMessage" role="status">{{ imageMessage }}</p>
        <div v-if="imageError" class="feedback error" role="alert">
          <p>{{ imageError }}</p>
          <button v-if="failedImageAction" type="button" class="btn btn-secondary" :disabled="imageWorking" @click="imageAction(failedImageAction.image, failedImageAction.action)"><RefreshCw :size="18" aria-hidden="true" />重试</button>
        </div>
        <nav class="thumbnails" aria-label="选择预览页">
          <button v-for="page in pages" :key="page.index" type="button" class="thumbnail" :aria-current="selected.index === page.index ? 'true' : undefined" :aria-label="`第 ${page.index + 1} 页，${statusLabel(page.image)}`" @click="selectedIndex = page.index">
            <img v-if="page.image?.url && !brokenUrls.has(page.image.url)" :src="page.image.url" :alt="imageAlt(page.index)" loading="lazy" @error="brokenUrls.add(page.image.url)" />
            <span v-else class="thumbnail-placeholder"><ImageOff :size="22" aria-hidden="true" /></span>
            <span>{{ page.index + 1 }} · {{ statusLabel(page.image) }}</span>
          </button>
        </nav>
      </template>
    </section>
    <ContentDisplay />
    <ImageViewer :visible="viewerVisible" :src="viewerSrc" :alt="viewerAlt" @close="viewerVisible = false" />
  </div>
</template>

<style scoped>
.result-view { box-sizing: border-box; width: 100%; max-width: 1200px; margin: 0 auto; padding: 32px 24px 64px; color: #252935; overflow-wrap: anywhere; }
.result-header, .download-controls, .preview-toolbar, .image-actions, .feedback, .page-error { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.result-header { justify-content: space-between; align-items: flex-start; padding-bottom: 24px; }
.heading { flex: 1 1 280px; min-width: 0; }
h1 { font-size: 28px; line-height: 1.3; margin: 0 0 12px; }
h2 { font-size: 18px; margin: 0; }
p { font-size: 16px; line-height: 1.65; margin: 8px 0; }
.summary, h2 span { color: #606674; }
h2 span { font-size: 14px; font-weight: 400; margin-left: 8px; }
.download-section { border-block: 1px solid #dfe2e8; padding: 20px 0; }
.strength-field { display: flex; align-items: center; gap: 12px; font-size: 16px; }
.strength-field select { width: 100px; }
.download-message { white-space: pre-wrap; }
.feedback p { flex-basis: 100%; }
.error { color: #a82936; }
.partial-note { color: #8b5010; margin-bottom: 20px; }
.image-section { padding: 28px 0; min-width: 0; }
.preview-toolbar { justify-content: space-between; margin-bottom: 16px; }
.image-actions { gap: 4px; }
.preview-image { display: flex; width: 100%; height: min(65vh, 680px); min-height: 260px; align-items: center; justify-content: center; padding: 12px; background: #f7f8fa; border: 0; cursor: zoom-in; }
.preview-image img { display: block; width: 100%; height: 100%; object-fit: contain; }
.empty-state { min-height: 240px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; text-align: center; background: #f7f8fa; padding: 28px 16px; }
.empty-state svg { color: #606674; }
.page-error { margin-bottom: 16px; }
.page-error p { flex: 1 1 220px; }
.thumbnails { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 12px; margin-top: 20px; }
.thumbnail { display: flex; flex-direction: column; gap: 8px; min-width: 0; padding: 6px; border: 1px solid #dfe2e8; border-radius: 8px; background: white; color: #252935; cursor: pointer; font: inherit; }
.thumbnail[aria-current="true"] { border-color: #315ee8; box-shadow: inset 0 0 0 1px #315ee8; }
.thumbnail img, .thumbnail-placeholder { display: flex; align-items: center; justify-content: center; width: 100%; height: 108px; object-fit: contain; background: #f7f8fa; }
.thumbnail > span:last-child { font-size: 14px; line-height: 1.5; }
.btn { min-height: 44px; max-width: 100%; white-space: normal; overflow-wrap: anywhere; }
.icon-button { display: inline-flex; justify-content: center; align-items: center; width: 44px; height: 44px; flex: 0 0 44px; }
button:focus-visible, select:focus-visible { outline: 3px solid #315ee8; outline-offset: 3px; }
button:disabled { cursor: not-allowed; opacity: .55; }
@media (max-width: 700px) {
  .result-view { padding: 24px 16px 40px; }
  h1 { font-size: 24px; }
  .preview-image { height: 440px; max-height: 65vh; min-height: 240px; padding: 8px; }
  .thumbnails { grid-template-columns: repeat(auto-fill, minmax(88px, 1fr)); gap: 8px; }
}
</style>
