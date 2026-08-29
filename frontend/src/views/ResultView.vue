<template>
  <div class="container" style="max-width: 100%;">
    <div class="page-header" style="max-width: 1200px; margin: 0 auto 30px auto; align-items: center;">
      <div>
        <h1 class="page-title">创作完成</h1>
      </div>
      <div class="nav-row" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        <button class="btn btn-info btn-small" @click="goEdit">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
          </svg>
          重新编辑
        </button>
        <div class="deai-download" title="去AI化 & 下载">
          <div class="deai-select-part">
            <span class="deai-label">去AI化</span>
            <select v-model="deaiStrength" class="deai-select" title="去AI化强度">
              <option value="light">light</option>
              <option value="medium">medium</option>
              <option value="heavy">heavy</option>
            </select>
          </div>
          <span class="deai-divider"></span>
          <button class="deai-download-btn" @click="downloadAll" :disabled="downloadWorking">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            <span>{{ downloadWorking ? '下载中...' : '下载' }}</span>
          </button>
        </div>
        <button class="btn btn-warning btn-small" @click="exitEdit">
          退出
        </button>
      </div>
    </div>
    <div class="card" style="max-width: 1200px; margin: 0 auto 24px auto;">
      <div class="grid-cols-4">
        <div v-for="image in store.images" :key="image.index" class="image-card group">
          <div
            v-if="image.url"
            style="position: relative; aspect-ratio: 3/4; overflow: hidden; cursor: pointer;"
            @click="openImage(image)"
          >
            <img
              :src="image.url"
              :alt="`第 ${image.index + 1} 页`"
              style="width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s;"
            />
            <div style="position: absolute; inset: 0; background: rgba(0,0,0,0.3); opacity: 0; transition: opacity 0.2s; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600;" class="hover-overlay">
              预览大图
            </div>
          </div>
          <div style="padding: 12px; border-top: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 12px; color: var(--text-sub);">Page {{ image.index + 1 }}</span>
            <div style="display: flex; gap: 8px;">
              <button
                style="border: none; background: none; color: var(--primary); cursor: pointer; font-size: 12px;"
                @click="copyImage(image)"
              >
                {{ copiedImageIndex === image.index ? '已复制' : '复制' }}
              </button>
              <button
                style="border: none; background: none; color: var(--primary); cursor: pointer; font-size: 12px;"
                @click="downloadOne(image)"
              >
                下载
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div style="max-width: 1200px; margin: 0 auto 24px auto;">
      <ContentDisplay />
    </div>

    <ImageViewer
      :visible="viewerVisible"
      :src="viewerSrc"
      :alt="viewerAlt"
      @close="viewerVisible = false"
    />

    <!-- 下载完成提示 -->
    <Teleport to="body">
      <div v-if="downloadComplete" class="dl-mask" @click.self="downloadComplete = false">
        <div class="dl-dialog">
          <div class="dl-icon">
            <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </div>
          <h3 class="dl-title">下载完成</h3>
          <p class="dl-desc">{{ downloadMessage }}</p>
          <div class="dl-actions">
            <button class="dl-btn primary" @click="downloadComplete = false">知道了</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 下载进行中提示 -->
    <Teleport to="body">
      <div v-if="downloadWorking" class="dl-mask" style="z-index: 10002;">
        <div class="dl-dialog" style="width: 380px; padding: 30px 26px 26px;">
          <div class="dl-spinner"></div>
          <p class="dl-stage">{{ downloadStage }}</p>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.image-card > div:first-child {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.image-card:hover .hover-overlay {
  opacity: 1;
}
.image-card:hover img {
  transform: scale(1.05);
}

/* 按钮样式：btn‑primary主蓝色，btn‑secondary薄荷绿，尺寸、padding、圆角完全对齐 */
:deep(.btn) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  transition: opacity 0.2s;
}
:deep(.btn:hover) {
  opacity: 0.85;
}
:deep(.btn-primary) {
  background-color: #2563eb;
  color: #ffffff;
}
:deep(.btn-secondary) {
  background-color: #059669;
  color: #ffffff;
}

/* 下载完成弹窗 */
.dl-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 10001;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: dl-fade 0.2s ease;
}
@keyframes dl-fade {
  from { opacity: 0; }
  to   { opacity: 1; }
}
.dl-dialog {
  background: #fff;
  width: 420px;
  max-width: 90vw;
  border-radius: 14px;
  padding: 28px 28px 22px;
  text-align: center;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.25);
  animation: dl-pop 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes dl-pop {
  from { transform: scale(0.85); opacity: 0; }
  to   { transform: scale(1); opacity: 1; }
}
.dl-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  margin: 0 auto 14px;
  background: #ecfdf5;
  border-radius: 50%;
}
.dl-title {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}
.dl-desc {
  margin: 0 0 20px;
  font-size: 14px;
  color: #555;
  line-height: 1.6;
  white-space: pre-line;
}
.dl-actions {
  display: flex;
  justify-content: center;
}
.dl-btn {
  padding: 9px 28px;
  border-radius: 50px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.dl-btn.primary {
  background: linear-gradient(135deg, #059669 0%, #10b981 100%);
  color: #fff;
  box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
}
.dl-btn.primary:hover {
  background: linear-gradient(135deg, #047857 0%, #059669 100%);
  transform: translateY(-1px);
}

/* 去AI化&下载组合控件：左侧强度选择 + 右侧下载按钮，合成一个整体胶囊 */
.deai-download {
  display: inline-flex;
  align-items: stretch;
  height: 34px;
  border-radius: 50px;
  overflow: hidden;
  border: 1px solid #93c5fd;
  background: #eff6ff;
}
.deai-download:focus-within {
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}
.deai-select-part {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-left: 14px;
}
.deai-label {
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
  white-space: nowrap;
}
.deai-select {
  height: 100%;
  padding: 0 10px 0 2px;
  border: none;
  background: transparent;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  outline: none;
}
.deai-select option {
  color: #333;
}
.deai-divider {
  width: 1px;
  background: #93c5fd;
  flex-shrink: 0;
}
.deai-download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
  border: none;
  background: linear-gradient(135deg, #059669 0%, #10b981 100%);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.2s, opacity 0.2s;
}
.deai-download-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #047857 0%, #059669 100%);
}
.deai-download-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 下载进行中 */
.dl-spinner {
  width: 38px;
  height: 38px;
  margin: 0 auto 16px;
  border: 3px solid #e5e7eb;
  border-top-color: #059669;
  border-radius: 50%;
  animation: dl-spin 0.8s linear infinite;
}
@keyframes dl-spin {
  to { transform: rotate(360deg); }
}
.dl-stage {
  margin: 0;
  font-size: 14px;
  color: #444;
  line-height: 1.7;
  text-align: center;
}
</style>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import ContentDisplay from '../components/result/ContentDisplay.vue'
import ImageViewer from '../components/common/ImageViewer.vue'
import { runDeaiDownload, downloadAsZip } from '../composables/useDeaiDownload'
import { authHeaders } from '../api/client'
import { getToken } from '../api/token'

const router = useRouter()
const store = useGeneratorStore()

// 退出编辑/再来一篇：按进入来源返回（历史记录进入回历史，其他回创作中心）
function exitEdit() {
  router.push(store.entrySource === 'history' ? '/history' : '/')
}

const copiedImageIndex = ref<number | null>(null)
const deaiStrength = ref<'light' | 'medium' | 'heavy'>('medium')
const viewerVisible = ref(false)
const viewerSrc = ref('')
const viewerAlt = ref('')
const downloadComplete = ref(false)
const downloadMessage = ref('')
const downloadWorking = ref(false)
const downloadStage = ref('')

// 放大查看单张图片
const openImage = (image: any) => {
  viewerSrc.value = image.url
  viewerAlt.value = `第 ${image.index + 1} 页`
  viewerVisible.value = true
}

const goEdit = () => {
  router.push('/generate')
}

// 复制图片到剪贴板
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

// 单张图片下载
const downloadOne = (image: any) => {
  if (image.url) {
    const link = document.createElement('a')
    const baseUrl = image.url.split('?')[0]
    const token = getToken()
    link.href = `${baseUrl}?thumbnail=false${token ? `&token=${encodeURIComponent(token)}` : ''}`
    link.download = `rednote_page_${image.index + 1}.png`
    link.click()
  }
}



// 一键下载：点击后立即弹出文件夹选择器（浏览器要求选择器必须紧跟用户点击手势），
// 选定目标文件夹后自动执行去AI化并直接写入该文件夹（不打包压缩）
const downloadAll = async () => {
  if (downloadWorking.value) return

  // 0. 浏览器支持则立即弹出文件夹选择器（showDirectoryPicker 必须紧跟用户点击手势），
  //    否则会报 "Must be handling a user gesture"；不支持（http 非 localhost）则走 zip 兜底
  let dirHandle: any = null
  if ('showDirectoryPicker' in window) {
    try {
      dirHandle = await (window as any).showDirectoryPicker({ mode: 'readwrite', startIn: 'downloads' })
    } catch (pickErr: any) {
      // 用户取消选择（AbortError）→ 静默结束，不下载任何文件
      return
    }
  }

  downloadWorking.value = true
  try {
    // 1. 确定任务ID（作为子文件夹名，便于后续查找）
    let taskId = store.taskId || ''
    if (!taskId) {
      const firstImg = store.images.find(i => i.url)
      const m = firstImg?.url?.match(/\/api\/images\/([^/]+)\//)
      if (m) taskId = m[1]
    }

    // 2. 复用共享下载逻辑：去AI化 → 准备文件 → 写入所选文件夹（或 zip 兜底下载）
    const images = store.images
      .filter((i: any) => i.url && i.status === 'done')
      .map((i: any) => ({ index: i.index, url: i.url }))
    const content = {
      titles: store.content.titles,
      copywriting: store.content.copywriting,
      tags: store.content.tags
    }
    const result = dirHandle
      ? await runDeaiDownload({ dirHandle, taskId, strength: deaiStrength.value, images, content, setStage: (t) => { downloadStage.value = t } })
      : await downloadAsZip({ taskId, strength: deaiStrength.value, images, content, setStage: (t) => { downloadStage.value = t } })
    downloadMessage.value = result.message
    downloadComplete.value = true
  } catch (e: any) {
    console.error('下载失败:', e)
    alert('下载失败，请稍后重试')
  } finally {
    downloadWorking.value = false
  }
}
</script>