<script setup lang="ts">
import { Image, RotateCw, AlertCircle } from 'lucide-vue-next'
import type { Page } from '../../api'
import type { GeneratedImage } from '../../stores/generator'
import type { ProcessingPage, ProcessingStrength, ProcessingVersion } from '../../api/postprocessing'
import ImageVersions from './ImageVersions.vue'

withDefaults(defineProps<{
  page?: Page; image?: GeneratedImage; locked: boolean; canRetry: boolean; showRetry?: boolean; showCanvas?: boolean; showContent?: boolean
  processingPage?: ProcessingPage; processingStrength?: ProcessingStrength; processingSubmitting?: boolean
  processingLoading?: boolean; processingError?: string
}>(), { showRetry: true, showCanvas: true, showContent: true })
defineEmits<{
  update: [value: string]; retry: []; preview: [src: string, version: ProcessingVersion]
  process: [strength: ProcessingStrength, force: boolean]
  adopt: [version: ProcessingVersion, sourceRevision: string]
}>()
</script>

<template>
  <section class="page-editor" aria-label="当前页面">
    <div v-if="page" class="page-editor-body">
      <template v-if="showCanvas">
      <div v-if="showRetry" class="canvas-toolbar">
        <span>第 {{ page.index + 1 }} 页</span>
        <div>
          <button v-if="image" class="icon-button" title="重新生成当前图片" aria-label="重新生成当前图片"
            :disabled="!canRetry" @click="$emit('retry')"><RotateCw :size="17" /></button>
        </div>
      </div>
      <ImageVersions v-if="image?.url && image.status === 'done'" :index="page.index" :original-url="image.url"
        :page="processingPage" :default-strength="processingStrength" :submitting="processingSubmitting"
        :loading="processingLoading" :load-error="processingError"
        @preview="(src, version) => $emit('preview', src, version)"
        @process="(strength, force) => $emit('process', strength, force)"
        @adopt="(version, revision) => $emit('adopt', version, revision)" />
      <div v-else class="canvas-surface">
        <div class="canvas-empty" :class="{ failed: image?.status === 'error' }">
          <template v-if="image?.status === 'generating' || image?.status === 'retrying'">
            <RotateCw class="spinning" :size="28" /><strong role="status">{{ image.status === 'retrying' ? '正在重新生成' : '正在生成图片' }}</strong>
          </template>
          <template v-else-if="image?.status === 'error'">
            <AlertCircle :size="28" /><strong>本页尚未完成</strong>
            <p>{{ image.error || '图片生成未完成' }}</p>
            <button v-if="canRetry" class="btn btn-secondary" @click="$emit('retry')"><RotateCw :size="16" />重试本页</button>
          </template>
          <template v-else><Image :size="30" /><strong>图片待生成</strong><span>第 {{ page.index + 1 }} 页</span></template>
        </div>
      </div>
      </template>
      <div v-if="showContent" class="page-copy">
        <div><label for="page-content">页面内容</label><span>{{ page.content.length }} 字</span></div>
        <textarea id="page-content" :value="page.content" :disabled="locked" rows="7"
          placeholder="页面标题、内容与画面描述" @input="$emit('update', ($event.target as HTMLTextAreaElement).value)"></textarea>
      </div>
    </div>
    <div v-else class="canvas-empty"><Image :size="28" /><strong>还没有页面</strong></div>
  </section>
</template>

<style scoped>
.page-editor { min-width:0; background:#fff; }
.canvas-toolbar { padding:0 22px; height:54px; display:flex; align-items:center; justify-content:space-between; background:#fff; border-bottom:1px solid var(--border-color); }
.canvas-toolbar>span { font-size:13px; color:var(--text-sub); }
.canvas-toolbar>div { display:flex; }
.canvas-toolbar .icon-button { border:none; background:transparent; }
.canvas-surface { min-height:420px; background:#f3f5f8; display:grid; place-items:center; padding:28px; }
.canvas-image { display:block; max-width:100%; padding:0; border:0; background:#fff; box-shadow:0 3px 16px #25293512; }
.canvas-image img { display:block; width:auto; height:auto; max-height:420px; max-width:100%; object-fit:contain; }
.canvas-empty { display:flex; align-items:center; justify-content:center; gap:13px; flex-direction:column; min-height:310px; color:#727d90; text-align:center; padding:22px; }
.canvas-empty strong { font-size:15px; font-weight:500; color:#515d70; }
.canvas-empty span,.canvas-empty p { font-size:13px; max-width:320px; overflow-wrap:anywhere; }
.canvas-empty.failed { color:#af4b2d; }
.page-copy { padding:22px; background:#fff; }
.page-copy>div { display:flex; justify-content:space-between; gap:8px; margin-bottom:12px; font-size:13px; }
.page-copy>div span { color:var(--text-sub); }
textarea { width:100%; min-height:166px; border:1px solid var(--border-color); background:#fff; color:var(--text-main); border-radius:6px; resize:vertical; padding:12px; font:inherit; font-size:15px; line-height:1.8; }
.spinning { animation:spin 1s linear infinite; }
@media(max-width:700px) { .canvas-surface { min-height:340px; padding:18px; } .canvas-empty { min-height:280px; } .page-copy { padding:18px 16px; } textarea { font-size:16px; } }
</style>
