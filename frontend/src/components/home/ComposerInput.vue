<template>
  <div class="creation-composer" :aria-busy="loading">
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
    <details class="more-settings">
      <summary><SlidersHorizontal :size="18" aria-hidden="true" />更多设置</summary>
      <div class="settings-content">
        <div class="reference-field">
          <label for="creation-reference" class="input-label">参考内容 <span>（选填）</span></label>
          <textarea
            id="creation-reference"
            :value="referenceContent"
            class="field reference-input"
            rows="3"
            placeholder="参考资料、产品卖点或文案素材"
            :disabled="loading || locked"
            @input="emit('update:referenceContent', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>
        <div class="reference-field">
          <label for="creation-images" class="input-label">参考图片 <span>（选填）</span></label>
          <p id="image-limits" class="field-note">JPEG、PNG 或 WebP，最多 5 张，每张不超过 10 MiB</p>
          <input
            id="creation-images"
            class="file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            :aria-describedby="imageError ? 'image-limits image-error' : 'image-limits'"
            :disabled="loading || locked || uploadedImages.length >= 5"
            @change="handleImageUpload"
          />
          <p v-if="imageError" id="image-error" class="input-error" role="alert">{{ imageError }}</p>
          <ul v-if="uploadedImages.length" class="image-list">
            <li v-for="(image, index) in uploadedImages" :key="image.preview" class="reference-image">
              <img :src="image.preview" :alt="`参考图片：${image.file.name}`" />
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
        <slot name="options" />
      </div>
    </details>
    <div class="creation-actions">
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
  </div>
</template>

<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { ArrowUpRight, LoaderCircle, SlidersHorizontal, Square, X } from 'lucide-vue-next'

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
}>(), { buttonText: '生成大纲', referenceContent: '', disabled: false, cancelling: false })
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:referenceContent', value: string): void
  (e: 'generate'): void
  (e: 'cancel'): void
  (e: 'imagesChange', images: File[]): void
}>()
const composing = ref(false)
const imageError = ref('')
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

function handleImageUpload(event: Event) {
  const input = event.target as HTMLInputElement
  if (props.loading || props.locked) { input.value = ''; return }
  const files = uploadedImages.value.map(image => image.file)
  const errors: string[] = []
  for (const file of Array.from(input.files || [])) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      errors.push(`${file.name}：仅支持 JPEG、PNG 或 WebP。`)
    } else if (file.size > 10 * 1024 * 1024) {
      errors.push(`${file.name}：文件超过 10 MiB。`)
    } else if (files.length >= 5) {
      errors.push(`${file.name}：最多添加 5 张参考图片。`)
    } else {
      files.push(file)
    }
  }
  imageError.value = errors.join(' ')
  syncPreviews(files)
  emit('imagesChange', files)
  input.value = ''
}

function removeImage(index: number) {
  if (props.loading) return
  const files = uploadedImages.value.map(image => image.file).filter((_, position) => position !== index)
  syncPreviews(files)
  imageError.value = ''
  emit('imagesChange', files)
}

function clearPreviews() {
  uploadedImages.value.forEach(image => URL.revokeObjectURL(image.preview))
  uploadedImages.value = []
}
onUnmounted(clearPreviews)
defineExpose({ clearPreviews })
</script>

<style scoped>
.creation-composer { min-width: 0; }
.input-label { display: block; margin-bottom: 10px; color: #252935; font-size: 16px; font-weight: 600; }
.input-label span, .field-note { color: #656b78; font-weight: 400; }
.topic-input, .reference-input { display: block; padding: 16px; font: inherit; font-size: 16px; line-height: 1.7; resize: vertical; background: white; border: 1px solid #d6dae2; border-radius: 8px; }
.topic-input { min-height: 172px; }
.topic-input:focus, .reference-input:focus { outline: 2px solid #315ee8; outline-offset: 2px; }
.more-settings { margin-top: 12px; border-bottom: 1px solid #e2e5eb; }
summary { display: flex; align-items: center; gap: 10px; min-height: 48px; width: fit-content; cursor: pointer; color: #505765; font-size: 16px; list-style: none; }
summary::-webkit-details-marker { display: none; }
summary::after { content: '+'; margin-left: 12px; }
details[open] > summary::after { content: '−'; }
summary:focus-visible { outline: 2px solid #315ee8; outline-offset: 2px; }
.settings-content { display: grid; gap: 24px; padding: 16px 0 24px; }
.reference-field { min-width: 0; }
.field-note { margin: 6px 0 12px; font-size: 16px; line-height: 1.6; }
.file-input { display: block; width: 100%; min-width: 0; min-height: 44px; font-size: 16px; color: #505765; }
.file-input::file-selector-button { min-height: 44px; padding: 8px 14px; margin-right: 12px; background: white; color: #252935; border: 1px solid #d6dae2; border-radius: 6px; cursor: pointer; }
.input-error { margin-top: 8px; color: #a62b35; font-size: 16px; overflow-wrap: anywhere; }
.image-list { list-style: none; padding: 0; margin: 16px 0 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 12px; }
.reference-image { min-width: 0; }
.reference-image > img { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; background: #f7f8fa; border: 1px solid #e2e5eb; border-radius: 6px; }
.image-caption { display: flex; align-items: center; gap: 4px; min-width: 0; }
.image-caption > span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 16px; }
.icon-button { width: 44px; height: 44px; flex: 0 0 44px; }
.creation-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.generate-button { background: #315ee8; color: white; min-height: 44px; border-radius: 6px; }
.generation-status { text-align: right; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spinning { animation: none; } }
</style>
