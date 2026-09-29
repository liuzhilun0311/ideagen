<template>
  <section class="creation-composer" :aria-busy="loading" aria-labelledby="composer-heading">
    <div class="composer-heading">
      <div>
        <h2 id="composer-heading">告诉我你想创作什么</h2>
        <p>主题越具体，生成的大纲越容易直接使用。</p>
      </div>
      <kbd>⌘ / Ctrl + Enter</kbd>
    </div>
    <label for="creation-topic" class="input-label">创作主题</label>
    <textarea
      id="creation-topic"
      :value="modelValue"
      class="field topic-input"
      placeholder="例如：上海周末城市漫步，沿途的建筑、街角咖啡与拍照地点"
      rows="5"
      :disabled="loading || locked"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
      @compositionstart="composing = true"
      @compositionend="composing = false"
      @keydown="handleKeydown"
    />
    <details open class="more-settings">
      <summary class="settings-heading"><SlidersHorizontal :size="18" aria-hidden="true" />补充资料</summary>
      <div class="settings-content">
        <div class="reference-field">
          <div class="reference-heading">
            <label for="creation-reference" class="input-label">参考文本 <span>（选填）</span></label>
            <label class="document-upload">
              <span>导入 Word / Markdown</span>
              <input type="file" aria-label="导入参考文档" accept=".docx,.md,.markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown" :disabled="loading || locked || importing" @change="handleReferenceDocument" />
            </label>
          </div>
          <textarea
            id="creation-reference"
            :value="referenceContent"
            class="field reference-input"
            rows="3"
            placeholder="参考资料、产品卖点或文案素材"
            :disabled="loading || locked"
            @input="emit('update:referenceContent', ($event.target as HTMLTextAreaElement).value)"
          />
          <p v-if="referenceDocumentName" class="field-note">已导入：{{ referenceDocumentName }}，内容已填入参考文本，可继续编辑。</p>
          <p v-if="importing" role="status">正在读取文档…</p>
          <section v-if="pendingDocument" class="document-preview" aria-label="文档提取预览">
            <strong>{{ pendingDocument.name }}</strong>
            <textarea aria-label="提取的文档文字" :value="pendingDocument.text" readonly rows="5" class="field reference-input" />
            <div class="document-actions">
              <button type="button" class="btn btn-secondary" :disabled="loading || locked" @click="applyDocument(false)">追加到参考文本</button>
              <button type="button" class="btn btn-secondary" :disabled="loading || locked" @click="applyDocument(true)">替换参考文本</button>
              <button type="button" class="btn btn-secondary" @click="pendingDocument = null">取消导入</button>
            </div>
          </section>
          <p v-if="referenceError" class="input-error" role="alert">{{ referenceError }}</p>
        </div>
        <div class="reference-field image-reference-field">
          <div class="reference-heading">
            <span id="reference-images-label" class="input-label">参考图片 <span>（选填）</span></span>
            <div class="image-upload-actions">
            <label class="document-upload" title="JPEG、PNG 或 WebP；每张不超过 5 MiB">
              <ImagePlus :size="16" aria-hidden="true" /><span>选择文件</span>
              <input id="creation-images" type="file" aria-label="选择参考图片"
                accept="image/jpeg,image/png,image/webp" multiple
                :disabled="loading || locked" @change="handleImageUpload" />
            </label>
            <details class="reference-mode-picker">
              <summary>图片参考选项({{ referenceMode.length }})<ChevronDown :size="14" aria-hidden="true" /></summary>
              <div class="reference-mode-menu">
                <label v-for="item in referenceOptions" :key="item.value">
                  <input type="checkbox" :disabled="loading || locked" :checked="referenceMode.includes(item.value)" @change="toggleReferenceMode(item.value)">
                  {{ item.label }}
                </label>
              </div>
            </details>
            </div>
          </div>
          <div
            class="image-dropzone"
            :class="{ 'is-dragging': imageDragDepth > 0 }"
            role="group"
            aria-labelledby="reference-images-label"
            :tabindex="loading || locked ? -1 : 0"
            :aria-disabled="loading || locked"
            :aria-describedby="imageError ? 'image-error' : undefined"
            @dragenter.prevent="imageDragDepth++"
            @dragover.prevent="handleImageDrag"
            @dragleave.prevent="imageDragDepth = Math.max(0, imageDragDepth - 1)"
            @drop.prevent="handleImageDrop"
            @paste="handleImagePaste"
          >
          <div v-if="!uploadedImages.length" class="image-dropzone-empty" aria-hidden="true"><ImagePlus :size="28" /></div>
          <ul v-if="uploadedImages.length" class="image-list">
            <li v-for="(image, index) in uploadedImages" :key="image.preview" class="reference-image">
              <button type="button" class="reference-image-preview" :aria-label="`放大参考图片 ${image.file.name}`" @click="openPreview(image)">
                <img :src="image.preview" :alt="`参考图片：${image.file.name}`" />
                <Maximize2 :size="17" aria-hidden="true" />
              </button>
              <div class="image-caption">
                <span :title="image.file.name">{{ image.file.name }}</span>
                <button
                  type="button"
                  class="icon-button"
                  :aria-label="`移除参考图片 ${image.file.name}`"
                  :title="`移除 ${image.file.name}`"
                  :disabled="loading || locked"
                  @click="removeImage(index)"
                ><X :size="18" aria-hidden="true" /></button>
              </div>
            </li>
          </ul>
          </div>
          <p v-if="imageError" id="image-error" class="input-error" role="alert">{{ imageError }}</p>
        </div>
        <slot name="supplement" />
      </div>
    </details>
    <dialog ref="previewDialog" class="reference-preview-dialog" aria-label="参考图片预览" @click="($event.target === previewDialog) && closePreview()">
      <header>
        <strong>{{ previewImage?.file.name }}</strong>
        <button type="button" class="icon-button" aria-label="关闭参考图片预览" title="关闭" @click="closePreview"><X :size="18" /></button>
      </header>
      <img v-if="previewImage" :src="previewImage.preview" :alt="`参考图片：${previewImage.file.name}`" />
    </dialog>
    <div v-if="showActions" class="creation-actions">
      <slot name="before-generate" />
      <button v-if="loading" type="button" class="btn" :disabled="cancelling" @click="emit('cancel')">
        <Square :size="16" aria-hidden="true" />{{ cancelling ? '正在取消' : '取消' }}
      </button>
      <button
        type="button"
        class="btn btn-primary generate-button"
        :disabled="!modelValue.trim() || loading || disabled"
        @click="emit('generate')"
      >
        <LoaderCircle v-if="loading" :size="18" class="spinning" aria-hidden="true" />
        <ArrowUpRight v-else :size="18" aria-hidden="true" />
        {{ loading ? (cancelling ? '等待取消完成' : '正在生成大纲') : buttonText }}
      </button>
    </div>
    <p v-if="loading" class="field-note generation-status" role="status">{{ cancelling ? '正在通知服务端取消…' : '大纲生成中…' }}</p>
  </section>
</template>

<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { ArrowUpRight, ChevronDown, ImagePlus, LoaderCircle, Maximize2, SlidersHorizontal, Square, X } from 'lucide-vue-next'
import { extractReferenceDocument, MAX_REFERENCE_TEXT } from '../../features/referenceDocument'
import { normalizeApiError } from '../../utils/errors'
import { useStudioSession } from '../../stores/studioSession'
import { referenceImageError } from '../../features/referenceImages'

interface UploadedImage { file: File; preview: string }
const props = withDefaults(defineProps<{
  modelValue: string
  loading: boolean
  cancelling?: boolean
  buttonText?: string
  referenceContent?: string
  images?: File[]
  disabled?: boolean
  locked?: boolean
  showActions?: boolean
  referenceMode?: string[]
}>(), { buttonText: '生成大纲', referenceContent: '', disabled: false, cancelling: false, showActions: true, referenceMode: () => [] })
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:referenceContent', value: string): void
  (e: 'generate'): void
  (e: 'cancel'): void
  (e: 'imagesChange', images: File[]): void
  (e: 'update:referenceMode', value: string[]): void
}>()
const composing = ref(false)
const previewImage = ref<UploadedImage | null>(null)
const previewDialog = ref<HTMLDialogElement>()
const referenceOptions = [
  { value: 'style', label: '图片风格' },
  { value: 'subject', label: '图片主体' },
  { value: 'composition', label: '构图关系' },
  { value: 'color', label: '色彩与材质' },
  { value: 'content', label: '图片内容' },
]
function toggleReferenceMode(value: string) {
  if (props.loading || props.locked) return
  const next = props.referenceMode.includes(value)
    ? props.referenceMode.filter(item => item !== value)
    : [...props.referenceMode, value]
  emit('update:referenceMode', next)
}
const imageError = ref('')
const imageDragDepth = ref(0)
const referenceError = ref('')
const referenceDocumentName = ref('')
const importing = ref(false)
const pendingDocument = ref<{ name: string; text: string } | null>(null)
const session = useStudioSession()
let importVersion = 0
let importController: AbortController | null = null
function cancelImport() {
  importVersion++
  importController?.abort()
  importing.value = false
  pendingDocument.value = null
  referenceDocumentName.value = ''
  referenceError.value = ''
}
watch(() => session.revision, cancelImport)
watch(() => props.loading || props.locked, busy => { if (busy) cancelImport() })
onUnmounted(cancelImport)
const uploadedImages = ref<UploadedImage[]>([])

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || (!event.ctrlKey && !event.metaKey)) return
  if (composing.value || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  if (!props.loading && !props.disabled && props.modelValue.trim()) emit('generate')
}

function syncPreviews(files: File[]) {
  const previous = uploadedImages.value
  const next = files.map(file => previous.find(image => image.file === file)
    || { file, preview: URL.createObjectURL(file) })
  previous.filter(image => !next.includes(image)).forEach(image => URL.revokeObjectURL(image.preview))
  uploadedImages.value = next
}
watch(() => props.images, files => {
  if (files) syncPreviews(files)
}, { immediate: true, deep: true })

function addImages(incoming: File[]) {
  if (props.loading || props.locked) return
  const files = uploadedImages.value.map(image => image.file)
  const errors: string[] = []
  for (const file of incoming) {
    const error = referenceImageError(file)
    if (error) {
      errors.push(error)
    } else if (files.some(existing => existing === file || (existing.name === file.name
      && existing.size === file.size && existing.type === file.type && existing.lastModified === file.lastModified))) {
      errors.push(`${file.name}：已添加该图片。`)
    } else {
      files.push(file)
    }
  }
  imageError.value = errors.join(' ')
  syncPreviews(files)
  emit('imagesChange', files)
}

function handleImageUpload(event: Event) {
  const input = event.target as HTMLInputElement
  addImages(Array.from(input.files || []))
  input.value = ''
}

function handleImageDrag(event: DragEvent) {
  if (event.dataTransfer) event.dataTransfer.dropEffect = props.loading || props.locked ? 'none' : 'copy'
}

function handleImageDrop(event: DragEvent) {
  imageDragDepth.value = 0
  addImages(Array.from(event.dataTransfer?.files || []))
}

function handleImagePaste(event: ClipboardEvent) {
  const files = Array.from(event.clipboardData?.items || [])
    .filter(item => item.kind === 'file')
    .map(item => item.getAsFile())
    .filter((file): file is File => !!file)
  if (!files.length) return
  event.preventDefault()
  addImages(files)
}

async function handleReferenceDocument(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || props.loading || props.locked) return
  cancelImport()
  const ticket = ++importVersion
  importController = new AbortController()
  importing.value = true
  referenceError.value = ''
  try {
    const text = await extractReferenceDocument(file, importController.signal)
    if (ticket === importVersion) pendingDocument.value = { name: file.name, text }
  } catch (cause) {
    if (ticket === importVersion) referenceError.value = normalizeApiError(cause, '参考文档读取失败').detail
  } finally {
    if (ticket === importVersion) importing.value = false
  }
}
function applyDocument(replace: boolean) {
  if (!pendingDocument.value || props.loading || props.locked) return
  const next = !replace && props.referenceContent.trim()
    ? `${props.referenceContent}\n\n${pendingDocument.value.text}` : pendingDocument.value.text
  if (next.length > MAX_REFERENCE_TEXT) {
    referenceError.value = '合并后的参考文本超过 100000 字符，请先精简。'
    return
  }
  emit('update:referenceContent', next)
  referenceDocumentName.value = pendingDocument.value.name
  pendingDocument.value = null
  referenceError.value = ''
}

function removeImage(index: number) {
  if (props.loading || props.locked) return
  const files = uploadedImages.value.map(image => image.file).filter((_, position) => position !== index)
  syncPreviews(files)
  imageError.value = ''
  emit('imagesChange', files)
}

function openPreview(image: UploadedImage) {
  previewImage.value = image
  previewDialog.value?.showModal()
}

function closePreview() {
  previewDialog.value?.close()
  previewImage.value = null
}

function clearPreviews() {
  uploadedImages.value.forEach(image => URL.revokeObjectURL(image.preview))
  uploadedImages.value = []
}
onUnmounted(clearPreviews)
defineExpose({ clearPreviews })
</script>

<style scoped>
.creation-composer { min-width: 0; padding: 24px; background:#fff; border:1px solid #e2e5eb; border-radius:8px; }
.composer-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; margin-bottom:20px; }
.composer-heading h2 { margin:0; font-size:18px; line-height:1.4; }
.composer-heading p { margin:6px 0 0; color:#656b78; font-size:13px; }
kbd { flex:0 0 auto; padding:4px 7px; color:#656b78; background:#f7f8fa; border:1px solid #e2e5eb; border-radius:4px; font-size:12px; }
.input-label { display: block; margin-bottom: 10px; color: #252935; font-size: 16px; font-weight: 600; }
.input-label span, .field-note { color: #656b78; font-weight: 400; }
.topic-input, .reference-input { display: block; padding: 16px; font: inherit; font-size: 16px; line-height: 1.7; resize: vertical; background: white; border: 1px solid #d6dae2; border-radius: 8px; }
.topic-input { min-height: 172px; }
.topic-input:focus, .reference-input:focus { outline: 2px solid #315ee8; outline-offset: 2px; }
.more-settings { margin-top: 18px; border-top: 1px solid #e2e5eb; border-bottom: 1px solid #e2e5eb; }
.settings-heading { display: flex; align-items: center; gap: 10px; min-height: 48px; margin:0; color: #505765; font-size: 16px; font-weight:600; }
.settings-content { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; padding: 16px 0 24px; }
.reference-input { width:100%; max-width:100%; box-sizing:border-box; }
.reference-field { min-width: 0; }
.reference-heading { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; }
.reference-heading .input-label { margin-bottom:10px; }
.document-upload { position:relative; display:inline-flex; align-items:center; min-height:40px; padding:0 11px; border:1px solid #cbd5e1; border-radius:6px; background:#f8fafc; color:#334155; font-size:13px; cursor:pointer; }
.document-upload input { position:absolute; width:1px; height:1px; opacity:0; pointer-events:none; }
.document-upload:focus-within { outline:2px solid #315ee8; outline-offset:2px; }
.document-upload:has(input:disabled) { opacity:.5; cursor:not-allowed; }
.document-preview { display:grid; gap:10px; margin-top:12px; }
.document-preview strong { overflow-wrap:anywhere; }
.document-actions { display:flex; flex-wrap:wrap; gap:8px; }
.reference-mode-picker { position:relative; flex:0 0 auto; }
.reference-mode-picker summary { display:flex; align-items:center; gap:3px; min-height:40px; padding:0 7px; border:1px solid #cbd5e1; border-radius:6px; background:#f8fafc; color:#252935; font-size:13px; cursor:pointer; list-style:none; white-space:nowrap; }
.reference-mode-picker summary svg { flex-shrink:0; color:#64748b; }
.reference-mode-picker[open] summary svg { transform:rotate(180deg); }
.reference-mode-picker summary::-webkit-details-marker { display:none; }
.reference-mode-menu { position:absolute; z-index:5; right:0; top:calc(100% + 4px); width:160px; padding:8px; border:1px solid #d6dae2; border-radius:6px; background:#fff; box-shadow:0 8px 20px #172b4d1c; }
.reference-mode-menu label { display:flex; align-items:center; gap:8px; padding:8px 5px; margin:0; color:#334155; font-size:13px; font-weight:400; cursor:pointer; }
.reference-mode-menu input { width:16px; height:16px; accent-color:#315ee8; }
.field-note { margin: 6px 0 12px; font-size: 16px; line-height: 1.6; }
.image-upload-actions { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px; min-width:0; }
.image-upload-actions .document-upload { gap:6px; }
.image-dropzone { min-height:144px; padding:16px; border:1px solid #d6dae2; border-radius:8px; background:#fff; }
.image-dropzone:focus-visible, .image-dropzone.is-dragging:not([aria-disabled="true"]) { outline:2px solid #315ee8; outline-offset:2px; background:#f5f8ff; }
.image-dropzone[aria-disabled="true"] { opacity:.6; }
.image-dropzone-empty { min-height:110px; display:grid; place-items:center; color:#8993a3; }
.image-dropzone .image-list { margin:0; }
.input-error { margin-top: 8px; color: #a62b35; font-size: 16px; overflow-wrap: anywhere; }
.image-list { list-style: none; padding: 0; margin: 16px 0 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 12px; }
.reference-image { min-width: 0; }
.reference-image-preview { position:relative; display:flex; align-items:center; justify-content:center; width:100%; aspect-ratio:4 / 3; padding:0; overflow:hidden; border:1px solid #e2e5eb; border-radius:6px; background:#f7f8fa; cursor:zoom-in; }
.reference-image-preview img { width:100%; height:100%; object-fit:contain; }
.reference-image-preview svg { position:absolute; right:8px; bottom:8px; padding:5px; border-radius:50%; color:#fff; background:#172033b8; }
.reference-preview-dialog { width:min(900px,calc(100% - 24px)); max-height:calc(100dvh - 32px); margin:auto; padding:14px; border:1px solid #cfd6dc; border-radius:8px; background:#fff; }
.reference-preview-dialog::backdrop { background:#151d3266; }
.reference-preview-dialog header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
.reference-preview-dialog header strong { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.reference-preview-dialog>img { display:block; width:100%; max-height:calc(100dvh - 110px); object-fit:contain; background:#f7f8fa; }
.image-caption { display: flex; align-items: center; gap: 4px; min-width: 0; }
.image-caption > span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 16px; }
.icon-button { width: 44px; height: 44px; flex: 0 0 44px; }
.creation-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.generate-button { background: #315ee8; color: white; min-height: 44px; border-radius: 6px; }
.generation-status { text-align: right; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spinning { animation: none; } }
@media (max-width: 700px) {
  .creation-composer { padding: 18px 16px; }
  .composer-heading { flex-direction:column; gap:10px; }
  kbd { display:none; }
}
</style>
