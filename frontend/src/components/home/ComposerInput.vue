<template>
  <!-- 创作输入组合框：主题 / 参考内容 / 参考图片 三分区 -->
  <div class="composer-container">
    <!-- ① 主题（必填） -->
    <div class="composer-field">
      <div class="field-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
        </svg>
        <span class="field-title">主题</span>
        <span class="field-badge required">必填</span>
      </div>
      <div class="composer-input-wrapper">
        <textarea
          ref="textareaRef"
          :value="modelValue"
          @input="handleInput"
          class="composer-textarea"
          placeholder="一句话描述你想创作的内容"
          @keydown.enter.prevent="handleEnter"
          :disabled="loading"
          rows="1"
        ></textarea>
        <button
          v-if="modelValue"
          type="button"
          class="clear-input-btn"
          title="清空输入"
          @click="clearTopic"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>

    <!-- ② 参考内容（选填） -->
    <div class="composer-field">
      <div class="field-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8a6d3b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
        </svg>
        <span class="field-title">参考内容</span>
        <span class="field-badge optional">选填</span>
      </div>
      <div class="ref-input-row">
        <textarea
          ref="referenceRef"
          :value="referenceContent"
          @input="handleReferenceInput"
          class="ref-textarea"
          placeholder="粘贴参考资料、产品卖点、文案素材、笔记内容等…"
          :disabled="loading"
          rows="3"
        ></textarea>
        <button
          v-if="referenceContent"
          type="button"
          class="clear-input-btn"
          title="清空输入"
          @click="clearReference"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="field-footer">
        <span></span>
        <span v-if="referenceContent" class="field-count">{{ referenceContent.length }} 字</span>
      </div>
    </div>

    <!-- ③ 参考图片（选填，一张或多张） -->
    <div class="composer-field">
      <div class="field-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <circle cx="8.5" cy="8.5" r="1.5"></circle>
          <polyline points="21 15 16 10 5 21"></polyline>
        </svg>
        <span class="field-title">参考图片</span>
        <span class="field-badge optional">选填</span>
      </div>
      <label class="image-upload-card" :class="{ 'has-images': uploadedImages.length > 0 }">
        <input
          type="file"
          accept="image/*"
          multiple
          @change="handleImageUpload"
          :disabled="loading"
          style="display: none;"
        />
        <div v-if="uploadedImages.length > 0" class="image-thumbs">
          <div
            v-for="(img, idx) in uploadedImages"
            :key="idx"
            class="uploaded-image-item"
          >
            <img :src="img.preview" :alt="`参考图 ${idx + 1}`" />
            <button class="remove-image-btn" type="button" @click.prevent.stop="removeImage(idx)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
            <span class="image-index">{{ idx + 1 }}</span>
          </div>
          <div v-if="uploadedImages.length < 5" class="image-add-tile">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            <span>添加照片</span>
          </div>
        </div>
        <div v-else class="image-upload-placeholder">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="3"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
          </svg>
          <span>点击上传参考图片</span>
        </div>
      </label>
    </div>

    <!-- 工具栏（生成按钮） -->
    <div class="composer-toolbar">
      <div class="toolbar-left"></div>
      <div class="toolbar-right">
        <!-- 插槽：可放"生成大纲"提示词选择等 -->
        <slot name="before-generate" />
        <button
          class="btn btn-primary generate-btn"
          @click="$emit('generate')"
          :disabled="!modelValue.trim() || loading"
        >
          <span v-if="loading" class="spinner-sm"></span>
          <span>{{ loading ? '处理中' : buttonText }}</span>
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-hint" role="status" aria-live="polite">
      请稍后，这一步大概要 15-30 秒左右。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'

/**
 * 主题输入组合框组件
 *
 * 功能：
 * - 主题文本输入（必填，自动调整高度）
 * - 参考内容输入（选填，支持大段文字）
 * - 参考图片上传（选填，最多5张）
 * - 生成按钮
 */

// 定义上传的图片类型
interface UploadedImage {
  file: File
  preview: string
}

// 定义 Props
const props = defineProps<{
  modelValue: string
  loading: boolean
  /** 生成按钮文案（可覆盖，如"进入编辑大纲"） */
  buttonText?: string
  /** 参考内容（选填） */
  referenceContent?: string
}>()

// 定义 Emits
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:referenceContent', value: string): void
  (e: 'generate'): void
  (e: 'imagesChange', images: File[]): void
}>()

// 输入框引用
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const referenceRef = ref<HTMLTextAreaElement | null>(null)

// 已上传的图片
const uploadedImages = ref<UploadedImage[]>([])

/**
 * 处理输入变化
 */
function handleInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
  adjustHeight()
}

/**
 * 处理回车键
 */
function handleEnter(e: KeyboardEvent) {
  if (e.shiftKey) return // 允许 Shift+Enter 换行
  emit('generate')
}

/**
 * 清空主题输入（× 按钮）
 */
function clearTopic() {
  emit('update:modelValue', '')
  adjustHeight()
}

/**
 * 清空参考内容输入（× 按钮）
 */
function clearReference() {
  emit('update:referenceContent', '')
  adjustReferenceHeight()
}

/**
 * 处理参考内容输入变化
 */
function handleReferenceInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:referenceContent', target.value)
  adjustReferenceHeight()
}

/**
 * 自动调整输入框高度
 */
function adjustHeight() {
  const el = textareaRef.value
  if (!el) return

  el.style.height = 'auto'
  const newHeight = Math.max(44, Math.min(el.scrollHeight, 120))
  el.style.height = newHeight + 'px'
}

/**
 * 自动调整参考内容输入框高度
 */
function adjustReferenceHeight() {
  const el = referenceRef.value
  if (!el) return

  el.style.height = 'auto'
  const newHeight = Math.max(72, Math.min(el.scrollHeight, 240))
  el.style.height = newHeight + 'px'
}

/**
 * 处理图片上传
 */
function handleImageUpload(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files) return

  const files = Array.from(target.files)
  files.forEach((file) => {
    // 限制最多 5 张图片
    if (uploadedImages.value.length >= 5) {
      return
    }
    // 创建预览 URL
    const preview = URL.createObjectURL(file)
    uploadedImages.value.push({ file, preview })
  })

  // 通知父组件
  emitImagesChange()

  // 清空 input，允许重复选择同一文件
  target.value = ''
}

/**
 * 移除图片
 */
function removeImage(index: number) {
  const img = uploadedImages.value[index]
  // 释放预览 URL
  URL.revokeObjectURL(img.preview)
  uploadedImages.value.splice(index, 1)

  // 通知父组件
  emitImagesChange()
}

/**
 * 通知父组件图片变化
 */
function emitImagesChange() {
  const files = uploadedImages.value.map(img => img.file)
  emit('imagesChange', files)
}

/**
 * 清理所有预览 URL
 */
function clearPreviews() {
  uploadedImages.value.forEach(img => URL.revokeObjectURL(img.preview))
  uploadedImages.value = []
}

// 组件卸载时清理
onUnmounted(() => {
  clearPreviews()
})

// 暴露方法给父组件
defineExpose({
  clearPreviews
})
</script>

<style scoped>
/* 组合框容器 */
.composer-container {
  background: white;
  border-radius: 16px;
  padding: 18px 18px 14px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

/* ===== 分区通用 ===== */
.composer-field {
  padding: 12px 14px;
  border-radius: 12px;
}

.composer-field + .composer-field {
  margin-top: 10px;
}

/* 主题：浅蓝底 */
.composer-field:first-of-type {
  background: #f5f9ff;
  border: 1px solid #dbe7ff;
}
.composer-field:first-of-type:focus-within {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
}

/* 参考内容：浅米底 */
.composer-field:nth-of-type(2) {
  background: #fbfaf5;
  border: 1px solid #eee7d3;
}
.composer-field:nth-of-type(2):focus-within {
  border-color: #d9b878;
  box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.08);
}

/* 参考图片：浅紫底 */
.composer-field:nth-of-type(3) {
  background: #faf7ff;
  border: 1px solid #e8dfff;
}

/* 分区标题 */
.field-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.field-title {
  font-size: 13px;
  font-weight: 600;
  color: #4a4a4a;
}

/* 必填/选填标记 */
.field-badge {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 10px;
  font-weight: 500;
}
.field-badge.required {
  color: #dc2626;
  background: #fef2f2;
}
.field-badge.optional {
  color: #a8916a;
  background: #f6efdf;
}

/* ===== 主题输入 ===== */
.composer-input-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.composer-textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 16px;
  line-height: 1.6;
  resize: none;
  min-height: 40px;
  max-height: 120px;
  padding: 4px 0;
  font-family: inherit;
  color: var(--text-main, #1a1a1a);
}

.composer-textarea::placeholder {
  color: #9bb1d8;
}

.composer-textarea:disabled {
  background: transparent;
  color: #999;
}

/* 清空按钮（主题/参考内容通用） */
.clear-input-btn {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.08);
  color: #999;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 8px;
  transition: all 0.2s;
}

.clear-input-btn:hover {
  background: rgba(0, 0, 0, 0.16);
  color: #555;
}

/* ===== 参考内容输入 ===== */
.ref-input-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.ref-textarea {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.7;
  resize: vertical;
  font-family: inherit;
  color: #3b3226;
}

.ref-textarea::placeholder {
  color: #b3a48a;
}

.ref-textarea:disabled {
  background: transparent;
  color: #999;
}

/* 分区脚注 */
.field-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
}

.field-hint {
  font-size: 12px;
  color: #a8916a;
}

.field-count {
  font-size: 12px;
  color: #c0ab86;
  font-variant-numeric: tabular-nums;
}

/* ===== 参考图片上传卡片 ===== */
.image-upload-card {
  display: block;
  cursor: pointer;
  border: 1.5px dashed #c9b8f0;
  border-radius: 10px;
  background: rgba(124, 58, 237, 0.03);
  transition: border-color 0.2s, background 0.2s;
}

.image-upload-card:hover {
  border-color: #8b5cf6;
  background: rgba(124, 58, 237, 0.06);
}

.image-upload-card.has-images {
  border-style: solid;
  border-color: #ddd2f2;
}

.image-upload-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  color: #8b5cf6;
  font-size: 13px;
}

/* 缩略图网格 */
.image-thumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px;
}

.uploaded-image-item {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  flex-shrink: 0;
}

.uploaded-image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-index {
  position: absolute;
  left: 4px;
  bottom: 4px;
  min-width: 16px;
  height: 16px;
  padding: 0 3px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.55);
  color: white;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-image-btn {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  opacity: 0;
  transition: opacity 0.2s;
}

.uploaded-image-item:hover .remove-image-btn {
  opacity: 1;
}

.remove-image-btn:hover {
  background: var(--primary, #ff2442);
}

/* 添加照片格子 */
.image-add-tile {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  border: 1.5px dashed #c9b8f0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: #8b5cf6;
  font-size: 11px;
  flex-shrink: 0;
  transition: all 0.2s;
}

.image-add-tile:hover {
  background: rgba(124, 58, 237, 0.06);
}

/* ===== 工具栏 ===== */
.composer-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: flex-end;
  width: 100%;
}

/* 生成按钮 */
.generate-btn {
  min-width: 112px;
  padding: 10px 24px;
  font-size: 15px;
  border-radius: 100px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-hint {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 36, 66, 0.06);
  color: var(--text-sub, #666);
  font-size: 14px;
  line-height: 1.5;
  text-align: right;
}

/* 加载动画 */
.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>