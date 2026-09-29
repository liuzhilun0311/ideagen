<template>
  <!-- 图片画廊模态框 -->
  <div v-if="visible && record && !accessUnavailable" class="modal-fullscreen" @click="$emit('close')">
    <div class="modal-body" @click.stop>
      <!-- 头部区域 -->
      <div class="modal-header">
        <div style="flex: 1;">
          <!-- 标题区域 -->
          <div class="title-section">
            <h3
              class="modal-title"
              :class="{ 'collapsed': !titleExpanded && record.title.length > 80 }"
            >
              {{ record.title }}
            </h3>
            <button
              v-if="record.title.length > 80"
              class="title-expand-btn"
              @click="titleExpanded = !titleExpanded"
            >
              {{ titleExpanded ? '收起' : '展开' }}
            </button>
          </div>
          <div class="modal-meta">
            <span v-if="record.owner">作者：{{ record.owner.username }}</span>
            <span>{{ record.outline.pages.length }} 张图片 · {{ formattedDate }}</span>
            <span v-if="record.images?.task_id" class="task-id-chip" title="与任务关联的ID（下载文件夹名即为此ID）">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
              任务: {{ record.images.task_id }}
            </span>
          </div>
        </div>
        <div class="header-actions">
          <button v-if="!readonly && record.can_edit === true" class="btn btn-info btn-small edit-btn" @click="$emit('edit', record.id)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
            编辑
          </button>
          <button class="close-icon" @click="$emit('close')">×</button>
        </div>
      </div>

      <!-- Tab栏：查看大纲 / 查看图片 / 查看文案 -->
      <div class="tabs-wrap">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'outline' }"
          @click="activeTab = 'outline'"
        >
          查看大纲
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'images' }"
          @click="activeTab = 'images'"
        >
          查看图片
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'copy' }"
          @click="activeTab = 'copy'"
        >
          查看文案
        </button>
      </div>

      <div v-if="readError" class="preview-error" role="alert">
        <span>{{ readError }}</span>
        <button class="mini-btn" type="button" :disabled="retrying || processing.loading.value" @click="retryImages">重试读取图片</button>
      </div>

      <!-- Tab内容区 -->
      <div class="tab-content">
        <!-- Tab1：查看大纲 -->
        <div v-if="activeTab === 'outline'" class="outline-panel">
          <div class="panel-toolbar">
            <span class="panel-title">原始大纲</span>
            <button class="mini-btn" type="button" @click="copyOutline">
              {{ copiedOutline ? '已复制' : '复制' }}
            </button>
          </div>
          <pre class="outline-pre">{{ record.outline.raw }}</pre>
        </div>

        <!-- Tab2：查看图片 -->
        <div v-if="activeTab === 'images'" class="images-panel">
          <div class="panel-toolbar">
            <span class="panel-title">点击图片可放大查看</span>
          </div>
          <div v-if="imagesList.length" class="modal-gallery-grid">
            <div
              v-for="img in imagesList"
              :key="img.filename"
              class="modal-img-item"
            >
              <div
                class="modal-img-preview"
                @click="openImage(img.filename, img.index)"
              >
                <img
                  :key="imageAttempt"
                  :src="displayUrl(img.filename, img.index)"
                  :alt="pageLabel(img)"
                  loading="lazy"
                  decoding="async"
                  @error="imageError = '图片读取失败，请重试'"
                />
              </div>
              <div class="img-footer">
                <span>{{ pageLabel(img) }}</span>
                <div class="img-actions">
                  <span
                    class="img-link"
                    @click.stop="copyImage(img.filename, img.index)"
                  >
                    {{ copiedImageFilename === img.filename ? '已复制' : '复制' }}
                  </span>
                  <span
                    v-if="img.index !== null"
                    class="img-link"
                    @click.stop="$emit('download', img.filename, img.index)"
                  >
                    下载
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-tip">
            该记录暂无已生成的图片
          </div>
        </div>

        <!-- Tab3：查看文案 -->
        <div v-if="activeTab === 'copy'" class="copy-panel">
          <div v-if="noteContent" class="content-block">
            <div class="panel-toolbar">
              <span class="panel-title">📝 小红书文案</span>
              <button class="mini-btn" type="button" @click="copyContent">
                {{ copiedContent ? '已复制' : '复制' }}
              </button>
            </div>
            <div class="section">
              <div class="label">标题</div>
              <div class="title-list">
                <div v-for="(t, idx) in noteContent.titles ?? []" :key="idx" class="title-item">
                  <span class="tag-mark">{{ idx === selectedTitleIndex(noteContent.titles, noteContent.selected_title_index) ? "[已选]" : "[备选]" }}</span>
                  <span>{{ t }}</span>
                </div>
              </div>
            </div>
            <div class="section">
              <div class="label">正文</div>
              <div class="copy-text">{{ noteContent.copywriting || "暂无正文" }}</div>
            </div>
            <div class="section">
              <div class="label">标签</div>
              <div class="tag-list">
                <span v-for="tag in noteContent.tags ?? []" :key="tag" class="hash-tag">#{{ tag }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-tip">
            该记录暂无文案内容（标题/正文/标签）
          </div>
        </div>
      </div>
    </div>
  </div>

  <ImageViewer
    :visible="viewerVisible"
    :src="viewerSrc"
    :alt="viewerAlt"
    @close="viewerVisible = false"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount, onDeactivated } from 'vue'
import ImageViewer from '../common/ImageViewer.vue'
import { getImageUrl } from '../../api'
import { authHeaders } from '../../api/client'
import { withToken } from '../../api/image'
import { usePostprocessing } from '../../composables/usePostprocessing'
import { useAuthStore } from '../../stores/auth'
import type { HistoryPermissions } from '../../api/types'
import { normalizeApiError } from '../../utils/errors'
import { publicationText, selectedTitleIndex } from '../../utils/publicationContent'

interface ViewingRecord extends HistoryPermissions {
  id: string
  title: string
  updated_at: string
  outline: {
    raw: string
    pages: Array<{ type: string; content: string }>
  }
  images: {
    task_id: string | null
    generated: string[]
  }
  content?: NoteContent
}

interface NoteContent {
  selected_title_index?: number
  titles: string[]
  copywriting: string
  tags: string[]
}

const props = defineProps<{
  visible: boolean
  record: ViewingRecord | null
  content?: NoteContent
  readonly?: boolean
}>()
const auth = useAuthStore()
const processing = usePostprocessing(computed(() => props.visible ? props.record?.id || null : null))
function displayUrl(filename: string, index: number | null) {
  const page = processing.pages.value.find(item => item.index === index)
  if (page) return withToken(page.processed_url || page.original_url)
  return props.record?.images.task_id ? getImageUrl(props.record.images.task_id, filename, false) : ''
}

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'edit', id: string): void
  (e: 'download', filename: string, index: number): void
  (e: 'unavailable'): void
}>()

// tab状态：outline / images / copy，默认打开查看图片
const activeTab = ref<'outline' | 'images' | 'copy'>('images')
const titleExpanded = ref(false)
const viewerVisible = ref(false)
const viewerSrc = ref('')
const viewerAlt = ref('')
const copiedImageFilename = ref<string | null>(null)
const copiedOutline = ref(false)
const copiedContent = ref(false)
const accessUnavailable = ref(false)
const imageError = ref('')
const imageAttempt = ref(0)
const retrying = ref(false)
const readError = computed(() => processing.error.value?.detail || imageError.value)
let epoch = 0
function reset() {
  ++epoch
  viewerVisible.value = false
  viewerSrc.value = ''
  copiedImageFilename.value = null
  copiedOutline.value = false
  copiedContent.value = false
  activeTab.value = 'images'
  imageError.value = ''
  retrying.value = false
}
function unavailable() { accessUnavailable.value = true; reset(); emit('unavailable') }
function isAccessFailure(status: number) { return [401, 403, 404].includes(status) }
watch(() => processing.error.value, value => { if (value && isAccessFailure(value.status)) unavailable() }, { flush: 'sync' })
watch([() => props.record?.id, () => props.visible], () => { accessUnavailable.value = false; reset() }, { flush: 'sync' })
watch([() => auth.token, () => auth.user?.id, () => auth.sessionRevision], () => { accessUnavailable.value = true; reset(); emit('close') }, { flush: 'sync' })
onBeforeUnmount(reset)
onDeactivated(reset)

// 图片列表（兼容 images 字段可能缺失的情况）
interface GalleryImage { filename: string; index: number | null }
const imagesList = computed<GalleryImage[]>(() => {
  return (props.record?.images?.generated || []).filter(Boolean).map(filename => {
    // Generated lists omit missing pages; array positions are not page identities.
    const match = /(?:^|[/\\])(\d+)\.(?:png|jpe?g|webp)$/i.exec(filename)
    const index = match ? Number(match[1]) : null
    return { filename, index: index !== null && Number.isSafeInteger(index) ? index : null }
  })
})
function pageLabel(image: GalleryImage) { return image.index === null ? image.filename : `第 ${image.index + 1} 页` }
async function retryImages() {
  if (retrying.value || processing.loading.value || accessUnavailable.value) return
  const request = epoch
  retrying.value = true
  try {
    await processing.refresh()
    if (request !== epoch || accessUnavailable.value) return
    if (!processing.error.value) { imageError.value = ''; ++imageAttempt.value }
  } catch (cause) {
    if (request !== epoch) return
    const error = normalizeApiError(cause, '读取图片失败')
    if (isAccessFailure(error.status)) unavailable()
    else imageError.value = error.detail
  } finally { if (request === epoch) retrying.value = false }
}

// 统一文案内容来源：优先使用记录中持久化的 content，否则回退到传入的 content prop
const noteContent = computed<NoteContent | null>(() => {
  if (accessUnavailable.value) return null
  const c = (props.record && props.record.content) || props.content
  return c || null
})

const openImage = (filename: string, index: number | null) => {
  if (accessUnavailable.value || !props.record || !props.record.images?.task_id) return
  viewerSrc.value = displayUrl(filename, index)
  viewerAlt.value = pageLabel({ filename, index })
  viewerVisible.value = true
}

// 复制单张图片到剪贴板
const copyImage = async (filename: string, index: number | null) => {
  if (accessUnavailable.value || !props.record || !props.record.images?.task_id) return
  const request = epoch
  try {
    const response = await fetch(displayUrl(filename, index), { headers: authHeaders() })
    if (request !== epoch) return
    if ([401, 403, 404].includes(response.status)) { unavailable(); return }
    if (!response.ok) throw new Error('图片读取失败')
    const blob = await response.blob()
    if (request !== epoch) return
    if (!blob.type.startsWith('image/')) throw new Error('返回内容不是图片')
    await navigator.clipboard.write([new ClipboardItem({ [blob.type || 'image/png']: blob })])
    if (request !== epoch) return
    copiedImageFilename.value = filename
    window.setTimeout(() => {
      if (copiedImageFilename.value === filename) copiedImageFilename.value = null
    }, 1500)
  } catch (e: any) {
    if (request !== epoch) return
    console.error('复制图片失败:', e)
    alert('复制图片失败，请稍后重试')
  }
}

// 复制大纲文本
const copyOutline = async () => {
  if (accessUnavailable.value || !props.record) return
  const request = epoch
  try {
    await navigator.clipboard.writeText(props.record.outline.raw || '')
    if (request !== epoch) return
    copiedOutline.value = true
    window.setTimeout(() => { copiedOutline.value = false }, 1500)
  } catch (e: any) {
    if (request !== epoch) return
    console.error('复制大纲失败:', e)
    alert('复制大纲失败，请稍后重试')
  }
}

// 复制文案（标题 + 正文 + 标签）
const copyContent = async () => {
  if (!noteContent.value) return
  const request = epoch
  const txt = publicationText(noteContent.value, noteContent.value.selected_title_index)
  try {
    await navigator.clipboard.writeText(txt)
    if (request !== epoch) return
    copiedContent.value = true
    window.setTimeout(() => { copiedContent.value = false }, 1500)
  } catch (e: any) {
    if (request !== epoch) return
    console.error('复制文案失败:', e)
    alert('复制文案失败，请稍后重试')
  }
}

const formattedDate = computed(() => {
  if (!props.record) return ''
  const d = new Date(props.record.updated_at)
  return `${d.getMonth() + 1}/${d.getDate()}`
})
</script>

<style scoped>
.preview-error { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 12px 20px; color: #b42335; background: #fff5f5; font-size: 13px; flex-shrink: 0; }
.preview-error span { overflow-wrap: anywhere; min-width: 0; flex: 1; }
.modal-fullscreen {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.modal-body {
  background: white;
  width: 100%;
  max-width: 1000px;
  height: 90vh;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  padding: 20px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-shrink: 0;
  gap: 20px;
}

.title-section {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 4px;
}

.modal-title {
  flex: 1;
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  color: #1a1a1a;
  word-break: break-word;
  transition: max-height 0.3s ease;
}

.modal-title.collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.title-expand-btn {
  flex-shrink: 0;
  padding: 2px 8px;
  background: #f0f0f0;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  color: #666;
  transition: all 0.2s;
  margin-top: 2px;
}
.title-expand-btn:hover {
  background: var(--primary, #ff2442);
  color: white;
}

.modal-meta {
  font-size: 12px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  overflow-wrap: anywhere;
  margin-top: 8px;
}

.task-id-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 20px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  cursor: default;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-shrink: 0;
}

.close-icon {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  padding: 0;
  line-height: 1;
}
.close-icon:hover {
  color: #333;
}

/* Tab样式 */
.tabs-wrap {
  display: flex;
  border-bottom: 1px solid #eee;
  flex-shrink:0;
}
.tab-btn {
  padding:12px 20px;
  border:none;
  background:transparent;
  font-size:14px;
  cursor:pointer;
  color:#666;
  border-bottom:2px solid transparent;
  transition:all 0.2s;
}
.tab-btn.active {
  color:#2563eb;
  border-bottom-color:#2563eb;
  font-weight:600;
}
.tab-btn:hover:not(.active) {
  background:#f7f8fa;
}

.tab-content {
  flex:1;
  overflow:hidden;
}

/* 查看大纲面板 */
.outline-panel {
  height:100%;
  overflow-y:auto;
  padding:20px;
}
.outline-raw {
  margin-bottom:20px;
}
.outline-pre {
  background:#f7f8fa;
  padding:12px;
  border-radius:6px;
  white-space:pre-wrap;
  font-size:13px;
}

/* 查看图片面板 */
.images-panel {
  height:100%;
  display:flex;
  flex-direction:column;
  overflow:hidden;
}
.images-panel .panel-toolbar {
  padding: 16px 20px 0;
  margin-bottom: 12px;
}

/* 查看文案面板 */
.copy-panel {
  height:100%;
  overflow-y:auto;
  padding:20px;
}

.empty-tip {
  padding: 60px 20px;
  text-align: center;
  color: #999;
  font-size: 14px;
}

/* 面板工具栏（标题 + 复制按钮） */
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
}
.mini-btn {
  padding: 4px 14px;
  border: 1px solid #d1d5db;
  border-radius: 50px;
  background: #fff;
  color: #374151;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.mini-btn:hover {
  background: #eff6ff;
  border-color: #2563eb;
  color: #2563eb;
}

.content-block {
  padding: 16px;
  background-color: #f9fafb;
  border-radius: 8px;
  border: 1px solid #eee;
}

.section {
  margin-bottom: 12px;
}

.label {
  font-size: 13px;
  color: #666;
  margin-bottom: 4px;
}

.title-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title-item {
  font-size: 14px;
}

.tag-mark {
  color: #2563eb;
  font-weight: 600;
  margin-right: 6px;
}

.copy-text {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.6;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.hash-tag {
  font-size: 13px;
  color: #059669;
}

.modal-gallery-grid {
  flex: 1;
  overflow-y: auto;
  padding: 0 20px 20px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}

.modal-img-item {
  display: flex;
  flex-direction: column;
}

.modal-img-preview {
  position: relative;
  width: 100%;
  aspect-ratio: 3/4;
  overflow: hidden;
  border-radius: 8px;
  contain: layout style paint;
  cursor: zoom-in;
}
.modal-img-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.placeholder {
  width: 100%;
  aspect-ratio: 3/4;
  background: #f5f5f5;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 14px;
}

.img-footer {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #666;
}

.img-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.img-link {
  cursor: pointer;
  color: var(--primary, #ff2442);
  transition: opacity 0.2s;
}
.img-link:hover {
  opacity: 0.7;
}

@media (max-width: 768px) {
  .modal-fullscreen {
    padding: 20px;
  }
  .modal-gallery-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px;
    padding: 0 12px 12px;
  }
  .content-block {
    margin: 0;
  }
  .copy-panel {
    padding: 12px;
  }
  .outline-panel {
    padding:12px;
  }
}
</style>
