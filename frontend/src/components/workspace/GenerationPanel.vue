<script setup lang="ts">
import { computed } from 'vue'
import { Image, FileText, ListTree, Settings2 } from 'lucide-vue-next'
import { useGeneratorStore } from '../../stores/generator'
import type { PromptItem } from '../../api'
import ImageStylePicker from './ImageStylePicker.vue'
import OutlineOptions from './OutlineOptions.vue'
import CopyOptions from './CopyOptions.vue'
import OutlinePromptInspector from './OutlinePromptInspector.vue'
const props = defineProps<{
  mode: 'images' | 'copy'
  textModels: { name: string; label: string }[]
  imageModels: { name: string; label: string }[]
  prompts: { outline: PromptItem[]; image: PromptItem[]; content: PromptItem[] }
  busy: boolean
  phase: string | null
}>()
defineEmits<{ run: [kind: 'outline'] }>()
const store = useGeneratorStore()
const groups = [
  { key: 'images' as const, label: '图片生成', icon: Image, model: 'imageModelName' as const, prompt: 'imagePromptName' as const, kind: 'image' as const },
  { key: 'content' as const, label: '发布文案', icon: FileText, model: 'contentModelName' as const, prompt: 'contentPromptName' as const, kind: 'content' as const },
]
const visibleGroups = computed(() => groups.filter(group => group.key === (props.mode === 'copy' ? 'content' : 'images')))
const outlineLocked = computed(() => props.busy || store.images.length > 0)
</script>

<template>
  <aside class="generation-panel" aria-label="生成设置">
    <div class="panel-intro"><strong>{{ mode === 'images' ? '图片参数' : '文案参数' }}</strong><span>调整后仅影响下一次生成</span></div>
    <section v-if="mode === 'images'" class="image-settings-section">
      <ImageStylePicker id="workspace" :disabled="busy" />
      <div class="image-parameters">
        <fieldset class="parameter-grid" :disabled="busy">
          <label>分辨率<select v-model="store.imageResolution" class="field"><option>AUTO</option><option>1K</option><option>2K</option><option>4K</option></select></label>
          <label>宽高比<select v-model="store.imageAspectRatio" class="field"><option>1:1</option><option>16:9</option><option>9:16</option><option>3:2</option><option>2:3</option><option>4:3</option><option>3:4</option></select></label>
          <label>质量<select v-model="store.imageQuality" class="field"><option value="auto">自动</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option><option value="ultra">超高</option><option value="highest">最高</option></select></label>
          <label>输出格式<select v-model="store.imageOutputFormat" class="field"><option value="png">PNG</option><option value="jpeg">JPEG</option><option value="webp">WebP</option></select></label>
        </fieldset>
      </div>
      <label class="reference-toggle">参考第一张图
        <select v-model="store.useCoverAsReference" :disabled="busy" aria-label="是否使用第一张图作为参考">
          <option :value="false">否</option>
          <option :value="true">是</option>
        </select>
      </label>
    </section>
    <div v-if="mode === 'images'" class="page-tools-divider" aria-hidden="true"></div>
    <slot name="page-tools" />
    <div v-for="group in visibleGroups" :key="group.key" class="generation-group">
      <label :for="`${group.key}-model`">模型</label>
      <select :id="`${group.key}-model`" v-model="store[group.model]" class="field" :disabled="busy">
        <option v-if="!(group.key === 'images' ? imageModels : textModels).length" value="">暂无可用模型</option>
        <option v-for="model in group.key === 'images' ? imageModels : textModels" :key="model.name" :value="model.name">{{ model.label }}</option>
      </select>
      <CopyOptions v-if="group.key === 'content'" :busy="busy" />
    </div>
    <details v-if="mode === 'images'" class="outline-adjustments">
      <summary>大纲调整</summary>
      <h3><ListTree :size="17" />重新规划大纲</h3>
      <OutlineOptions id="workspace" :disabled="outlineLocked" />
      <label for="outline-model">模型</label>
      <select id="outline-model" v-model="store.outlineModelName" class="field" :disabled="outlineLocked">
        <option v-if="!textModels.length" value="">暂无可用模型</option>
        <option v-for="model in textModels" :key="model.name" :value="model.name">{{ model.label }}</option>
      </select>
      <button class="btn btn-secondary run-button"
        :disabled="outlineLocked || !store.outline.pages.length || !textModels.some(model => model.name === store.outlineModelName)"
        @click="$emit('run', 'outline')"><ListTree :size="16" />{{ phase === 'outline' ? '正在生成大纲' : '重新生成大纲' }}</button>
      <RouterLink v-if="!textModels.length" to="/settings" class="model-link">配置模型 <Settings2 :size="14" /></RouterLink>
    </details>
    <details v-if="mode === 'images'" class="advanced-settings">
      <summary>高级设置：提示词与模型</summary>
      <OutlinePromptInspector :busy="busy" />
      <div class="advanced-note">模型选择和重新规划大纲会影响生成成本与内容结果，日常生成通常无需调整。</div>
    </details>
    <RouterLink v-if="!(mode === 'copy' ? textModels : imageModels).length" to="/settings" class="model-link">配置模型 <Settings2 :size="14" /></RouterLink>
  </aside>
</template>

<style scoped>
.generation-panel { min-width:0; padding:0; background:#fff; }
.panel-intro { display:flex; align-items:baseline; justify-content:space-between; gap:8px; margin-bottom:12px; }
.panel-intro strong { font-size:13px; }
.panel-intro span { color:var(--text-sub); font-size:11px; }
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
.image-settings-section { display:grid; gap:12px; padding-bottom:18px; border-bottom:1px solid var(--border-color); }
.page-tools-divider { margin-top:18px; border-top:2px solid var(--border-color); }
.section-title { display:grid; gap:3px; }
.section-title strong { font-size:13px; color:var(--text-main); }
.section-title small,.advanced-note { color:var(--text-sub); font-size:11px; line-height:1.45; }
.parameter-grid { border:0; padding:0; margin:0; min-width:0; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
.parameter-grid label { min-width:0; }
.parameter-grid select { display:block; width:100%; min-height:44px; margin-top:7px; }
summary { min-height:44px; padding:12px 0; cursor:pointer; font-size:13px; }
h2 { display:flex; align-items:center; gap:8px; font-size:14px; font-weight:600; margin-bottom:22px; }
.generation-group { padding-bottom:22px; margin-bottom:22px; border-bottom:1px solid var(--border-color); }
.generation-group:last-of-type { margin-bottom:0; border-bottom:0; padding-bottom:0; }
.outline-adjustments { margin-top:22px; border-top:1px solid var(--border-color); }
.outline-adjustments summary { min-height:44px; padding:14px 0; font-size:13px; cursor:pointer; }
.outline-adjustments summary:focus-visible { outline:2px solid var(--primary); outline-offset:3px; }
.outline-adjustments h3 { margin-top:12px; }
h3 { display:flex; align-items:center; gap:8px; font-size:13px; font-weight:600; margin-bottom:18px; }
label { display:block; font-size:12px; color:var(--text-sub); margin:12px 0 7px; }
.field { font-size:13px; padding:9px 10px; max-width:100%; }
.reference-toggle { display:flex; align-items:center; gap:8px; margin:14px 0 4px; color:var(--text-main); }
.reference-toggle input { width:16px; height:16px; margin:0; accent-color:var(--primary); }
.run-button { width:100%; margin-top:16px; padding:0 8px; font-size:13px; }
.model-link { color:var(--primary); display:flex; gap:8px; align-items:center; font-size:13px; margin-top:20px; min-height:44px; }
.advanced-settings { margin-top:20px; padding-top:4px; border-top:1px solid var(--border-color); }
.advanced-settings summary { color:var(--text-sub); }
@media(min-width:701px) and (max-width:1100px) { .generation-panel { padding:18px 12px; } }
@media(max-width:700px) { .generation-panel { border-left:0; padding:20px 16px; } .field { font-size:16px; } .run-button { font-size:15px; } }
</style>
