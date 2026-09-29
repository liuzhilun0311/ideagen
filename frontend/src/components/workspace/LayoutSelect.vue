<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { Check, Image as ImageIcon, LayoutGrid, X } from 'lucide-vue-next'
import { findLayoutItem, itemValue, layoutPreviewAlt, layoutPreviewUrl, promptItems, usePromptCatalog } from '../../features/promptCatalog'

const props = defineProps<{ modelValue: string; label?: string; id?: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const dialog = ref<HTMLDialogElement>()
const previewDialog = ref<HTMLDialogElement>()
const searchInput = ref<HTMLInputElement>()
const query = ref('')
const selectedPreview = ref<{ name: string; url: string } | null>(null)
const failedPreviews = ref<string[]>([])
const catalog = usePromptCatalog()
const layouts = computed(() => promptItems('image', 'layout'))
const layoutGroups = [
  ['role', '页面角色'],
  ['information', '信息结构'],
  ['growth', '增长结构'],
  ['media', '媒体适配'],
] as const
const category = ref('全部')
const results = computed(() => layouts.value.filter(item =>
  (category.value === '全部' || item.metadata.layout_group === category.value)
  && `${item.name} ${item.description} ${String(item.metadata.summary || '')}`.includes(query.value.trim())))
const selected = computed(() => findLayoutItem(layouts.value, props.modelValue))
function choose(value: string) {
  if (props.disabled) return
  emit('update:modelValue', value)
  dialog.value?.close()
}
async function browse() {
  query.value = ''
  dialog.value?.showModal()
  await nextTick()
  searchInput.value?.focus()
}
function openPreview(item: { name: string; metadata?: Record<string, unknown> }) {
  const url = layoutPreviewUrl(item.metadata || {})
  if (!url) return
  selectedPreview.value = { name: item.name, url }
  previewDialog.value?.showModal()
}
function missing(item: { name: string; metadata?: Record<string, unknown> }) {
  const url = layoutPreviewUrl(item.metadata || {})
  return !url || failedPreviews.value.includes(url)
}
function markPreviewFailed(item: { name: string; metadata?: Record<string, unknown> }) {
  const url = layoutPreviewUrl(item.metadata || {})
  if (url) failedPreviews.value = [...new Set([...failedPreviews.value, url])]
}
</script>

<template>
  <div class="layout-select">
    <label :for="id">{{ label || '单页布局' }}</label>
    <div class="selection-row">
      <select :id="id" :aria-label="label || '单页布局'" :value="selected ? itemValue(selected) : modelValue" :disabled="disabled"
        @change="choose(($event.target as HTMLSelectElement).value)">
        <option v-if="!selected" :value="modelValue" disabled>不可用：{{ modelValue || '暂无可用布局' }}</option>
        <option v-for="item in layouts" :key="item.id" :value="itemValue(item)">{{ item.name }}</option>
      </select>
      <button type="button" class="icon-button" :disabled="disabled" :aria-label="`浏览${label || '单页布局'}`"
        title="浏览布局与样图" @click="browse"><LayoutGrid :size="18" /></button>
    </div>
    <p v-if="selected" class="summary">{{ selected.metadata.summary || selected.description || '按内容组织页面信息。' }}</p>
    <p v-else class="summary" role="alert">所选布局已停用、删除或无权使用，请重新选择。</p>
    <p v-if="catalog.error.value" class="summary" role="status">{{ catalog.error.value }}</p>

    <dialog ref="dialog" class="layout-dialog" @click="($event.target === dialog) && dialog?.close()">
      <header><div><h2>选择单页布局</h2><span>按平台和内容目标选择更合适的页面结构</span></div>
        <button type="button" class="icon-button" aria-label="关闭布局选择" @click="dialog?.close()"><X :size="20" /></button>
      </header>
      <div class="search"><input ref="searchInput" v-model="query" aria-label="搜索布局" placeholder="搜索布局名称或说明" /></div>
      <nav class="categories" aria-label="布局分类">
        <button v-for="[value, name] in [['全部', '全部'], ...layoutGroups]" :key="value"
          type="button" :aria-pressed="category === value" @click="category = value">{{ name }}</button>
      </nav>
      <div class="layout-results">
        <article v-for="item in results" :key="item.id" class="layout-item" :class="{ selected: selected?.id === item.id }">
          <button type="button" class="layout-choice" :disabled="disabled" @click="choose(itemValue(item))">
            <span class="preview">
              <img v-if="!missing(item)" :src="layoutPreviewUrl(item.metadata)" :alt="layoutPreviewAlt(item)" loading="lazy"
                @error="markPreviewFailed(item)" />
              <span v-else class="missing-preview"><ImageIcon :size="24" /><small>{{ layoutPreviewUrl(item.metadata) ? '样图文件不存在' : '暂无样图' }}</small></span>
            </span>
            <span class="item-heading"><strong>{{ item.name }}</strong><Check v-if="selected?.id === item.id" :size="17" /></span>
            <span>{{ item.metadata.summary || item.description || '按内容组织页面信息。' }}</span>
            <small v-if="item.metadata.platforms">适合：{{ (item.metadata.platforms as string[]).join('、') }}</small>
          </button>
          <button v-if="!missing(item)" type="button" class="preview-button" @click="openPreview(item)">放大预览</button>
        </article>
      </div>
      <p v-if="!results.length" class="empty">没有匹配的布局</p>
    </dialog>
    <dialog ref="previewDialog" class="preview-dialog" @click="($event.target === previewDialog) && previewDialog?.close()">
      <button type="button" class="icon-button close-preview" aria-label="关闭样图预览" @click="previewDialog?.close()"><X :size="20" /></button>
      <img v-if="selectedPreview" :src="selectedPreview.url" :alt="`${selectedPreview.name}参考图`" />
      <p v-if="selectedPreview">{{ selectedPreview.name }}</p>
    </dialog>
  </div>
</template>

<style scoped>
.layout-select { display:grid; gap:7px; min-width:0; }
label { font-size:13px; }
.selection-row { display:flex; align-items:center; gap:6px; }
select { width:100%; min-width:0; min-height:44px; padding:10px; border:1px solid var(--border-color); border-radius:6px; background:white; font:inherit; }
.summary { margin:0; color:var(--text-sub); font-size:12px; line-height:1.6; }
.layout-dialog { width:min(920px, calc(100% - 32px)); max-height:calc(100dvh - 48px); margin:auto; padding:24px; border:1px solid var(--border-color); border-radius:8px; background:white; color:var(--text-main); overflow:auto; }
.layout-dialog::backdrop, .preview-dialog::backdrop { background:#151d3280; }
header { display:flex; justify-content:space-between; align-items:center; gap:12px; }
h2 { margin:0 0 5px; font-size:20px; } header span { color:var(--text-sub); font-size:13px; }
.search { margin:18px 0 12px; } .search input { width:100%; min-height:44px; padding:10px; border:1px solid var(--border-color); border-radius:6px; font:inherit; }
.categories { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; border-bottom:1px solid var(--border-color); }
.categories button { min-height:40px; padding:8px 10px; border:0; border-bottom:2px solid transparent; background:transparent; color:var(--text-sub); font:inherit; }
.categories button[aria-pressed=true] { color:var(--primary); border-bottom-color:var(--primary); }
.layout-results { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.layout-item { border:1px solid var(--border-color); border-radius:6px; overflow:hidden; } .layout-item.selected { border-color:var(--primary); box-shadow:0 0 0 1px var(--primary); }
.layout-choice { width:100%; display:flex; flex-direction:column; gap:7px; padding:12px; text-align:left; background:white; border:0; color:inherit; font:inherit; font-size:12px; line-height:1.5; }
.preview { display:block; aspect-ratio:3/2; background:#f4f6f7; } .preview img { width:100%; height:100%; object-fit:contain; display:block; }
.missing-preview { height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; color:#7a8494; } .missing-preview small { font-size:11px; }
.item-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:15px; } .layout-choice small { color:var(--text-sub); }
.preview-button { width:100%; min-height:36px; border:0; border-top:1px solid var(--border-color); background:#fafbfc; color:var(--primary); font:inherit; font-size:12px; cursor:pointer; }
.empty { padding:28px 0; text-align:center; color:var(--text-sub); }
.preview-dialog { width:min(900px, calc(100% - 32px)); max-height:calc(100dvh - 48px); margin:auto; padding:20px; border:1px solid var(--border-color); border-radius:8px; background:white; }
.preview-dialog img { display:block; max-width:100%; max-height:calc(100dvh - 120px); margin:auto; object-fit:contain; } .preview-dialog p { margin:10px 0 0; text-align:center; color:var(--text-sub); }
.close-preview { display:block; margin-left:auto; }
.icon-button { display:inline-grid; place-items:center; min-width:40px; min-height:40px; padding:8px; border:1px solid var(--border-color); border-radius:6px; background:white; cursor:pointer; }
@media(max-width:700px) { .layout-dialog { width:calc(100% - 16px); padding:16px; } .layout-results { grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; } .layout-choice { padding:8px; } select, .search input { font-size:16px; } }
@media(max-width:360px) { .layout-results { grid-template-columns:1fr; } }
</style>
