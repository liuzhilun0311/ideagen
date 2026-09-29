<template>
  <!-- 历史记录卡片 -->
  <div class="gallery-card">
    <!-- 封面区域 -->
    <div class="card-cover" @click="$emit('preview', record.id)">
      <img
        v-if="record.adopted_thumbnail_url || (record.thumbnail && record.task_id)"
        :src="record.adopted_thumbnail_url ? withToken(record.adopted_thumbnail_url) : getImageUrl(record.task_id!, record.thumbnail!)"
        alt="cover"
        loading="lazy"
        decoding="async"
      />
      <div v-else class="cover-placeholder">
        <span>{{ record.title.charAt(0) }}</span>
      </div>

      <!-- 悬浮操作按钮 -->
      <div class="card-overlay">
        <button class="overlay-btn" @click.stop="$emit('preview', record.id)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
          预览
        </button>
        <button v-if="canEdit" class="overlay-btn primary" @click.stop="$emit('edit', record.id)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
          编辑
        </button>
        <button class="overlay-btn success" @click.stop="$emit('download', record.id)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          下载
        </button>
      </div>

      <!-- 状态标识 -->
      <div class="status-badge" :class="record.status">
        {{ statusText }}
      </div>
    </div>

    <!-- 底部信息 -->
    <div class="card-footer">
      <div class="card-title" :title="record.title">{{ record.title }}</div>
      <div v-if="record.owner" class="owner-label">作者：{{ record.owner.username }}</div>
      <div class="card-meta">
        <span>{{ record.page_count }}P</span>
        <span class="dot">·</span>
        <span>{{ formattedDate }}</span>

        <div class="more-actions-wrapper">
          <span v-if="!readonly && record.can_share && record.shared_count" class="sharing-count">已共享 {{ record.shared_count }} 人</span>
          <button v-if="!readonly && record.can_share" class="more-btn" title="配置用户" aria-label="配置用户" @click.stop="$emit('share', record)">
            <Users :size="16" />
          </button>
          <button v-if="canEdit" class="more-btn" title="删除作品" aria-label="删除作品" @click.stop="$emit('delete', record)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Users } from 'lucide-vue-next'
import type { HistoryPermissions } from '../../api/types'
import { getImageUrl } from '../../api'
import { withToken } from '../../api/image'

/**
 * 历史记录卡片组件
 *
 * 展示单个历史记录的封面、标题、状态等信息
 * 支持预览、编辑、删除操作
 */

// 定义记录类型
interface GalleryRecord extends HistoryPermissions {
  id: string
  title: string
  status: string
  page_count: number
  updated_at: string
  thumbnail?: string | null
  adopted_thumbnail_url?: string | null
  task_id?: string | null
}

// 定义 Props
const props = defineProps<{
  record: GalleryRecord
  readonly?: boolean
}>()
const canEdit = computed(() => !props.readonly && props.record.can_edit === true)

// 定义 Emits
defineEmits<{
  (e: 'preview', id: string): void
  (e: 'edit', id: string): void
  (e: 'download', id: string): void
  (e: 'delete', record: GalleryRecord): void
  (e: 'share', record: GalleryRecord): void
}>()

/**
 * 获取状态文本
 */
const statusText = computed(() => {
  const map: Record<string, string> = {
    draft: '草稿',
    completed: '已完成',
    generating: '生成中'
  }
  return map[props.record.status] || props.record.status
})

/**
 * 格式化日期
 */
const formattedDate = computed(() => {
  const d = new Date(props.record.updated_at)
  return `${d.getMonth() + 1}/${d.getDate()}`
})
</script>

<style scoped>
/* 卡片容器 */
.gallery-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.04);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  will-change: transform;
  contain: layout style paint;
}

.gallery-card:hover {
  transform: translateY(-4px) translateZ(0);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
}

/* 封面区域 */
.card-cover {
  aspect-ratio: 3/4;
  background: #f7f7f7;
  position: relative;
  overflow: hidden;
  cursor: pointer;
}

.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: transform;
  backface-visibility: hidden;
}

.gallery-card:hover .card-cover img {
  transform: scale(1.05) translateZ(0);
}

/* 封面占位符 */
.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  color: #e0e0e0;
  font-weight: 800;
  background: #fafafa;
}

/* 悬浮遮罩层 */
.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(2px);
  pointer-events: none;
  will-change: opacity;
}

.gallery-card:hover .card-overlay {
  opacity: 1;
  pointer-events: auto;
}
.gallery-card:focus-within .card-overlay {
  opacity: 1;
  pointer-events: auto;
}

/* 遮罩层按钮：三个按钮等宽、图标+文字统一 */
.overlay-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 112px;
  padding: 8px 16px;
  border-radius: 100px;
  border: 1px solid rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s, transform 0.1s;
  will-change: transform;
}

.overlay-btn svg {
  flex-shrink: 0;
}

.overlay-btn:hover {
  background: white;
  color: var(--text-main, #1a1a1a);
  transform: translateY(-2px);
}

.overlay-btn.primary {
  background: var(--primary, #ff2442);
  border-color: var(--primary, #ff2442);
}

.overlay-btn.primary:hover {
  background: var(--primary-hover, #e61e3a);
  color: white;
}

.overlay-btn.success {
  background: #059669;
  border-color: #059669;
}

.overlay-btn.success:hover {
  background: #047857;
  color: white;
}

/* 状态标识 */
.status-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  backdrop-filter: blur(4px);
}

.status-badge.completed {
  background: rgba(82, 196, 26, 0.9);
}

.status-badge.draft {
  background: rgba(0, 0, 0, 0.5);
}

.status-badge.generating {
  background: rgba(24, 144, 255, 0.9);
}

/* 底部区域 */
.card-footer {
  padding: 16px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-main, #1a1a1a);
}

.card-meta {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: var(--text-sub, #666);
}

.dot {
  margin: 0 6px;
}

/* 更多操作 */
.more-actions-wrapper {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
}
.owner-label { font-size: 12px; color: var(--text-sub, #666); margin-bottom: 8px; overflow-wrap: anywhere; }
.sharing-count { font-size: 11px; }

.more-btn {
  background: none;
  border: none;
  color: var(--text-sub, #666);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background-color 0.2s, color 0.2s;
  min-width: 36px;
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.more-btn:hover {
  background: #fee;
  color: #ff4d4f;
}
@media (max-width:700px), (hover:none) {
  .card-overlay {
    inset: auto 0 0;
    opacity: 1;
    pointer-events: auto;
    flex-direction: row;
    flex-wrap: wrap;
    padding: 12px;
    gap: 8px;
    background: #17212ee6;
    backdrop-filter: none;
  }
  .overlay-btn { min-width: 0; min-height: 44px; flex: 1; padding: 8px; border-radius: 6px; }
  .more-btn { min-width:44px; min-height:44px; }
  .card-meta, .more-actions-wrapper { flex-wrap:wrap; }
}
</style>
