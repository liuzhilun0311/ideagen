<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { Check, Image as ImageIcon, LayoutGrid, Search, X } from 'lucide-vue-next'
import { availableImageStyles, type StyleRecommendation } from '../../features/styles/catalog'
import { usePromptCatalog } from '../../features/promptCatalog'

const props = withDefaults(defineProps<{ modelValue: string; label: string; id?: string; disabled?: boolean; recommendation?: StyleRecommendation; showDescription?: boolean }>(), { showDescription: true })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const dialog = ref<HTMLDialogElement>()
const previewDialog = ref<HTMLDialogElement>()
const preview = ref<{ name: string; url: string; label: string; detail: string } | null>(null)
const searchInput = ref<HTMLInputElement>()
const query = ref('')
const category = ref('全部')
const recent = ref<string[]>([])
const catalog = usePromptCatalog()
const imageStyles = computed(availableImageStyles)
const styleGroups = computed(() => [...new Set(imageStyles.value.filter(style => style.id !== 'auto').map(style => style.group))])
const selected = computed(() => imageStyles.value.find(style => style.id === props.modelValue || style.catalogId === props.modelValue))
const auto = computed(() => imageStyles.value.find(style => style.id === 'auto'))
const recommendedName = computed(() => imageStyles.value.find(style =>
  style.id === props.recommendation?.preset || style.catalogId === props.recommendation?.preset)?.name)
const optionValue = (style: typeof imageStyles.value[number]) => style.catalogId === props.modelValue ? props.modelValue : style.id
const recommended = computed(() => [props.recommendation?.preset, ...(props.recommendation?.alternatives || [])].filter(Boolean))
const results = computed(() => imageStyles.value.filter(style => {
  if (style.id === 'auto') return false
  if (category.value === '推荐' && !recommended.value.some(id => id === style.id || id === style.catalogId)) return false
  if (category.value === '最近' && !recent.value.some(id => id === style.id || id === style.catalogId)) return false
  if (!['全部', '推荐', '最近'].includes(category.value) && style.group !== category.value) return false
  return `${style.name} ${style.detail} ${style.scenes}`.includes(query.value.trim())
}))
const previewUrl = (style: typeof imageStyles.value[number]) => style.previewUrl
const failedPreviews = ref<string[]>([])
const hasPreview = (style: typeof imageStyles.value[number]) => !!previewUrl(style) && !failedPreviews.value.includes(style.id)
function markPreviewFailed(style: typeof imageStyles.value[number]) {
  failedPreviews.value = [...new Set([...failedPreviews.value, style.id])]
}
function openPreview(style: typeof imageStyles.value[number]) {
  const url = previewUrl(style)
  if (!url || !hasPreview(style)) return
  preview.value = { name: style.name, url, label: style.previewLabel, detail: style.previewDetail }
  previewDialog.value?.showModal()
}
function choose(value: string) {
  if (props.disabled) return
  emit('update:modelValue', value)
  recent.value = [value, ...recent.value.filter(id => id !== value)].filter(id => id !== 'auto').slice(0, 6)
  try { localStorage.setItem('ideagen-recent-styles', JSON.stringify(recent.value)) } catch { /* Storage is optional. */ }
  dialog.value?.close?.()
}
async function browse() {
  query.value = ''
  category.value = props.recommendation ? '推荐' : '全部'
  try {
    const saved = JSON.parse(localStorage.getItem('ideagen-recent-styles') || '[]')
    recent.value = Array.isArray(saved) ? saved.filter(id => imageStyles.value.some(style => style.id === id || style.catalogId === id)).slice(0, 6) : []
  } catch { recent.value = [] }
  dialog.value?.showModal()
  await nextTick()
  searchInput.value?.focus()
}
</script>

<template>
  <div class="style-select">
    <label>{{ label }}
      <span class="selection-row">
        <select :id="id" :aria-label="label" :value="modelValue" :disabled="disabled" @change="choose(($event.target as HTMLSelectElement).value)">
          <option v-if="!selected" :value="modelValue" disabled>不可用：{{ modelValue || '暂无可用风格' }}</option>
          <option v-if="auto" :value="optionValue(auto)">{{ auto.name }}{{ recommendedName ? ` · ${recommendedName}` : '' }}</option>
          <optgroup v-for="group in styleGroups" :key="group" :label="group">
            <option v-for="style in imageStyles.filter(s => s.group === group && s.id !== 'auto')" :key="style.id" :value="optionValue(style)">{{ style.name }}</option>
          </optgroup>
        </select>
        <button type="button" class="icon-button" :disabled="disabled" :aria-label="`浏览${label}`" title="浏览风格与适用场景" @click.prevent="browse"><LayoutGrid :size="18" /></button>
      </span>
    </label>
    <p v-if="selected && showDescription" class="scene"><span :style="{ background: selected.color }"></span>{{ selected.id === 'auto' && recommendation ? recommendation.reason : selected.scenes }}</p>
    <p v-if="!selected" class="scene" role="alert">所选风格已停用、删除或无权使用，请重新选择。</p>
    <p v-if="catalog.error.value" class="scene" role="status">{{ catalog.error.value }} <button type="button" :disabled="disabled || catalog.loading.value" @click="catalog.refresh">刷新目录</button></p>
    <dialog ref="dialog" class="style-dialog" @click="($event.target === dialog) && dialog?.close()">
      <header><div><h2>选择图片风格</h2><span>{{ label }} · {{ imageStyles.filter(style => style.id !== 'auto').length }} 种风格</span></div><button class="icon-button" aria-label="关闭风格选择" @click="dialog?.close()"><X :size="20" /></button></header>
      <div class="search"><Search :size="18" /><input ref="searchInput" v-model="query" aria-label="搜索风格或场景" placeholder="搜索风格或场景" /></div>
      <nav class="categories" aria-label="风格分类">
        <button v-for="group in ['全部', ...(recommendation ? ['推荐'] : []), ...(recent.length ? ['最近'] : []), ...styleGroups]" :key="group"
          :aria-pressed="category === group" @click="category = group">{{ group }}</button>
      </nav>
      <button v-if="auto" class="automatic" :disabled="disabled" @click="choose(auto.id)"><Check v-if="selected?.id === 'auto'" :size="16" />{{ auto.name }}<span v-if="recommendation">{{ imageStyles.find(s => s.id === recommendation?.preset || s.catalogId === recommendation?.preset)?.name }} · {{ recommendation.reason }}</span></button>
      <div class="style-results">
        <article v-for="style in results" :key="style.id" class="style-item" :class="{ selected: selected?.id === style.id }">
          <button class="style-choice" :disabled="disabled" :aria-pressed="selected?.id === style.id" @click="choose(style.id)">
            <span class="preview">
              <img v-if="hasPreview(style)" :src="style.previewThumbnail" :alt="`${style.name} · ${style.previewLabel}`" loading="lazy" width="384" height="512"
                @error="markPreviewFailed(style)" />
              <span v-else class="missing-preview"><ImageIcon :size="24" /><small>{{ style.previewSource === 'missing' ? style.previewLabel : '样图加载失败' }}</small></span>
            </span>
            <span class="item-heading"><strong>{{ style.name }}</strong><Check v-if="selected?.id === style.id" :size="17" /></span>
            <span>{{ style.detail }}</span><span class="scenario">适合：{{ style.scenes }}</span>
            <small v-if="style.group === '商业获客'">商业场景预设</small>
            <small>{{ style.caution }}</small>
            <small class="example-label">{{ hasPreview(style) ? style.previewLabel : style.previewSource === 'missing' ? style.previewDetail : '样图加载失败' }}</small>
          </button>
          <button v-if="hasPreview(style)" type="button" class="preview-button" @click="openPreview(style)">放大预览</button>
        </article>
      </div>
      <p v-if="!results.length" class="empty">没有匹配的风格</p>
    </dialog>
    <dialog ref="previewDialog" class="preview-dialog" @click="($event.target === previewDialog) && previewDialog?.close()">
      <header><strong>{{ preview?.name }}样图</strong><button type="button" class="icon-button" aria-label="关闭样图预览" @click="previewDialog?.close()"><X :size="20" /></button></header>
      <p class="sample-caption">{{ [preview?.label, preview?.detail].filter(Boolean).join(' · ') }}</p>
      <img v-if="preview" :src="preview.url" :alt="`${preview.name}样图`" />
    </dialog>
  </div>
</template>

<style scoped>
.style-select { min-width:0; width:100%; }
label { display:grid; gap:7px; font-size:13px; }
.selection-row { display:flex; align-items:center; gap:6px; min-width:0; }
select { width:100%; flex:1; min-width:0; padding:10px; min-height:44px; font:inherit; border:1px solid var(--border-color); border-radius:6px; background:white; color:inherit; }
.scene { display:flex; align-items:baseline; gap:6px; font-size:12px; line-height:1.6; color:var(--text-sub); margin:7px 0 0; overflow-wrap:anywhere; }
.scene>span { display:inline-block; width:9px; height:9px; flex-shrink:0; }
.style-dialog { width:min(920px, calc(100% - 32px)); max-height:calc(100dvh - 48px); margin:auto; padding:24px; border:1px solid var(--border-color); border-radius:8px; color:var(--text-main); background:white; overflow:auto; }
.style-dialog::backdrop { background:#151d3280; }
header { display:flex; align-items:center; justify-content:space-between; gap:12px; }
h2 { font-size:20px; margin:0 0 5px; } header span { color:var(--text-sub); font-size:13px; }
.search { display:flex; gap:8px; align-items:center; border:1px solid var(--border-color); padding:0 12px; margin:20px 0 12px; border-radius:6px; }
.search input { width:100%; min-width:0; min-height:44px; border:0; font:inherit; background:transparent; }
.categories { display:flex; flex-wrap:wrap; gap:6px; border-bottom:1px solid var(--border-color); margin-bottom:12px; }
.categories button { padding:10px 12px; min-height:44px; border:0; border-bottom:2px solid transparent; background:transparent; color:var(--text-sub); font:inherit; font-size:13px; }
.categories button[aria-pressed=true] { border-bottom-color:var(--primary); color:var(--primary); }
.automatic { width:100%; display:flex; gap:8px; flex-wrap:wrap; text-align:left; padding:12px 0; border:0; background:white; font:inherit; font-size:14px; }
.automatic span { color:var(--text-sub); font-size:13px; }
.style-results { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:10px; }
.style-item { display:flex; flex-direction:column; align-items:stretch; text-align:left; background:white; border:1px solid var(--border-color); border-radius:6px; color:inherit; overflow:hidden; }
.style-item.selected { border-color:var(--primary); box-shadow:0 0 0 1px var(--primary); }
.style-choice { display:flex; flex-direction:column; align-items:stretch; gap:7px; text-align:left; padding:12px; border:0; background:white; color:inherit; font:inherit; font-size:12px; line-height:1.5; }
.preview { display:block; aspect-ratio:3/4; background:#f4f6f7; }
.preview img { width:100%; height:100%; object-fit:contain; display:block; }
.missing-preview { height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; color:#7a8494; }
.missing-preview small { font-size:11px; }
.preview-button { width:100%; min-height:36px; border:0; border-top:1px solid var(--border-color); background:#fafbfc; color:var(--primary); font:inherit; font-size:12px; cursor:pointer; }
.item-heading { display:flex; gap:8px; align-items:center; justify-content:space-between; font-size:15px; }
.scenario { color:#296958; } small { font-size:11px; color:var(--text-sub); }
.example-label { margin-top:auto; padding-top:5px; color:#6c7382; }
.sample-caption { color:var(--text-sub); font-size:12px; line-height:1.5; margin:8px 0; overflow-wrap:anywhere; }
.empty { padding:28px 0; text-align:center; color:var(--text-sub); }
button { cursor:pointer; } button:focus-visible { outline:2px solid var(--primary); outline-offset:2px; }
.preview-dialog { width:min(900px,calc(100% - 32px)); max-height:calc(100dvh - 48px); margin:auto; padding:16px; border:1px solid var(--border-color); border-radius:8px; background:white; }
.preview-dialog::backdrop { background:#151d3280; }
.preview-dialog header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
.preview-dialog img { display:block; width:100%; max-height:calc(100dvh - 120px); object-fit:contain; background:#f4f6f7; }
@media(max-width:700px) { select { font-size:16px; } .style-dialog { width:calc(100% - 16px); padding:16px; max-height:calc(100dvh - 16px); } .style-results { grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; } .style-item { padding:8px; } .categories button { padding:8px; } .search input { font-size:16px; } }
@media(max-width:360px) { .style-results { grid-template-columns:1fr; } }
</style>
