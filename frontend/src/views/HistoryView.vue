<template>
  <div class="container" style="max-width: 1200px;">

    <!-- Header Area -->
    <div class="page-header">
      <div>
        <h1 class="page-title">我的作品</h1>
      </div>
      <div style="display: flex; gap: 10px;">
        <button
          class="btn btn-secondary btn-small"
          @click="handleScanAll"
          :disabled="isScanning"
        >
          <svg v-if="!isScanning" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
          <div v-else class="spinner-small" style="margin-right: 6px;"></div>
          {{ isScanning ? '同步中...' : '同步历史' }}
        </button>
        <button class="btn btn-primary btn-small" @click="router.push('/')">
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
      <p class="empty-tips">去创建一个新的作品吧</p>
    </div>

    <div v-else class="gallery-grid">
      <GalleryCard
        v-for="record in records"
        :key="record.id"
        :record="record"
        @preview="viewImages"
        @edit="loadRecord"
        @download="handleDownload"
        @delete="confirmDelete"
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
      @close="closeGallery"
      @edit="loadRecord"
      @download="downloadImage"
    />

    <!-- 大纲查看模态框 -->
    <OutlineModal
      v-if="showOutlineModal && viewingRecord"
      :visible="showOutlineModal"
      :pages="viewingRecord.outline.pages"
      @close="showOutlineModal = false"
    />

    <!-- 下载进行中提示 -->
    <Teleport to="body">
      <div v-if="downloadWorking" class="dl-mask">
        <div class="dl-dialog">
          <div class="dl-spinner"></div>
          <p class="dl-stage">{{ downloadStage }}</p>
        </div>
      </div>
    </Teleport>

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
            <button class="dl-btn" @click="downloadComplete = false">知道了</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onActivated } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  getHistoryList,
  getHistoryStats,
  searchHistory,
  deleteHistory,
  getHistory,
  getImageUrl,
  type HistoryRecord,
  scanAllTasks
} from '../api'
import { useGeneratorStore } from '../stores/generator'
import { runDeaiDownload, downloadAsZip } from '../composables/useDeaiDownload'

// 引入组件
import StatsOverview from '../components/history/StatsOverview.vue'
import GalleryCard from '../components/history/GalleryCard.vue'
import ImageGalleryModal from '../components/history/ImageGalleryModal.vue'
import OutlineModal from '../components/history/OutlineModal.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import { normalizeApiError, type AppError } from '../utils/errors'

const router = useRouter()
const route = useRoute()
const store = useGeneratorStore()

// 数据状态
const records = ref<HistoryRecord[]>([])
const loading = ref(false)
const stats = ref<any>(null)
const currentTab = ref('all')
const searchKeyword = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
// 页码输入框（跳转用）
const pageInput = ref(1)
watch(currentPage, (v) => { pageInput.value = v })

// 查看器状态
const viewingRecord = ref<any>(null)
const showOutlineModal = ref(false)
const isScanning = ref(false)
const error = ref<AppError | null>(null)
const successMessage = ref('')

// 下载状态
const downloadWorking = ref(false)
const downloadStage = ref('')
const downloadMessage = ref('')
const downloadComplete = ref(false)

/**
 * 加载历史记录列表
 */
async function loadData() {
  loading.value = true
  error.value = null
  try {
    let statusFilter = currentTab.value === 'all' ? undefined : currentTab.value
    const res = await getHistoryList(currentPage.value, 12, statusFilter)
    if (res.success) {
      records.value = res.records
      totalPages.value = res.total_pages
    } else {
      error.value = normalizeApiError(res.error || res.error_message || '获取历史记录列表失败', '获取历史记录列表失败')
    }
  } catch(e) {
    error.value = normalizeApiError(e, '获取历史记录列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 加载统计数据
 */
async function loadStats() {
  try {
    const res = await getHistoryStats()
    if (res.success) {
      stats.value = res
    } else {
      error.value = normalizeApiError(res.error || res.error_message || '获取统计信息失败', '获取统计信息失败')
    }
  } catch(e) {
    error.value = normalizeApiError(e, '获取统计信息失败')
  }
}

/**
 * 切换标签页
 */
function switchTab(tab: string) {
  currentTab.value = tab
  currentPage.value = 1
  loadData()
}

/**
 * 搜索历史记录
 */
async function handleSearch() {
  if (!searchKeyword.value.trim()) {
    loadData()
    return
  }
  loading.value = true
  error.value = null
  try {
    const res = await searchHistory(searchKeyword.value)
    if (res.success) {
      records.value = res.records
      totalPages.value = 1
    } else {
      error.value = normalizeApiError(res.error || res.error_message || '搜索历史记录失败', '搜索历史记录失败')
    }
  } catch(e) {
    error.value = normalizeApiError(e, '搜索历史记录失败')
  } finally {
    loading.value = false
  }
}

/**
 * 加载记录并跳转到编辑页
 */
async function loadRecord(id: string) {
  const res = await getHistory(id)
  if (res.success && res.record) {
    store.setTopic(res.record.title)
    store.setOutline(res.record.outline.raw, res.record.outline.pages)
    store.setRecordId(res.record.id)
    // 恢复已生成的文案（标题/文案/标签）
    const rc = res.record.content
    if (rc && ((rc.titles && rc.titles.length) || rc.copywriting)) {
      store.setContent(rc.titles || [], rc.copywriting || '', rc.tags || [])
    }
    const generated = res.record.images.generated || []
    if (generated.some(Boolean)) {
      store.taskId = res.record.images.task_id
      store.images = res.record.outline.pages.map((page, idx) => {
        const filename = generated[page.index] || generated[idx] || ''
        return {
          index: page.index,
          url: filename ? getImageUrl(res.record!.images.task_id || '', filename, false) : '',
          status: filename ? 'done' : 'error',
          retryable: !filename
        }
      })
    }
    store.setEntrySource('history')
    router.push('/outline')
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '打开历史记录失败', '打开历史记录失败')
  }
}

/**
 * 查看图片
 */
async function viewImages(id: string) {
  const res = await getHistory(id)
  if (res.success) {
    viewingRecord.value = res.record
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '查看图片失败', '查看图片失败')
  }
}

/**
 * 关闭图片查看器
 */
function closeGallery() {
  viewingRecord.value = null
  showOutlineModal.value = false
}

/**
 * 确认删除
 */
async function confirmDelete(record: any) {
  if(confirm('确定删除吗？')) {
    const result = await deleteHistory(record.id)
    if (result.success) {
      loadData()
      loadStats()
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '删除历史记录失败', '删除历史记录失败')
    }
  }
}

/**
 * 切换页码
 */
function changePage(p: number) {
  currentPage.value = p
  loadData()
}

/**
 * 前往输入的页码（回车/失焦触发），越界自动收敛到 1~总页数
 */
function goToPage() {
  const p = Math.min(Math.max(1, pageInput.value || 1), totalPages.value)
  changePage(p)
  pageInput.value = p
}

/**
 * 下载单张图片
 */
function downloadImage(filename: string, index: number) {
  if (!viewingRecord.value) return
  const link = document.createElement('a')
  link.href = getImageUrl(viewingRecord.value.images.task_id, filename, false)
  link.download = `page_${index + 1}.png`
  link.click()
}

/**
 * 一键下载全部（与创作完成页功能一致）：去AI化 + 选择文件夹直接写入
 */
async function handleDownload(id: string) {
  if (downloadWorking.value) return

  // 浏览器支持则立即弹出文件夹选择器（要求紧跟用户点击手势）；不支持（如 http 非 localhost）则走 zip 兜底
  let dirHandle: any = null
  if ('showDirectoryPicker' in window) {
    try {
      dirHandle = await (window as any).showDirectoryPicker({ mode: 'readwrite', startIn: 'downloads' })
    } catch (pickErr: any) {
      // 用户取消选择 → 静默结束
      return
    }
  }

  downloadWorking.value = true
  try {
    const res = await getHistory(id)
    if (!res.success || !res.record) {
      alert(res.error_message || '获取历史记录详情失败')
      return
    }
    const r = res.record
    const taskId = r.images?.task_id || ''
    if (!taskId) {
      alert('该记录没有关联的图片任务，无法下载')
      return
    }
    const generated = r.images?.generated || []
    const images = (r.outline?.pages || [])
      .map((page: any, idx: number) => {
        const filename = generated[page.index] || generated[idx] || ''
        return { index: page.index ?? idx, url: filename ? getImageUrl(taskId, filename, false) : '' }
      })
      .filter((i: any) => i.url)
    if (images.length === 0) {
      alert('该记录没有可下载的图片')
      return
    }

    const result = dirHandle
      ? await runDeaiDownload({
          dirHandle,
          taskId,
          images,
          content: {
            titles: r.content?.titles || [],
            copywriting: r.content?.copywriting || '',
            tags: r.content?.tags || []
          },
          setStage: (t) => { downloadStage.value = t }
        })
      : await downloadAsZip({
          taskId,
          images,
          content: {
            titles: r.content?.titles || [],
            copywriting: r.content?.copywriting || '',
            tags: r.content?.tags || []
          },
          setStage: (t) => { downloadStage.value = t }
        })
    downloadMessage.value = result.message
    downloadComplete.value = true
  } catch (e: any) {
    console.error('下载失败:', e)
    alert('下载失败，请稍后重试')
  } finally {
    downloadWorking.value = false
  }
}

/**
 * 扫描所有任务并同步
 */
async function handleScanAll() {
  isScanning.value = true
  try {
    const result = await scanAllTasks()
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
    console.error('扫描失败:', e)
    error.value = normalizeApiError(e, '扫描失败')
  } finally {
    isScanning.value = false
  }
}

onMounted(async () => {
  await loadData()
  await loadStats()

  // 检查路由参数，如果有 ID 则自动打开图片查看器
  if (route.params.id) {
    await viewImages(route.params.id as string)
  }

  // 自动执行一次扫描（静默，不显示结果）
  try {
    const result = await scanAllTasks()
    if (result.success && (result.synced || 0) > 0) {
      await loadData()
      await loadStats()
    }
  } catch (e) {
    console.error('自动扫描失败:', e)
  }
})

// 从其他模块切换回来时刷新数据（KeepAlive 缓存下 onMounted 只执行一次）
onActivated(async () => {
  await loadData()
  await loadStats()
})
</script>

<style scoped>
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
