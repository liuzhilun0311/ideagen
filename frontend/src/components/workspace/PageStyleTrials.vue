<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, ImagePlus, RefreshCw, Palette, AlertCircle, Maximize2 } from 'lucide-vue-next'
import { availableImageStyles, styleChoice, effectiveStyle, type ImageStyle } from '../../features/styles/catalog'
import type { ImageCandidate } from '../../api/candidates'
import { withToken } from '../../api/image'
import StyleSelect from './StyleSelect.vue'
import PaletteSelect from './PaletteSelect.vue'
import LayoutSelect from './LayoutSelect.vue'
import SuiteDiagnostics from './SuiteDiagnostics.vue'
import ImagePromptInspector from './ImagePromptInspector.vue'
import { readLayout } from '../../features/generationOptions'

const props = defineProps<{
  index: number; defaultStyle: ImageStyle; candidates: ImageCandidate[]; disabled: boolean
  controlsHost?: HTMLElement | null; hasImage?: boolean
  taskId?: string | null
  pageContent?: string
}>()
const emit = defineEmits<{
  trial: [style: ImageStyle]; adopt: [candidate: ImageCandidate]; apply: [candidate: ImageCandidate]; refresh: []
  viewingCandidate: [value: boolean]
  preview: [url: string]
  layoutChange: [layout: string]
}>()
const localStyle = ref(styleChoice(props.defaultStyle))
const chosen = ref('')
const items = computed(() => props.candidates.filter(item => item.index === props.index))
const selected = computed(() => items.value.find(item => item.id === chosen.value) || items.value.at(-1))
const view = ref<'adopted' | 'candidate'>('adopted')
const loadState = ref<'loading' | 'ready' | 'error'>('loading')
const reload = ref(0)
const actual = computed(() => effectiveStyle(localStyle.value, props.defaultStyle.recommendation))
const activeStyle = computed(() => availableImageStyles().find(style =>
  style.id === actual.value.preset || style.catalogId === actual.value.preset))
const layout = computed(() => readLayout(props.pageContent || ''))
const candidateUrl = computed(() => {
  const url = selected.value ? withToken(selected.value.image_url) : ''
  return reload.value ? `${url}${url.includes('?') ? '&' : '?'}reload=${reload.value}` : url
})
const viewingCandidate = computed(() => view.value === 'candidate' && !!selected.value)
watch(viewingCandidate, value => emit('viewingCandidate', value), { immediate: true })
watch(candidateUrl, () => { loadState.value = 'loading' })
watch(() => props.index, () => { localStyle.value = styleChoice(props.defaultStyle); chosen.value = '' })
watch(() => styleChoice(props.defaultStyle), (next, previous) => {
  for (const key of ['preset', 'notes'] as const) {
    if (localStyle.value[key] === previous[key]) localStyle.value[key] = next[key]
  }
  if (JSON.stringify(localStyle.value.palette) === JSON.stringify(previous.palette)) {
    localStyle.value.palette = next.palette ? { ...next.palette } : undefined
  } else if (localStyle.value.palette?.mode === 'auto') {
    localStyle.value.palette = { mode: 'auto', recommendation: next.palette?.recommendation, reason: next.palette?.reason }
  }
})
watch(() => items.value.length, () => { chosen.value = items.value.at(-1)?.id || '' })
watch(selected, candidate => {
  view.value = candidate && !candidate.adopted ? 'candidate' : 'adopted'
})
function selectCandidate(candidate: ImageCandidate) {
  view.value = viewingCandidate.value && selected.value?.id === candidate.id ? 'adopted' : 'candidate'
  chosen.value = candidate.id
  if (candidate.status === 'ready') localStyle.value = styleChoice(candidate.style)
}
const diagnosticCandidate = computed(() => viewingCandidate.value
  ? selected.value?.id : items.value.find(item => item.adopted)?.id)
const name = (preset: string) => availableImageStyles().find(style => style.id === preset || style.catalogId === preset)?.name || `不可用：${preset}`
</script>

<template>
  <section class="page-trials" aria-label="本页风格试验">
    <Teleport :to="controlsHost" :disabled="!controlsHost">
      <div class="trial-settings">
        <div class="panel-section execution-section">
          <button class="btn btn-primary" :disabled="disabled" @click="emit('trial', styleChoice(localStyle))"><ImagePlus :size="18" />生成本页 · 1 张</button>
        </div>
        <div class="panel-section generation-design">
          <h3>当前页设置 <span>第 {{ index + 1 }} 页</span></h3>
          <StyleSelect v-model="localStyle.preset" label="本页试用风格" :disabled="disabled" :recommendation="defaultStyle.recommendation" :show-description="false" />
          <div v-if="activeStyle" class="style-preview">
            <button v-if="activeStyle.previewUrl" class="sample-zoom" type="button" :aria-label="`放大查看${activeStyle.name}样图`" :title="activeStyle.previewLabel"
              @click="emit('preview', activeStyle.previewUrl)">
              <img :src="activeStyle.previewThumbnail" :alt="`${activeStyle.name}风格预览`" />
              <Maximize2 :size="14" />
            </button>
            <span v-else class="missing-preview">暂无样图</span>
            <div class="style-preview-description" tabindex="0" role="region" aria-label="本页风格说明"><strong>{{ activeStyle.name }}</strong><p>{{ activeStyle.detail || activeStyle.scenes }}</p><small>{{ activeStyle.previewLabel }}</small></div>
          </div>
          <PaletteSelect v-model="localStyle.palette" label="本页配色" :disabled="disabled" />
          <details class="page-layout-settings" open>
            <LayoutSelect :model-value="layout" label="单页布局" :disabled="disabled" @update:model-value="emit('layoutChange', $event)" />
            <small>只影响当前页面的内容编排，不改变整套大纲结构。</small>
          </details>
        </div>
        <div class="panel-section prompt-section"><ImagePromptInspector :index="index" :style="actual" :disabled="disabled" /></div>
        <div class="panel-section diagnostics-section">
          <SuiteDiagnostics :page-index="index" :generation-id="diagnosticCandidate" />
        </div>
      </div>
    </Teleport>
    <header class="page-preview-header"><h3>第 {{ index + 1 }} 页</h3><button class="icon-button" title="刷新候选版本" aria-label="刷新候选版本" :disabled="disabled" @click="emit('refresh')"><RefreshCw :size="16" /></button></header>
    <slot v-if="!viewingCandidate" />
    <template v-if="viewingCandidate && selected">
        <div v-if="selected.status === 'ready'" class="candidate-surface">
          <img v-show="loadState !== 'error'" :key="candidateUrl" class="candidate-image" :src="candidateUrl" :alt="`第 ${index + 1} 页${name(selected.style.preset)}候选图`" @load="loadState = 'ready'" @error="loadState = 'error'" />
          <p v-if="loadState === 'loading'" role="status">正在加载候选图</p>
          <div v-if="loadState === 'error'" class="load-error" role="alert"><AlertCircle :size="24" /><strong>图片加载失败</strong><p>生成结果已保留，无需重新生成。</p><button class="btn btn-secondary" @click="reload++"><RefreshCw :size="16" />重新加载图片</button></div>
        </div>
        <p v-else role="status">{{ selected.status === 'failed' ? '此候选图生成失败，原图片未改变' : '尚未获得生成结果，请稍后刷新候选版本，避免重复生成' }}</p>
    </template>
    <div v-if="items.length" class="candidate-strip" aria-label="候选版本">
      <button v-for="(item, number) in items" :key="item.id" :aria-pressed="viewingCandidate && selected?.id === item.id"
        :title="viewingCandidate && selected?.id === item.id ? '返回当前采用图片' : '查看此版本'"
        @click="selectCandidate(item)">
        <img v-if="item.status === 'ready'" :src="withToken(item.image_url)" alt="" loading="lazy" />
        <span v-else class="thumbnail-state"><ImagePlus :size="20" /></span>
        <strong>版本 {{ number + 1 }}</strong><span>{{ name(item.style.preset) }}</span>
        <small>{{ item.adopted ? '已采用' : item.stale ? '内容已变化' : item.status === 'failed' ? '生成失败' : item.status === 'generating' ? '生成中' : '待采用' }}</small>
      </button>
    </div>
    <template v-if="selected && (viewingCandidate || selected.adopted)">
        <div class="version-actions">
          <button v-if="viewingCandidate" class="icon-button" title="放大候选图" aria-label="放大候选图" :disabled="selected.status !== 'ready' || loadState !== 'ready'" @click="emit('preview', candidateUrl)"><Maximize2 :size="17" /></button>
          <button class="btn btn-primary" :disabled="disabled || selected.adopted || selected.stale || selected.status !== 'ready'" @click="emit('adopt', selected)"><Check :size="17" />{{ selected.adopted ? '已采用此版本' : '采用此版本' }}</button>
          <button class="btn btn-secondary" :disabled="disabled || selected.status !== 'ready'" @click="emit('apply', selected)"><Palette :size="17" />将此风格用于整套</button>
        </div>
    </template>
  </section>
</template>

<style scoped>
.page-trials { padding:16px; border-bottom:1px solid var(--border-color); display:grid; gap:14px; min-width:0; background:#fff; }
.page-preview-header { padding-bottom:12px; border-bottom:1px solid var(--border-color); }
.diagnostic-button { display:flex; align-items:center; justify-content:flex-start; gap:6px; width:100%; padding:7px 10px; border:1px solid var(--border-color); border-radius:6px; background:#fff; color:var(--text-sub); font:inherit; font-size:12px; cursor:pointer; }
.diagnostics-panel { padding:12px; border:1px solid var(--border-color); border-radius:6px; background:#fafbfd; }
.diagnostics-panel article { margin-top:10px; border-top:1px solid var(--border-color); padding-top:10px; }
.diagnostics-panel pre { max-height:300px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; font:12px/1.5 ui-monospace,Consolas,monospace; }
.diagnostics-dialog { width:min(760px,calc(100% - 24px)); max-height:calc(100dvh - 32px); overflow:auto; margin:auto; padding:20px; border:1px solid var(--border-color); border-radius:8px; color:var(--text-main); background:#fff; }
.diagnostics-dialog::backdrop { background:#151d3266; }
.diagnostics-dialog header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:16px; }
.diagnostics-dialog h2 { margin:0; font-size:18px; }
.diagnostics-dialog .diagnostics-panel { padding:0; border:0; background:transparent; }
.trial-settings { display:grid; gap:10px; padding-bottom:4px; }
.panel-section { display:grid; gap:10px; padding:12px; border:1px solid #e4e9f1; border-radius:8px; background:#fbfcfe; }
.panel-section:last-child { border-bottom:0; padding-bottom:0; }
.section-heading { display:grid; gap:3px; }
.section-heading strong { font-size:13px; color:var(--text-main); }
.section-heading small { color:var(--text-sub); font-size:11px; line-height:1.4; }
.execution-section { background:#f4f7ff; border-color:#d6e1ff; }
.execution-section .btn { min-height:46px; font-size:14px; }
.prompt-section :deep(details) { margin:0; }
.style-preview { display:grid; grid-template-columns:72px minmax(0,1fr); gap:10px; align-items:start; padding:8px 0; min-width:0; }
.style-preview img { width:72px; height:100px; object-fit:contain; border-radius:4px; background:#eef1f4; }
.style-preview-description { min-width:0; max-height:110px; overflow-y:auto; overflow-x:hidden; overflow-wrap:anywhere; scrollbar-gutter:stable; overscroll-behavior:contain; padding-right:4px; }
.style-preview-description:focus-visible { outline:2px solid var(--primary); outline-offset:2px; }
.missing-preview { color:var(--text-sub); font-size:12px; }
.sample-zoom { position:relative; padding:0; border:0; background:transparent; cursor:zoom-in; }
.sample-zoom svg { position:absolute; bottom:2px; right:2px; padding:2px; box-sizing:content-box; background:white; border-radius:3px; }
.style-preview strong { display:block; font-size:13px; }
.style-preview p { margin:4px 0; color:var(--text-sub); font-size:12px; line-height:1.45; }
.style-preview small,.page-layout-settings small { color:var(--text-sub); font-size:11px; line-height:1.4; }
.page-layout-settings { display:grid; gap:8px; }
.page-layout-settings summary { min-height:0; padding:0; }
.page-layout-settings select { font-size:13px; }
.trial-settings h3 { display:flex; justify-content:space-between; gap:8px; font-size:15px; }
.trial-settings h3 span { font-size:12px; font-weight:400; color:var(--text-sub); margin:0; line-height:1.5; }
.trial-settings .btn { width:100%; min-height:46px; font-size:14px; padding:0 10px; }
.candidate-strip { display:flex; gap:8px; overflow-x:auto; padding:3px 3px 10px; min-width:0; }
.candidate-strip button { width:92px; flex:0 0 92px; padding:6px; border:1px solid var(--border-color); border-radius:6px; display:grid; gap:4px; background:white; font:inherit; font-size:11px; text-align:left; color:inherit; }
.candidate-strip button[aria-pressed=true] { border-color:var(--primary); box-shadow:0 0 0 1px var(--primary); }
.candidate-strip img,.thumbnail-state { width:100%; height:78px; object-fit:contain; background:#f0f3f5; display:grid; place-items:center; }
.candidate-strip small { color:#296958; font-size:11px; }
.candidate-surface { min-height:300px; display:grid; place-items:center; background:#f3f5f7; position:relative; }
.candidate-surface>p { position:absolute; bottom:12px; background:white; padding:8px; font-size:13px; }
.load-error { display:grid; justify-items:center; gap:12px; padding:24px; color:var(--text-sub); text-align:center; }
.load-error p { margin:0; font-size:13px; }
button:focus-visible { outline:2px solid var(--primary); outline-offset:2px; }
header, .trial-controls, .version-actions { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
header { justify-content:space-between; }
h3 { margin:0; font-size:16px; }
label { display:grid; gap:6px; min-width:0; font-size:13px; flex:1; }
select, textarea { width:100%; min-width:0; font:inherit; padding:10px; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-card, white); color:inherit; }
textarea { resize:vertical; }
.trial-controls .btn { align-self:end; }
.candidate-image { display:block; width:100%; max-height:460px; object-fit:contain; background:#f3f5f7; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; max-height:260px; overflow:auto; font:inherit; font-size:12px; }
summary { cursor:pointer; font-size:13px; }
@media(max-width:700px) { .page-trials { padding:12px; } select, textarea { font-size:16px; } .trial-controls > * { flex-basis:100%; } .version-actions .btn { white-space:normal; } }
</style>
