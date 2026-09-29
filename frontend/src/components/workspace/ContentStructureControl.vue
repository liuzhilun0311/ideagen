<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { useStructureRevision } from '../../composables/useStructureRevision'
import { selectionItems, findItem, promptItems } from '../../features/promptCatalog'
import OutlineRecommendation from './OutlineRecommendation.vue'

const props = defineProps<{ disabled: boolean; save: () => Promise<boolean> }>()
const revision = useStructureRevision(() => props.save())
const selected = ref(revision.current.value)
watch(revision.current, value => { selected.value = value })
watch(selected, () => { if (!revision.adopting.value) revision.cancel() })
const items = computed(() => selectionItems('outline', 'organization', selected.value))
const appliedName = computed(() => findItem(promptItems('outline', 'organization'), revision.current.value)?.name || revision.current.value)
const dialog = ref<HTMLDialogElement>()
const open = () => dialog.value?.showModal()
async function adopt() { if (await revision.adopt()) dialog.value?.close() }
function close() {
  if (revision.adopting.value) return
  revision.cancel()
  dialog.value?.close()
}
</script>

<template>
  <section class="content-structure-control" aria-label="整套内容结构">
    <div class="structure-heading"><strong>内容结构</strong><span>当前：{{ appliedName }}</span></div>
    <div class="structure-actions">
      <button class="btn btn-secondary" :disabled="disabled || revision.adopting.value" @click="open">调整大纲</button>
      <OutlineRecommendation label="推荐方案与理由" />
    </div>
    <dialog ref="dialog" class="structure-dialog" aria-label="内容结构调整预览" @cancel.prevent="close">
      <header><h2>调整内容结构</h2><button class="icon-button" aria-label="关闭结构预览" :disabled="revision.adopting.value" @click="close"><X :size="20" /></button></header>
      <label>内容结构
        <select v-model="selected" aria-label="整套内容结构" :disabled="disabled || revision.loading.value || revision.adopting.value">
          <option v-for="item in items" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.name === '自动' ? '自动推荐' : item.name }}</option>
        </select>
      </label>
      <p>目标结构：{{ items.find(item => item.value === selected)?.name || selected }}</p>
      <p>生成预览将调用大纲模型，可能产生费用。确认后另存为新版本，原作品的图片和文案保留。</p>
      <button class="btn btn-primary" :disabled="disabled || revision.loading.value || revision.adopting.value"
        @click="revision.generate(selected)">{{ revision.loading.value ? '正在生成预览' : '生成结构预览' }}</button>
      <button v-if="revision.loading.value" class="btn btn-secondary" @click="revision.cancel">取消预览请求</button>
      <p v-if="revision.error.value" role="alert">{{ revision.error.value }}</p>
      <section v-if="revision.preview.value" class="structure-preview">
        <article v-for="page in revision.preview.value.pages" :key="page.index"><h3>第 {{ page.index + 1 }} 页</h3><p>{{ page.content }}</p></article>
        <button class="btn btn-primary" :disabled="disabled || revision.adopting.value" @click="adopt">{{ revision.adopting.value ? '正在保留原作品' : '确认并创建新版本' }}</button>
      </section>
    </dialog>
  </section>
</template>

<style scoped>
.content-structure-control { padding:16px 0; border-block:1px solid var(--border-color); margin:16px 0; min-width:0; }
.structure-heading,.structure-actions { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.structure-heading { margin-bottom:10px; font-size:14px; }
.structure-heading span { color:var(--text-sub); }
select { min-height:44px; min-width:160px; max-width:100%; padding:8px; border:1px solid var(--border-color); border-radius:6px; background:white; }
.structure-dialog { margin:auto; width:min(900px,calc(100vw - 32px)); max-height:85vh; padding:24px; border:1px solid var(--border-color); border-radius:8px; overflow:auto; box-sizing:border-box; }
.structure-dialog::backdrop { background:rgba(0,0,0,.35); }
header { display:flex; justify-content:space-between; align-items:center; }
h2 { font-size:18px; }
h3 { font-size:14px; }
p { font-size:14px; line-height:1.6; }
.structure-preview article { border-top:1px solid var(--border-color); padding:12px 0; }
.structure-preview article p { white-space:pre-wrap; overflow-wrap:anywhere; }
</style>
