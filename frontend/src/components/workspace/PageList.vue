<script setup lang="ts">
import { ArrowDown, ArrowUp, FileText, Plus, Trash2 } from 'lucide-vue-next'
import type { Page } from '../../api'
import type { GeneratedImage } from '../../stores/generator'
import type { ProcessingPage } from '../../api/postprocessing'
import type { ImageCandidate } from '../../api/candidates'

const props = defineProps<{
  pages: Page[]
  images: GeneratedImage[]
  processingPages?: ProcessingPage[]
  candidates?: ImageCandidate[]
  selected: number
  locked: boolean
}>()
defineEmits<{
  select: [index: number]
  move: [from: number, to: number]
  remove: [index: number]
  add: []
}>()
const labels: Record<Page['type'], string> = { cover: '封面', content: '内容', summary: '总结', infographic: '信息图' }
const processingLabels = { idle: '未处理', queued: '排队中', processing: '处理中', done: '已处理', error: '处理失败' }
function processingPage(index: number) { return props.processingPages?.find(page => page.index === index) }
function thumbnail(index: number) {
  const page = processingPage(index)
  return page?.adopted === 'processed' && page.processed_url
    ? page.processed_url : props.images.find(image => image.index === index)?.url
}
</script>

<template>
  <aside class="page-list" aria-label="作品结构">
    <div class="list-heading"><div><span class="eyebrow">STRUCTURE</span><h2>页面结构</h2></div><span>{{ pages.length }} 页</span></div>
    <ol>
      <li v-for="(page, index) in pages" :key="page.index">
        <button class="page-choice" :class="{ selected: selected === index }"
          :aria-current="selected === index ? 'true' : undefined" @click="$emit('select', index)">
          <span class="page-mini">
            <img v-if="thumbnail(page.index)" :src="thumbnail(page.index)" alt="" />
            <FileText v-else :size="20" aria-hidden="true" />
          </span>
          <span class="page-label"><strong>{{ String(index + 1).padStart(2, '0') }} <span>{{ labels[page.type] }}</span></strong>
            <span class="page-summary">{{ page.content || '空白页面' }}</span>
            <span v-if="processingPage(page.index)" class="processing-status"
              :class="{ 'processing-failed': processingPage(page.index)?.status === 'error' }">
              {{ processingLabels[processingPage(page.index)!.status] }}
            </span>
            <span v-else class="processing-status">{{ images.some(image => image.index === page.index && image.status === 'done') ? '已采用' : candidates?.some(candidate => candidate.index === page.index && candidate.status === 'ready') ? '有候选 · 待采用' : '未生成' }}</span>
          </span>
        </button>
        <div v-if="selected === index" class="page-actions">
          <button class="icon-button" title="上移页面" aria-label="上移页面" :disabled="locked || index === 0"
            @click="$emit('move', index, index - 1)"><ArrowUp :size="16" /></button>
          <button class="icon-button" title="下移页面" aria-label="下移页面" :disabled="locked || index === pages.length - 1"
            @click="$emit('move', index, index + 1)"><ArrowDown :size="16" /></button>
          <button class="icon-button" title="删除页面" aria-label="删除页面" :disabled="locked || pages.length <= 1"
            @click="$emit('remove', index)"><Trash2 :size="16" /></button>
        </div>
      </li>
    </ol>
    <button class="btn btn-secondary add-page" :disabled="locked" @click="$emit('add')"><Plus :size="16" />添加页面</button>
    <p v-if="images.length" class="structure-note">页面结构已关联图片</p>
  </aside>
</template>

<style scoped>
.page-list { min-width:0; padding:20px 14px; background:var(--bg-card,#fff); border-right:1px solid var(--border-color); }
.list-heading { display:flex; align-items:center; justify-content:space-between; margin:0 0 20px; gap:8px; }
.list-heading h2 { margin-top:3px; font-size:14px; font-weight:650; }
.eyebrow { color:var(--text-sub); font-size:10px; letter-spacing:.08em; }
.list-heading>span,.structure-note { font-size:12px; color:var(--text-sub); }
ol { list-style:none; display:grid; gap:8px; padding:0; }
.page-choice { width:100%; display:flex; align-items:center; gap:10px; background:transparent; border:1px solid transparent; padding:8px; border-radius:6px; text-align:left; color:inherit; }
.page-choice:hover { background:#f5f6f8; }
.page-choice.selected { border-color:#bacbfa; background:#eef3ff; }
.page-mini { width:36px; height:48px; flex-shrink:0; background:#fff; border:1px solid var(--border-color); border-radius:3px; display:grid; place-items:center; color:#768294; overflow:hidden; }
.page-mini img { width:100%; height:100%; object-fit:contain; }
.page-label { min-width:0; display:grid; gap:5px; }
.page-label strong { font-size:12px; color:var(--text-sub); font-variant-numeric:tabular-nums; }
.page-label strong span { margin-left:4px; color:var(--text-main); font-weight:500; }
.page-summary { display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:12px; }
.processing-status { font-size:11px; color:#356c59; }
.processing-status.processing-failed { color:#af352e; }
.page-actions { display:flex; justify-content:flex-end; }
.page-actions .icon-button { background:transparent; border:none; }
.add-page { width:100%; margin-top:18px; font-size:13px; padding:0 8px; }
.structure-note { margin-top:12px; line-height:1.6; }
@media(max-width:700px) { .page-list { border-right:0; padding:16px; } .page-mini { width:42px; height:56px; } .page-label strong,.page-summary { font-size:14px; } }
</style>
