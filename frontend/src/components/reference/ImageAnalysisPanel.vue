<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { ImagePlus, LoaderCircle, Save, Sparkles, X } from 'lucide-vue-next'
import { analyzeImage, createPromptsFromAnalysis, createReferenceAsset, type AnalysisPart, type ImageAnalysis } from '../../api/imageAnalysis'
import { normalizeApiError } from '../../utils/errors'

const props = withDefaults(defineProps<{
  context: 'home' | 'workspace' | 'prompt-center'
  topic?: string
  pageContent?: string
  models?: { name: string; label: string }[]
  model?: string
}>(), { topic: '', pageContent: '' })

const emit = defineEmits<{
  close: []
  apply: [analysis: ImageAnalysis, parts: AnalysisPart[], mode: 'merge' | 'replace']
  saved: []
  'update:model': [value: string]
}>()

const file = ref<File | null>(null)
const previewUrl = ref('')
const analysis = ref<ImageAnalysis | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const mode = ref<'merge' | 'replace'>('merge')
const parts = ref<AnalysisPart[]>(props.context === 'prompt-center' ? ['layout', 'visual_style'] : ['content', 'layout', 'visual_style'])
const title = ref('图片参考素材')

function selectFile(event: Event) {
  const nextFile = (event.target as HTMLInputElement).files?.[0] || null
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  file.value = nextFile
  previewUrl.value = nextFile ? URL.createObjectURL(nextFile) : ''
  analysis.value = null
  error.value = ''
}

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})

function togglePart(part: AnalysisPart) {
  parts.value = parts.value.includes(part) ? parts.value.filter(item => item !== part) : [...parts.value, part]
}

async function run() {
  if (!file.value || loading.value) return
  loading.value = true
  error.value = ''
  const result = await analyzeImage(file.value, {
    topic: props.topic,
    pageContent: props.pageContent,
    saveSource: true,
    providerName: props.model,
  })
  loading.value = false
  if (!result.success || !result.analysis) {
    error.value = normalizeApiError(result.error || result.error_message || '图片分析失败', '图片分析失败').detail
    return
  }
  analysis.value = result.analysis
}

async function saveContent() {
  if (!analysis.value || saving.value || props.context === 'prompt-center') return
  saving.value = true
  const result = await createReferenceAsset({
    analysis_id: analysis.value.id,
    title: title.value,
    content: analysis.value.content,
    rewritten_content: analysis.value.rewritten_content,
  })
  saving.value = false
  if (!result.success) {
    error.value = normalizeApiError(result.error || result.error_message || '保存参考素材失败', '保存参考素材失败').detail
    return
  }
  emit('saved')
}

async function savePrompts() {
  if (!analysis.value || saving.value || props.context !== 'prompt-center') return
  saving.value = true
  const result = await createPromptsFromAnalysis({
    analysis_id: analysis.value.id,
    parts: parts.value.filter(part => part !== 'content'),
    names: { layout: '图片参考布局', visual_style: '图片参考风格' },
    drafts: {
      layout: { content: analysis.value.layout.prompt_text, description: analysis.value.layout.description },
      visual_style: { content: analysis.value.visual_style.prompt_text, description: analysis.value.visual_style.description },
    },
  })
  saving.value = false
  if (!result.success) {
    error.value = normalizeApiError(result.error || result.error_message || '保存提示词失败', '保存提示词失败').detail
    return
  }
  emit('saved')
}
</script>

<template>
  <section class="analysis-panel" aria-label="图片分析">
    <header class="analysis-header">
      <div><h2>分析参考图片</h2><p>分别识别内容、单页布局和图片风格。</p></div>
      <button class="icon-button" type="button" aria-label="关闭图片分析" title="关闭" @click="$emit('close')"><X :size="18" /></button>
    </header>
    <label class="upload-zone">
      <ImagePlus :size="20" aria-hidden="true" />
      <span>{{ file?.name || '选择一张参考图片' }}</span>
      <input type="file" accept="image/jpeg,image/png,image/webp" @change="selectFile" />
    </label>
    <img v-if="previewUrl" class="upload-preview" :src="previewUrl" alt="已选择的参考图片" />
    <label v-if="models" class="model-select">
      <span>分析模型</span>
      <select :value="model" :disabled="loading" @change="$emit('update:model', ($event.target as HTMLSelectElement).value)">
        <option v-if="!models.length" value="">暂无可用模型</option>
        <option v-for="item in models" :key="item.name" :value="item.name">{{ item.label }}</option>
      </select>
    </label>
    <button class="btn btn-primary" type="button" :disabled="!file || loading" @click="run">
      <LoaderCircle v-if="loading" :size="16" class="spinning" />
      <Sparkles v-else :size="16" />
      {{ loading ? '正在分析' : '开始分析' }}
    </button>
    <p v-if="error" class="analysis-error" role="alert">{{ error }}</p>
    <template v-if="analysis">
      <div class="analysis-options">
        <label v-for="part in (['content', 'layout', 'visual_style'] as AnalysisPart[])" :key="part">
          <input type="checkbox" :checked="parts.includes(part)" :disabled="context === 'prompt-center' && part === 'content'" @change="togglePart(part)" />
          {{ part === 'content' ? '内容' : part === 'layout' ? '单页布局' : '图片风格' }}
        </label>
        <select v-model="mode" aria-label="应用方式">
          <option value="merge">合并到当前创作</option>
          <option value="replace">替换对应设置</option>
        </select>
      </div>
      <div class="analysis-sections">
        <article><h3>内容</h3><textarea v-model="analysis.content.summary" rows="4" aria-label="内容分析"></textarea><textarea v-model="analysis.rewritten_content" rows="4" aria-label="可复用改写内容" placeholder="可复用改写内容"></textarea></article>
        <article>
          <h3>单页布局</h3>
          <img v-if="previewUrl" class="analysis-preview" :src="previewUrl" alt="单页布局参考图" />
          <textarea v-model="analysis.layout.prompt_text" rows="6" aria-label="单页布局提示词" placeholder="单页布局提示词"></textarea>
        </article>
        <article>
          <h3>图片风格</h3>
          <img v-if="previewUrl" class="analysis-preview" :src="previewUrl" alt="图片风格参考图" />
          <textarea v-model="analysis.visual_style.prompt_text" rows="6" aria-label="图片风格提示词" placeholder="图片风格提示词"></textarea>
        </article>
      </div>
      <div class="analysis-actions">
        <input v-if="context !== 'prompt-center'" v-model="title" class="field" aria-label="参考素材名称" />
        <button v-if="context !== 'prompt-center'" class="btn btn-secondary" type="button" :disabled="saving" @click="saveContent"><Save :size="16" />保存内容素材</button>
        <button v-else class="btn btn-secondary" type="button" :disabled="saving || !parts.some(part => part !== 'content')" @click="savePrompts"><Save :size="16" />保存为提示词</button>
        <button v-if="context !== 'prompt-center'" class="btn btn-primary" type="button" :disabled="!parts.length" @click="$emit('apply', analysis, parts, mode)">应用所选部分</button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.analysis-panel { display: grid; gap: 16px; padding: 20px; border: 1px solid #d6dae2; border-radius: 8px; background: #fff; }
.analysis-header { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
.analysis-header h2 { margin:0; font-size:20px; }
.analysis-header p { margin:5px 0 0; color:#656b78; font-size:13px; }
.upload-zone { display:flex; align-items:center; gap:10px; min-height:52px; padding:12px; border:1px dashed #aeb8c8; border-radius:6px; cursor:pointer; }
.upload-zone input { width:1px; height:1px; opacity:0; position:absolute; }
.upload-preview { display:block; width:100%; max-height:320px; border:1px solid #e2e5eb; border-radius:6px; object-fit:contain; background:#f5f6f8; }
.model-select { display:grid; gap:6px; max-width:420px; color:#505765; font-size:13px; }
.model-select select { min-height:40px; padding:7px 10px; border:1px solid #d6dae2; border-radius:6px; background:#fff; color:#252c32; }
.analysis-options { display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center; }
.analysis-options label { display:flex; align-items:center; gap:6px; min-height:36px; }
.analysis-options select { min-height:40px; padding:7px 10px; border:1px solid #d6dae2; border-radius:6px; }
.analysis-sections { display:grid; gap:10px; grid-template-columns:repeat(3,minmax(0,1fr)); }
.analysis-sections article { min-width:0; padding:14px; border:1px solid #e2e5eb; border-radius:6px; }
.analysis-sections h3 { margin:0 0 8px; font-size:15px; }
.analysis-preview { display:block; width:100%; max-height:240px; margin:0 0 10px; border-radius:4px; object-fit:contain; background:#f5f6f8; }
.analysis-sections p { margin:0 0 8px; white-space:pre-wrap; overflow-wrap:anywhere; color:#505765; line-height:1.6; }
.analysis-actions { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; }
.analysis-actions .field { flex:1 1 180px; min-height:44px; }
.analysis-error { margin:0; color:#a62b35; }
.spinning { animation:spin 1s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
@media(max-width:700px) { .analysis-sections { grid-template-columns:1fr; } .analysis-actions { justify-content:stretch; } .analysis-actions>* { flex:1 1 100%; } }
</style>
