<script setup lang="ts">
import { computed, ref } from 'vue'
import { Lightbulb, X } from 'lucide-vue-next'
import { useGeneratorStore } from '../../stores/generator'
import RecommendationSummary from './RecommendationSummary.vue'
import { findItem, promptItems } from '../../features/promptCatalog'

withDefaults(defineProps<{ label?: string }>(), { label: '本次推荐方案' })
const store = useGeneratorStore()
const recommendation = computed(() => store.outline.growth_recommendation)
const dialog = ref<HTMLDialogElement>()
const currentStructure = computed(() => {
  const value = store.outline.generation_preferences?.organization || store.outline.organization || '自动'
  return findItem(promptItems('outline', 'organization'), value)?.name || value
})
</script>

<template>
  <button class="btn btn-secondary" :disabled="!store.outline.pages.length" @click="dialog?.showModal()">
    <Lightbulb :size="18" />{{ label }}
  </button>
  <dialog ref="dialog" class="recommendation-dialog" aria-label="大纲推荐方案"
    @click="($event.target === dialog) && dialog?.close()">
    <header>
      <h2>推荐详情</h2>
      <button class="icon-button" aria-label="关闭推荐方案" @click="dialog?.close()"><X :size="20" /></button>
    </header>
    <RecommendationSummary v-if="recommendation" :recommendation="recommendation" />
    <p v-else role="status">这份大纲没有保存推荐方案。可继续手动设置图片风格和布局，重新生成大纲后会获取新推荐。</p>
    <p>当前内容结构：{{ currentStructure }}</p>
  </dialog>
</template>

<style scoped>
.recommendation-dialog { margin:auto; width:min(760px, calc(100vw - 32px)); max-height:85vh; overflow:auto; padding:24px; box-sizing:border-box; border:1px solid var(--border-color); border-radius:8px; color:var(--text-main); background:var(--bg-card, #fff); }
.recommendation-dialog::backdrop { background:rgba(0,0,0,.35); }
header { display:flex; justify-content:space-between; align-items:center; gap:16px; }
h2 { font-size:18px; margin:0; }
p { font-size:14px; line-height:1.6; }
@media(max-width:700px) { .recommendation-dialog { padding:16px; } }
</style>
