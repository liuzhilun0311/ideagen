<template>
  <div class="container" style="max-width: 100%;">
    <div class="page-header" style="max-width: 1200px; margin: 0 auto 30px auto; align-items: center;">
      <div>
        <h1 class="page-title">编辑图文</h1>
      </div>
      <div class="nav-row" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        <!-- 行1：返回编辑大纲 / 退出编辑 / 保存（靠右） -->
          <button 
          class="btn btn-info btn-small" @click="router.push({ path: '/outline', query: { from: 'generate' } })">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M19 12H5"></path><path d="m12 19-7-7 7-7"></path></svg>
            返回编辑大纲
          </button>
          <button class="btn btn-warning btn-small" @click="exitEdit">
            退出编辑
          </button>
          <button
            class="btn btn-purple btn-small"
            @click="handleSave"
            :disabled="saveDisabled"
          >
            保存
          </button>
        </div>
     </div>

    <div class="card image-module" style="max-width: 1200px; margin: 0 auto 24px auto;">
      <!-- 图片工具栏（与图片生成模块同一卡片；左侧进度 + 右侧控件） -->
      <div class="toolbar-row card-toolbar-row">
        <span v-if="store.progress.total > 0" class="progress-text">
          图片生成进度：{{ store.progress.current }}/{{ store.progress.total }}
        </span>
        <div class="inline-prompt prompt-image">
          <span class="prompt-label">提示词</span>
          <select id="image-prompt" v-model="store.imagePromptName" class="prompt-select" :disabled="isGenerating">
            <option value="">默认提示词</option>
            <option v-for="p in imagePrompts" :key="p.name" :value="p.name">{{ p.name }}</option>
          </select>
        </div>
        <div class="inline-prompt">
          <span class="prompt-label">模型</span>
          <select id="image-model" v-model="store.imageModelName" class="prompt-select" :disabled="isGenerating">
            <option v-if="imageModels.length === 0" value="">无可用模型</option>
            <option v-for="m in imageModels" :key="m.name" :value="m.name">{{ m.display_name }}</option>
          </select>
        </div>
        <button
          class="btn btn-small btn-fixed-4"
          :class="isGenerating ? 'btn-danger' : 'btn-success'"
          @click="isGenerating ? cancelImageGeneration() : startGenerationFlow(true)"
        >
          {{ isGenerating ? '取消' : '生成图片' }}
        </button>
      </div>

      <ErrorCard
        v-if="error"
        :error="error"
        dismissible
        style="margin-top: 18px;"
        @dismiss="error = null"
      />
      <!-- 图片待生成提示（与文案模块风格一致） -->
      <div v-if="!isGenerating && store.images.length === 0" class="image-idle-hint">
        <p>点击上方「生成图片」，即可为这组图文生成图片。</p>
      </div>
      <div class="grid-cols-4" style="margin-top: 40px;">
        <div v-for="image in store.images" :key="image.index" class="image-card">
          <!-- 图片展示区域 -->
          <div v-if="image.url && image.status === 'done'" class="image-preview">
            <img :src="image.url" :alt="`第 ${image.index + 1} 页`" @click="openImage(image)" />
          </div>
          <!-- 生成中/重试中状态 -->
          <div v-else-if="image.status === 'generating' || image.status === 'retrying'" class="image-placeholder">
            <div class="spinner"></div>
            <div class="status-text">{{ image.status === 'retrying' ? '重试中...' : '生成中...' }}</div>
          </div>
          <!-- 失败状态 -->
          <div v-else-if="image.status === 'error'" class="image-placeholder error-placeholder">
            <div class="error-icon">!</div>
            <div class="status-text">生成失败</div>
            <div v-if="image.error" class="image-error-text">{{ image.error }}</div>
            <button
              class="retry-btn"
              @click="retrySingleImage(image.index)"
            >
              点击重试
            </button>
          </div>
          <!-- 等待中状态 -->
          <div v-else class="image-placeholder">
            <div class="status-text">等待中</div>
          </div>
          <!-- 底部信息栏 -->
          <div class="image-footer">
            <span class="page-label">Page {{ image.index + 1 }}</span>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="status-badge" :class="image.status">
                {{ getStatusText(image.status) }}
              </span>
              <template v-if="image.url && image.status === 'done'">
                <button class="footer-action footer-action-info" @click="regenerateImage(image.index)">重新生成</button>
                <button class="footer-action footer-action-primary" @click="copyImage(image)">
                  {{ copiedImageIndex === image.index ? '已复制' : '复制' }}
                </button>
                <button class="footer-action footer-action-success" @click="downloadImage(image)">下载</button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div style="max-width: 1200px; margin: 0 auto 24px auto;">
      <ContentDisplay>
        <!-- 文案工具栏：与文案展示同一模块 -->
        <template #toolbar>
        <div class="toolbar-row content-module-toolbar">
          <div class="inline-prompt prompt-content">
            <span class="prompt-label">提示词</span>
            <select id="content-prompt" v-model="store.contentPromptName" class="prompt-select" :disabled="contentGenerating">
              <option value="">默认提示词</option>
              <option v-for="p in contentPrompts" :key="p.name" :value="p.name">{{ p.name }}</option>
            </select>
          </div>
          <div class="inline-prompt">
            <span class="prompt-label">模型</span>
            <select id="content-model" v-model="store.contentModelName" class="prompt-select" :disabled="contentGenerating">
              <option v-if="contentModels.length === 0" value="">无可用模型</option>
              <option v-for="m in contentModels" :key="m.name" :value="m.name">{{ m.display_name }}</option>
            </select>
          </div>
          <button
            class="btn btn-small btn-fixed-4"
            :class="contentGenerating ? 'btn-danger' : 'btn-success'"
            @click="contentGenerating ? cancelContentGeneration() : regenerateContent()"
          >
            {{ contentGenerating ? '取消' : '生成文案' }}
          </button>
        </div>
      </template>
      </ContentDisplay>
    </div>

    <ImageViewer
      :visible="viewerVisible"
      :src="viewerSrc"
      :alt="viewerAlt"
      @close="viewerVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateContent, updateHistory, getPrompts, cancelCurrentGeneration, getConfig, type PromptItem } from '../api'
import ErrorCard from '../components/common/ErrorCard.vue'
import ImageViewer from '../components/common/ImageViewer.vue'
import ContentDisplay from '../components/result/ContentDisplay.vue'
import { useGenerationRunner } from '../composables/useGenerationRunner'
import { useGenerationRestore } from '../composables/useGenerationRestore'
import { useImageRetry } from '../composables/useImageRetry'
import { formatErrorMessage, type AppError } from '../utils/errors'
import { authHeaders } from '../api/client'
import { getToken } from '../api/token'

const router = useRouter()
const store = useGeneratorStore()

// 退出编辑：按进入来源返回（历史记录进入回历史，其他回创作中心）
function exitEdit() {
  router.push(store.entrySource === 'history' ? '/history' : '/')
}

const error = ref<AppError | null>(null)
const copiedImageIndex = ref<number | null>(null)
const viewerVisible = ref(false)
const viewerSrc = ref('')
const viewerAlt = ref('')

const isGenerating = computed(() => store.progress.status === 'generating')
const contentGenerating = computed(() => store.content.status === 'generating')
// 保存按钮：图文（图片+文案）全部生成完毕才可点击
const saveDisabled = computed(() =>
  isGenerating.value ||
  contentGenerating.value ||
  store.images.length === 0 ||
  store.images.some(img => img.status === 'generating' || img.status === 'retrying') ||
  store.content.status !== 'done'
)
// 进度已改为工具栏内的文字表达（图片生成进度：x/n）

// 图片/文案提示词列表（不含系统默认）
const imagePrompts = ref<PromptItem[]>([])
const contentPrompts = ref<PromptItem[]>([])
// 图片/文案模型（服务商）列表：{ name: 服务商标识, display_name: 列表展示名称 }
const imageModels = ref<{ name: string; display_name: string }[]>([])
const contentModels = ref<{ name: string; display_name: string }[]>([])

const handleSave = () => {
  router.push('/result')
}

// 放大查看单张图片
const openImage = (image: any) => {
  viewerSrc.value = image.url
  viewerAlt.value = `第 ${image.index + 1} 页`
  viewerVisible.value = true
}

// 重新生成标题、文案和标签
// 文案生成的中断控制器（用于"取消"）
let contentAbort: AbortController | null = null

const regenerateContent = async () => {
  // 重新生成前取消上一次未结束的请求
  if (contentAbort) {
    contentAbort.abort()
    contentAbort = null
  }
  contentAbort = new AbortController()

  store.startContentGeneration()
  try {
    const result = await generateContent(store.topic, store.outline.raw, store.contentPromptName, contentAbort.signal, store.contentModelName)
    if (result.success && result.titles && result.copywriting && result.tags) {
      store.setContent(result.titles, result.copywriting, result.tags)
      if (store.recordId) {
        updateHistory(store.recordId, {
          content: { titles: result.titles, copywriting: result.copywriting, tags: result.tags }
        }).catch(() => {})
      }
    } else {
      store.setContentError(formatErrorMessage(result.error || result.error_message || '生成失败', '内容生成失败'))
    }
  } catch (e: any) {
    // 主动取消不当作错误
    if (e?.name === 'CanceledError' || e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') {
      store.clearContent()
      return
    }
    store.setContentError(formatErrorMessage(e, '内容生成失败'))
  } finally {
    contentAbort = null
  }
}

/** 取消文案生成（同时通知后端作废结果） */
const cancelContentGeneration = async () => {
  if (contentAbort) {
    contentAbort.abort()
    contentAbort = null
  }
  try { await cancelCurrentGeneration() } catch {}
  store.clearContent()
}

// 下载单张图片
const downloadImage = (image: any) => {
  if (image.url) {
    const link = document.createElement('a')
    const baseUrl = image.url.split('?')[0]
    const token = getToken()
    link.href = `${baseUrl}?thumbnail=false${token ? `&token=${encodeURIComponent(token)}` : ''}`
    link.download = `rednote_page_${image.index + 1}.png`
    link.click()
  }
}

// 复制单张图片到剪贴板
const copyImage = async (image: any) => {
  if (!image.url) return
  try {
    const baseUrl = image.url.split('?')[0]
    const blob = await (await fetch(baseUrl + '?thumbnail=false', { headers: authHeaders() })).blob()
    await navigator.clipboard.write([new ClipboardItem({ [blob.type || 'image/png']: blob })])
    copiedImageIndex.value = image.index
    window.setTimeout(() => {
      if (copiedImageIndex.value === image.index) copiedImageIndex.value = null
    }, 1500)
  } catch (e: any) {
    console.error('复制图片失败:', e)
    alert('复制图片失败，请稍后重试')
  }
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    generating: '生成中',
    done: '已完成',
    error: '失败',
    retrying: '重试中'
  }
  return texts[status] || '等待中'
}

function setError(nextError: AppError | null) {
  error.value = nextError
}

const {
  regenerateImage,
  retrySingleImage
} = useImageRetry(setError)

const {
  startGenerationFlow,
  cancelGenerationFlow
} = useGenerationRunner(setError)

/** 取消图片生成 */
const cancelImageGeneration = () => {
  cancelGenerationFlow()
}

const { restoreFromHistory } = useGenerationRestore()

onMounted(async () => {
  // 加载用户自定义提示词
  try {
    const res = await getPrompts()
    if (res.success && res.prompts) {
      imagePrompts.value = res.prompts.image.filter(p => !p.is_base)
      contentPrompts.value = res.prompts.content.filter(p => !p.is_base)
    }
  } catch (e) {
    console.error('加载提示词失败:', e)
  }
  await loadModels()

  if (store.outline.pages.length === 0) {
    router.push('/')
    return
  }
  // 进入生成页：恢复已生成的图片（没有则显示"生成图片"待生成状态）
  await restoreFromHistory()
})

// 加载可选模型（服务商）列表（模型设置里配置的图片/文本服务商）
// onMounted + onActivated 都调用：KeepAlive 缓存下切回页面时也会刷新启用状态
async function loadModels() {
  try {
    const cfgRes = await getConfig()
    if (cfgRes.success && cfgRes.config) {
      const imageProviders = cfgRes.config.image_generation?.providers || {}
      const textProviders = cfgRes.config.text_generation?.providers || {}
      // 只展示已启用（enabled !== false）的服务商
      imageModels.value = Object.keys(imageProviders)
        .filter(n => imageProviders[n]?.enabled !== false)
        .map(n => ({
          name: n,
          display_name: imageProviders[n]?.display_name || n
        }))
      contentModels.value = Object.keys(textProviders)
        .filter(n => textProviders[n]?.enabled !== false)
        .map(n => ({
          name: n,
          display_name: textProviders[n]?.display_name || n
        }))
      // 默认模型：无记忆时选第一个激活的（没有则为空）；记忆的模型已停用时回退到第一个
      const syncDefault = (list: { name: string; display_name: string }[], key: 'imageModelName' | 'contentModelName') => {
        if (list.length > 0) {
          const names = list.map(m => m.name)
          if (!store[key] || !names.includes(store[key])) {
            store[key] = list[0].name
          }
        } else {
          store[key] = ''
        }
      }
      syncDefault(imageModels.value, 'imageModelName')
      syncDefault(contentModels.value, 'contentModelName')
    }
  } catch (e) {
    console.error('加载模型列表失败:', e)
  }
}

// KeepAlive 缓存复用：切回页面时刷新模型列表（模型设置里可能改过启用状态）
onActivated(() => {
  loadModels()
})
</script>

<style scoped>
/* 生成/文案按钮：按四个字固定宽度，切换"生成/取消"时大小不变 */
.btn-fixed-4 {
  min-width: 98px;
}
/* 图片生成卡片内的工具栏行（与文案模块一致：顶部工具栏 + 下划线分隔） */
.card-toolbar-row {
  width: 100%;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}
/* 图片生成进度（工具栏行左侧，靠左） */
.progress-text {
  margin-right: auto;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-sub);
  white-space: nowrap;
}
/* 图片待生成提示（无图片且未生成时显示，与文案模块风格一致） */
.image-idle-hint {
  text-align: center;
  padding: 32px 12px;
  color: var(--text-sub);
  font-size: 15px;
  line-height: 1.7;
}
.image-idle-hint p {
  margin: 0;
}

/* 导航按钮行：返回编辑大纲 / 退出编辑 / 保存（页头右侧一行，靠右） */
.nav-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  width: 100%;
}
/* 文案工具栏（位于文案模块卡片顶部，靠右） */
.content-module-toolbar {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}
.image-preview {
  aspect-ratio: 3/4;
  overflow: hidden;
  position: relative;
  flex: 1; /* 填充卡片剩余空间 */
}
.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  cursor: zoom-in;
}

.image-placeholder {
  aspect-ratio: 3/4;
  background: #f9f9f9;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 1; /* 填充卡片剩余空间 */
  min-height: 240px; /* 确保有最小高度 */
}
.error-placeholder {
  background: #fff5f5;
}
.error-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #ff4d4f;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
}
.status-text {
  font-size: 13px;
  color: var(--text-sub);
}
.image-error-text {
  max-width: 85%;
  color: #991b1b;
  font-size: 12px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.retry-btn {
  margin-top: 8px;
  padding: 6px 16px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}
.retry-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}
.retry-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
.image-footer {
  padding: 12px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-label {
  font-size: 12px;
  color: var(--text-sub);
}
.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
}
.status-badge.done {
  background: #E6F7ED;
  color: #52C41A;
}
.status-badge.generating,
.status-badge.retrying {
  background: #E6F4FF;
  color: #1890FF;
}
.status-badge.error {
  background: #FFF1F0;
  color: #FF4D4F;
}
.footer-action {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 50px;
  white-space: nowrap;
  transition: all 0.2s;
}
.footer-action-info {
  color: #2563eb;
}
.footer-action-info:hover {
  background: #eff6ff;
}
.footer-action-primary {
  color: var(--primary);
}
.footer-action-primary:hover {
  background: #fff1f2;
}
.footer-action-success {
  color: #059669;
}
.footer-action-success:hover {
  background: #ecfdf5;
}
.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
/* 图片提示词：蓝色主题 */
.prompt-image .prompt-label {
  color: #2563eb;
}
.prompt-image .prompt-select {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}
.prompt-image .prompt-select:focus {
  border-color: #2563eb;
}
/* 文案提示词：与图片提示词同色（蓝色主题） */
.prompt-content .prompt-label {
  color: #2563eb;
}
.prompt-content .prompt-select {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}
.prompt-content .prompt-select:focus {
  border-color: #2563eb;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>