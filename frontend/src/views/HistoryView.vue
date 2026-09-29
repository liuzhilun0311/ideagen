<template>
  <div class="container" style="max-width: 1200px;">

    <!-- Header Area -->
    <div class="page-header">
      <div>
        <h1 class="page-title">我的作品</h1>
      </div>
      <div style="display: flex; gap: 10px;">
        <button
          v-if="!currentSource"
          class="btn btn-secondary btn-small"
          @click="handleScanAll"
          :disabled="isScanning || session.busy"
        >
          <svg v-if="!isScanning" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
          <div v-else class="spinner-small" style="margin-right: 6px;"></div>
          {{ isScanning ? '同步中...' : '同步历史' }}
        </button>
        <button class="btn btn-primary btn-small" :disabled="session.busy" @click="newCreation">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          新建图文
        </button>
      </div>
    </div>

    <ErrorCard
      v-if="error"
      :error="error"
      dismissible
      style="margin-bottom: 16px;"
      @dismiss="error = null"
    />

    <div v-else-if="successMessage" class="success-card" role="status" aria-live="polite">
      <span>{{ successMessage }}</span>
      <button type="button" @click="successMessage = ''" aria-label="关闭提示">×</button>
    </div>

    <!-- Stats Overview -->
    <StatsOverview v-if="stats" :stats="stats" />
    <div class="source-selector" role="group" aria-label="作品来源">
      <button :aria-pressed="!currentSource" @click="switchSource(undefined)">作品</button>
      <button :aria-pressed="currentSource === 'shared'" @click="switchSource('shared')">共享给我</button>
    </div>

    <!-- Toolbar: Tabs & Search -->
    <div class="toolbar-wrapper">
      <div class="tabs-container" style="margin-bottom: 0; border-bottom: none;">
        <div
          class="tab-item"
          :class="{ active: currentTab === 'all' }"
          @click="switchTab('all')"
        >
          全部
        </div>
        <div
          class="tab-item"
          :class="{ active: currentTab === 'completed' }"
          @click="switchTab('completed')"
        >
          已完成
        </div>
        <div
          class="tab-item"
          :class="{ active: currentTab === 'draft' }"
          @click="switchTab('draft')"
        >
          草稿箱
        </div>
      </div>

      <div class="search-mini">
        <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input
          v-model="searchKeyword"
          type="text"
          placeholder="搜索标题..."
          @keyup.enter="handleSearch"
        />
      </div>
    </div>

    <!-- Content Area -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <div v-else-if="records.length === 0" class="empty-state-large">
      <div class="empty-img">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
      </div>
      <h3>暂无相关记录</h3>
      <p class="empty-tips">{{ currentSource === 'shared' ? '暂无共享给你的相关作品' : '去创建一个新的作品吧' }}</p>
    </div>

    <div v-else class="gallery-grid">
      <GalleryCard
        v-for="record in records"
        :key="record.id"
        :record="record"
        :readonly="currentSource === 'shared'"
        @preview="viewImages"
        @edit="loadRecord"
        @download="handleDownload"
        @delete="confirmDelete"
        @share="openSharing"
      />
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="pagination-wrapper">
      <button class="page-btn" :disabled="currentPage === 1" @click="changePage(1)">首页</button>
      <button class="page-btn" :disabled="currentPage === 1" @click="changePage(currentPage - 1)">上一页</button>
      <span class="page-indicator">第</span>
      <input
        type="number"
        class="page-input"
        v-model.number="pageInput"
        min="1"
        :max="totalPages"
        @keyup.enter="goToPage"
        @blur="goToPage"
      />
      <span class="page-indicator">/ {{ totalPages }} 页</span>
      <button class="page-btn" :disabled="currentPage === totalPages" @click="changePage(currentPage + 1)">下一页</button>
      <button class="page-btn" :disabled="currentPage === totalPages" @click="changePage(totalPages)">尾页</button>
    </div>

    <!-- Image Viewer Modal -->
    <ImageGalleryModal
      v-if="viewingRecord"
      :visible="!!viewingRecord"
      :record="viewingRecord"
      :readonly="currentSource === 'shared' || viewingRecord.can_edit !== true"
      @close="closeGallery"
      @edit="loadRecord"
      @download="downloadImage"
      @unavailable="previewUnavailable"
    />

    <!-- 大纲查看模态框 -->
    <OutlineModal
      v-if="showOutlineModal && viewingRecord"
      :visible="showOutlineModal"
      :pages="viewingRecord.outline.pages"
      @close="showOutlineModal = false"
    />

    <WorkSharingDialog v-if="sharingRecord" :key="sharingRecord.id" :record="sharingRecord"
      @close="sharingRecord = null" @saved="sharingSaved" />

    <ImageDownloadDialog v-if="downloadVisible" :visible="downloadVisible" :pages="downloadPages"
      :can-process="currentSource !== 'shared' && downloadRecord?.can_edit === true"
      :loading="downloadLoading || downloadProcessing.loading.value"
      :load-error="downloadError || downloadProcessing.error.value?.detail"
      :content="downloadIndex === null ? downloadContent : undefined"
      @close="closeDownload" @process="editDownloadRecord" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  getHistoryList,
  getHistoryStats,
  deleteHistory,
  getHistory,
  type HistoryRecord,
  type HistoryDetail,
  type HistorySource,
  scanAllTasks
} from '../api'
import { useGeneratorStore } from '../stores/generator'
import { useStudioSession } from '../stores/studioSession'
import { useHistoryDraft } from '../composables/useHistoryDraft'
import ImageDownloadDialog from '../components/common/ImageDownloadDialog.vue'
import { usePostprocessing } from '../composables/usePostprocessing'

// 引入组件
import StatsOverview from '../components/history/StatsOverview.vue'
import GalleryCard from '../components/history/GalleryCard.vue'
import ImageGalleryModal from '../components/history/ImageGalleryModal.vue'
import OutlineModal from '../components/history/OutlineModal.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import { normalizeApiError } from '../utils/errors'
import WorkSharingDialog from '../components/history/WorkSharingDialog.vue'
import { useAuthStore } from '../stores/auth'
import { getMe } from '../api/auth'
import { setUser } from '../api/token'
import { selectedTitle } from '../utils/publicationContent'

const router = useRouter()
const route = useRoute()
const store = useGeneratorStore()
const session = useStudioSession()
const historyDraft = useHistoryDraft(router)
async function newCreation() {
  if (session.busy) return
  const hasDraft = store.topic || store.referenceContent || store.outline.raw
    || store.outline.pages.length || store.images.length || store.userImages.length
    || store.recordId || store.taskId || store.content.titles.length
    || store.content.copywriting || store.content.tags.length
  if (hasDraft && !window.confirm('新建图文将清空当前创作草稿，已保存的作品不受影响。确定继续吗？')) return
  if (!session.replaceDraft()) return
  historyDraft.cancelPending()
  store.reset()
  store.setEntrySource('home')
  store.saveToStorage()
  await router.push('/')
}
const auth = useAuthStore()
onDeactivated(historyDraft.cancelPending)
onBeforeUnmount(historyDraft.cancelPending)

// 数据状态
const records = ref<HistoryRecord[]>([])
const loading = ref(false)
const stats = ref<any>(null)
const currentTab = ref('all')
const currentSource = ref<HistorySource>()
const searchKeyword = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
// 页码输入框（跳转用）
const pageInput = ref(1)
watch(currentPage, (v) => { pageInput.value = v })

// 查看器状态
const viewingRecord = ref<HistoryDetail | null>(null)
const sharingRecord = ref<HistoryRecord | null>(null)
const showOutlineModal = ref(false)
const isScanning = ref(false)
const error = historyDraft.error
const successMessage = ref('')
let active = true
let lifecycle = 0
let listEpoch = 0
let statsEpoch = 0
let previewEpoch = 0
let refreshingAuth = false
function scope() {
  const revision = lifecycle
  const token = auth.token
  const userId = auth.user?.id
  const sessionRevision = auth.sessionRevision
  return () => active && lifecycle === revision && auth.token === token
    && auth.user?.id === userId && auth.sessionRevision === sessionRevision
}
function clearTransient() {
  ++lifecycle
  ++listEpoch
  ++statsEpoch
  closeGallery()
  closeDownload()
  sharingRecord.value = null
  records.value = []
  stats.value = null
  loading.value = false
  refreshingAuth = false
  isScanning.value = false
  error.value = null
  successMessage.value = ''
  historyDraft.cancelPending()
}
function openSharing(record: { id: string }) {
  const item = records.value.find(item => item.id === record.id)
  if (!currentSource.value && auth.isAdmin && item?.can_share && item.owner?.id === auth.user?.id) sharingRecord.value = item
}
function sharingSaved(id: string, userIds: string[]) {
  if (sharingRecord.value?.id !== id) return
  const item = records.value.find(item => item.id === id)
  if (item) item.shared_count = userIds.length
  sharingRecord.value = null
}
function previewUnavailable() {
  closeGallery()
  records.value = []
  stats.value = null
  error.value = normalizeApiError('作品已不可用，可能已被删除或取消共享。请刷新作品列表。', '作品不可用')
}

// 下载状态
const downloadVisible = ref(false)
const downloadLoading = ref(false)
const downloadError = ref('')
const downloadRecord = ref<HistoryDetail | null>(null)
const downloadIndex = ref<number | null>(null)
const downloadProcessing = usePostprocessing(computed(() => downloadVisible.value ? downloadRecord.value?.id || null : null))
let downloadEpoch = 0
const downloadPages = computed(() => downloadProcessing.pages.value
  .filter(page => downloadIndex.value === null || page.index === downloadIndex.value))
const downloadContent = computed(() => {
  const content = downloadRecord.value?.content
  if (!content) return undefined
  const titles = content.titles || []
  return { ...content, titles: titles.length ? [selectedTitle(titles, content.selected_title_index)] : [] }
})
function closeDownload() {
  downloadVisible.value = false
  downloadLoading.value = false
  downloadRecord.value = null
  downloadError.value = ''
  ++downloadEpoch
}
async function editDownloadRecord() {
  if (currentSource.value === 'shared' || !downloadRecord.value?.can_edit) return
  const id = downloadRecord.value?.id
  closeDownload()
  if (id) await loadRecord(id)
}
onDeactivated(closeDownload)

/**
 * 加载历史记录列表
 */
async function loadData() {
  if (!active) return
  const valid = scope()
  const request = ++listEpoch
  loading.value = true
  error.value = null
  try {
    let statusFilter = currentTab.value === 'all' ? undefined : currentTab.value
    const res = await getHistoryList(currentPage.value, 12, statusFilter, currentSource.value, searchKeyword.value.trim() || undefined)
    if (!valid() || request !== listEpoch) return
    if (res.success) {
      records.value = res.records
      totalPages.value = res.total_pages
    } else {
      records.value = []
      error.value = normalizeApiError(res.error || res.error_message || '获取历史记录列表失败', '获取历史记录列表失败')
    }
  } catch(e) {
    if (!valid() || request !== listEpoch) return
    records.value = []
    error.value = normalizeApiError(e, '获取历史记录列表失败')
  } finally {
    if (valid() && request === listEpoch) loading.value = false
  }
}

/**
 * 加载统计数据
 */
async function loadStats() {
  if (!active) return
  const valid = scope()
  const request = ++statsEpoch
  try {
    const res = await getHistoryStats(currentSource.value)
    if (!valid() || request !== statsEpoch) return
    if (res.success) {
      stats.value = res
    } else {
      stats.value = null
      error.value = normalizeApiError(res.error || res.error_message || '获取统计信息失败', '获取统计信息失败')
    }
  } catch(e) {
    if (!valid() || request !== statsEpoch) return
    stats.value = null
    error.value = normalizeApiError(e, '获取统计信息失败')
  }
}

/**
 * 切换标签页
 */
function switchTab(tab: string) {
  closeGallery()
  closeDownload()
  sharingRecord.value = null
  currentTab.value = tab
  currentPage.value = 1
  loadData()
}

/**
 * 搜索历史记录
 */
function handleSearch() {
  currentPage.value = 1
  closeGallery()
  closeDownload()
  sharingRecord.value = null
  void loadData()
}
function switchSource(source?: HistorySource) {
  if (currentSource.value === source) return
  clearTransient()
  currentSource.value = source
  currentPage.value = 1
  void loadData()
  void loadStats()
}

/**
 * 加载记录并跳转到编辑页
 */
async function loadRecord(id: string) {
  const record = records.value.find(item => item.id === id) || viewingRecord.value || downloadRecord.value
  if (currentSource.value === 'shared' || record?.id !== id || record.can_edit !== true) return
  if (await historyDraft.loadRecord(id)) closeGallery()
}

/**
 * 查看图片
 */
async function viewImages(id: string) {
  const valid = scope()
  const request = ++previewEpoch
  viewingRecord.value = null
  try {
    const res = await getHistory(id)
    if (!valid() || request !== previewEpoch) return
    if (res.success && res.record?.id === id) {
      viewingRecord.value = res.record
    } else {
      previewUnavailable()
    }
  } catch (cause) {
    if (!valid() || request !== previewEpoch) return
    error.value = normalizeApiError(cause, '查看图片失败')
  }
}

/**
 * 关闭图片查看器
 */
function closeGallery() {
  ++previewEpoch
  viewingRecord.value = null
  showOutlineModal.value = false
}

/**
 * 确认删除
 */
async function confirmDelete(record: any) {
  if (currentSource.value === 'shared' || record.can_edit !== true) return
  const valid = scope()
  if (record.id === store.recordId) {
    error.value = normalizeApiError('此作品正在创作区编辑，请先切换到另一份草稿再删除。', '无法删除当前作品')
    return
  }
  if (confirm('确定删除吗？')) {
    if (record.id === store.recordId) {
      error.value = normalizeApiError('此作品正在创作区编辑，请先切换到另一份草稿再删除。', '无法删除当前作品')
      return
    }
    try {
      const result = await deleteHistory(record.id)
      if (!valid()) return
      if (result.success) {
        loadData()
        loadStats()
      } else {
        error.value = normalizeApiError(result.error || result.error_message || '删除历史记录失败', '删除历史记录失败')
      }
    } catch (cause) {
      if (!valid()) return
      error.value = normalizeApiError(cause, '删除历史记录失败')
    }
  }
}

/**
 * 切换页码
 */
function changePage(p: number) {
  closeGallery()
  closeDownload()
  sharingRecord.value = null
  currentPage.value = p
  loadData()
}

/**
 * 前往输入的页码（回车/失焦触发），越界自动收敛到 1~总页数
 */
function goToPage() {
  const p = Math.min(Math.max(1, pageInput.value || 1), Math.max(1, totalPages.value))
  changePage(p)
  pageInput.value = p
}

/**
 * 下载单张图片
 */
function downloadImage(_filename: string, index: number) {
  if (!viewingRecord.value) return
  void handleDownload(viewingRecord.value.id, index)
}

/**
 * 下载已有图片版本，不在导出时触发图片处理。
 */
async function handleDownload(id: string, index: number | null = null) {
  const valid = scope()
  const epoch = ++downloadEpoch
  downloadRecord.value = null
  downloadIndex.value = index
  downloadError.value = ''
  downloadVisible.value = true
  downloadLoading.value = true
  try {
    const res = await getHistory(id)
    if (!valid() || epoch !== downloadEpoch) return
    if (!res.success || !res.record) {
      closeGallery()
      records.value = records.value.filter(record => record.id !== id)
      throw new Error(res.error_message || '作品已不可用，可能已被删除或取消共享')
    }
    downloadRecord.value = res.record
  } catch (cause) {
    if (valid() && epoch === downloadEpoch) downloadError.value = normalizeApiError(cause, '读取作品失败').detail
  } finally { if (valid() && epoch === downloadEpoch) downloadLoading.value = false }
}

/**
 * 扫描所有任务并同步
 */
async function handleScanAll() {
  if (currentSource.value || session.busy || isScanning.value) return
  const valid = scope()
  isScanning.value = true
  try {
    const result = await scanAllTasks()
    if (!valid()) return
    if (result.success) {
      let message = `扫描完成！\n`
      message += `- 总任务数: ${result.total_tasks || 0}\n`
      message += `- 同步成功: ${result.synced || 0}\n`
      message += `- 同步失败: ${result.failed || 0}\n`

      if (result.orphan_tasks && result.orphan_tasks.length > 0) {
        message += `- 孤立任务（无记录）: ${result.orphan_tasks.length} 个\n`
      }

      successMessage.value = message
      await loadData()
      await loadStats()
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '扫描失败', '扫描失败')
    }
  } catch (e) {
    if (!valid()) return
    console.error('扫描失败:', e)
    error.value = normalizeApiError(e, '扫描失败')
  } finally {
    if (valid()) isScanning.value = false
  }
}

async function refreshAuthorized() {
  const valid = scope()
  refreshingAuth = true
  loading.value = true
  try {
    const result = await getMe()
    if (!valid()) return
    if (!result.success || !result.user) throw new Error('登录状态已失效，请重新登录')
    auth.user = result.user
    setUser(result.user)
    await Promise.all([loadData(), loadStats()])
    if (valid() && route.params.id) await viewImages(route.params.id as string)
  } catch (cause) {
    if (valid()) {
      records.value = []
      stats.value = null
      error.value = normalizeApiError(cause, '刷新访问权限失败')
    }
  } finally {
    if (valid()) { refreshingAuth = false; loading.value = false }
  }
}
watch([() => auth.token, () => auth.user?.id, () => auth.sessionRevision], () => {
  clearTransient()
  currentPage.value = 1
  currentTab.value = 'all'
  currentSource.value = undefined
  searchKeyword.value = ''
  if (active && auth.token) void refreshAuthorized()
}, { flush: 'sync' })
watch(() => auth.user?.is_admin, () => {
  if (refreshingAuth) return
  clearTransient()
  if (active && auth.token) void refreshAuthorized()
}, { flush: 'sync' })
watch(() => route.fullPath, () => { clearTransient() }, { flush: 'sync' })
onMounted(() => { void refreshAuthorized() })

// 从其他模块切换回来时刷新数据（KeepAlive 缓存下 onMounted 只执行一次）
onActivated(() => {
  if (active) return
  active = true
  clearTransient()
  void refreshAuthorized()
})
onDeactivated(() => { active = false; clearTransient() })
onBeforeUnmount(() => { active = false; clearTransient() })
</script>

<style scoped>
.source-selector { display: flex; gap: 8px; margin: 20px 0; }
.source-selector button { border: 1px solid var(--border-color); background: white; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.source-selector button[aria-pressed="true"] { color: var(--primary); border-color: var(--primary); }
@media (max-width: 600px) {
  .toolbar-wrapper { flex-wrap: wrap; gap: 12px; }
  .search-mini { width: 100%; }
}
/* Small Spinner */
.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid var(--primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 下载遮罩 */
.dl-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 10001;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dl-dialog {
  background: #fff;
  width: 420px;
  max-width: 90vw;
  border-radius: 14px;
  padding: 28px 28px 22px;
  text-align: center;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.25);
}
.dl-spinner {
  width: 38px;
  height: 38px;
  margin: 0 auto 16px;
  border: 3px solid #e5e7eb;
  border-top-color: #059669;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.dl-stage {
  margin: 0;
  font-size: 14px;
  color: #444;
  line-height: 1.7;
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
  background: linear-gradient(135deg, #059669 0%, #10b981 100%);
  color: #fff;
  box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
  transition: all 0.2s;
}
.dl-btn:hover {
  background: linear-gradient(135deg, #047857 0%, #059669 100%);
  transform: translateY(-1px);
}

/* Toolbar */
.toolbar-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0;
}

.search-mini {
  position: relative;
  width: 240px;
  margin-bottom: 10px;
}

.search-mini input {
  width: 100%;
  padding: 8px 12px 8px 36px;
  border-radius: 100px;
  border: 1px solid var(--border-color);
  font-size: 14px;
  background: white;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.search-mini input:focus {
  border-color: var(--primary);
  outline: none;
  box-shadow: 0 0 0 3px var(--primary-light);
}

.search-mini .icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #ccc;
}

/* Gallery Grid */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

/* Pagination */
.pagination-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 40px;
  flex-wrap: wrap;
}

.page-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: white;
  border-radius: 6px;
  cursor: pointer;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-indicator {
  font-size: 14px;
  color: var(--text-sub);
}

.page-input {
  width: 60px;
  padding: 6px 8px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 14px;
  text-align: center;
  -moz-appearance: textfield;
}

.page-input::-webkit-outer-spin-button,
.page-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.page-input:focus {
  outline: none;
  border-color: var(--primary);
}

/* Empty State */
.empty-state-large {
  text-align: center;
  padding: 80px 0;
  color: var(--text-sub);
}

.empty-img {
  font-size: 64px;
  opacity: 0.5;
}

.empty-state-large .empty-tips {
  margin-top: 10px;
  color: var(--text-placeholder);
}
</style>
