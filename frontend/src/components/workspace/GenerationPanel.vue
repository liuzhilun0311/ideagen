<script setup lang="ts">
import { Image, FileText, ListTree, Square, Settings2 } from 'lucide-vue-next'
import { useGeneratorStore } from '../../stores/generator'
import type { PromptItem } from '../../api'
defineProps<{
  textModels: { name: string; label: string }[]
  imageModels: { name: string; label: string }[]
  prompts: { outline: PromptItem[]; image: PromptItem[]; content: PromptItem[] }
  busy: boolean
  phase: string | null
  cancelling: boolean
}>()
defineEmits<{ run: [kind: 'outline' | 'images' | 'content']; cancel: [] }>()
const store = useGeneratorStore()
const groups = [
  { key: 'images' as const, label: '图片生成', icon: Image, model: 'imageModelName' as const, prompt: 'imagePromptName' as const, kind: 'image' as const },
  { key: 'content' as const, label: '发布文案', icon: FileText, model: 'contentModelName' as const, prompt: 'contentPromptName' as const, kind: 'content' as const },
  { key: 'outline' as const, label: '重新规划大纲', icon: ListTree, model: 'outlineModelName' as const, prompt: 'outlinePromptName' as const, kind: 'outline' as const },
]
</script>

<template>
  <aside class="generation-panel" aria-label="生成设置">
    <h2><Settings2 :size="16" />生成设置</h2>
    <section v-for="group in groups" :key="group.key" class="generation-group">
      <h3><component :is="group.icon" :size="17" />{{ group.label }}</h3>
      <label :for="`${group.key}-model`">模型</label>
      <select :id="`${group.key}-model`" v-model="store[group.model]" class="field" :disabled="busy">
        <option v-if="!(group.key === 'images' ? imageModels : textModels).length" value="">暂无可用模型</option>
        <option v-for="model in group.key === 'images' ? imageModels : textModels" :key="model.name" :value="model.name">{{ model.label }}</option>
      </select>
      <label :for="`${group.key}-prompt`">提示词</label>
      <select :id="`${group.key}-prompt`" v-model="store[group.prompt]" class="field" :disabled="busy">
        <option value="">系统默认</option>
        <option v-for="prompt in prompts[group.kind]" :key="prompt.name" :value="prompt.name">{{ prompt.name }}</option>
      </select>
      <div v-if="group.key === 'images' && store.progress.total" class="image-progress" role="status">
        <span>已生成 {{ store.progress.current }} / {{ store.progress.total }}</span>
        <progress :max="store.progress.total" :value="store.progress.current" aria-label="图片生成进度"></progress>
      </div>
      <button v-if="phase === group.key" class="btn btn-secondary run-button" :disabled="cancelling" @click="$emit('cancel')">
        <Square :size="14" />{{ cancelling ? '正在取消' : '取消生成' }}
      </button>
      <button v-else class="btn run-button" :class="group.key === 'images' ? 'btn-primary' : 'btn-secondary'"
        :disabled="busy || !(group.key === 'images' ? imageModels : textModels).length || !store.outline.pages.length || (group.key === 'outline' && store.images.length > 0)"
        @click="$emit('run', group.key)">
        <component :is="group.icon" :size="16" />{{ group.key === 'images' ? '生成全部图片' : group.key === 'content' ? '生成文案' : '重新生成大纲' }}
      </button>
    </section>
    <RouterLink v-if="!textModels.length || !imageModels.length" to="/settings" class="model-link">配置模型 <Settings2 :size="14" /></RouterLink>
  </aside>
</template>

<style scoped>
.generation-panel { min-width:0; padding:22px 20px; background:#fff; border-left:1px solid var(--border-color); }
h2 { display:flex; align-items:center; gap:8px; font-size:14px; font-weight:600; margin-bottom:22px; }
.generation-group { padding-bottom:22px; margin-bottom:22px; border-bottom:1px solid var(--border-color); }
.generation-group:last-of-type { margin-bottom:0; border-bottom:0; padding-bottom:0; }
h3 { display:flex; align-items:center; gap:8px; font-size:13px; font-weight:600; margin-bottom:18px; }
label { display:block; font-size:12px; color:var(--text-sub); margin:12px 0 7px; }
.field { font-size:13px; padding:9px 10px; max-width:100%; }
.run-button { width:100%; margin-top:16px; padding:0 8px; font-size:13px; }
.image-progress { display:grid; gap:8px; margin-top:16px; font-size:12px; color:var(--text-sub); }
progress { width:100%; height:5px; border:0; border-radius:4px; accent-color:var(--primary); }
progress::-webkit-progress-bar { background:#e7ebf2; border-radius:4px; }
progress::-webkit-progress-value { background:var(--primary); border-radius:4px; }
.model-link { color:var(--primary); display:flex; gap:8px; align-items:center; font-size:13px; margin-top:20px; min-height:44px; }
@media(min-width:701px) and (max-width:1100px) { .generation-panel { border-top:1px solid var(--border-color); border-left:0; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:22px; } h2 { grid-column:1/-1; margin-bottom:0; } .generation-group { margin:0; } }
@media(max-width:700px) { .generation-panel { border-left:0; padding:20px 16px; } .field { font-size:16px; } .run-button { font-size:15px; } }
</style>
