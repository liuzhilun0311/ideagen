<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Copy, Eye, History, Pencil, Plus, RefreshCw, Search, ShieldCheck, Users, Image, Sparkles, X } from 'lucide-vue-next'
import LegacyPromptLibrary from '../components/prompts/LegacyPromptLibrary.vue'
import PromptEntryEditor from '../components/prompts/PromptEntryEditor.vue'
import PromptVersionHistory from '../components/prompts/PromptVersionHistory.vue'
import ReorderControls from '../components/common/ReorderControls.vue'
import { modules, usePromptCenter } from '../components/prompts/usePromptCenter'
import type { PromptEntry } from '../api/promptCenter'
import ImageAnalysisPanel from '../components/reference/ImageAnalysisPanel.vue'
import { useCreationOptions } from '../composables/useCreationOptions'
import { useGeneratorStore } from '../stores/generator'
import { referenceAssetImageUrl } from '../api/referenceAssets'
import { resolveStylePreview } from '../features/styles/samplePreview'

const center = usePromptCenter()
const {
  auth, activeModule, category, categories, legacy, search, filtered, draft, readonly,
  users, usersLoading, usersError, history, versions, historyLoading, busy, loading,
  dirty, error, conflict, notice,
} = center
const visibility = { private: '仅自己', selected: '指定用户', public: '所有用户' }
const layoutPreviews: Record<string, string> = {
  封面: 'cover',
  清单: 'list',
  步骤: 'steps',
  对比: 'compare',
  分类: 'category',
  关系: 'relation',
  例子: 'example',
  总结: 'summary',
}
const panelOpen = computed(() => !!draft.value || !!history.value)
const imageAnalysisDialog = ref<HTMLDialogElement | null>(null)
const previewDialog = ref<HTMLDialogElement | null>(null)
const previewImage = ref('')
const previewTitle = ref('')
const previewCaption = ref('')
const failedPreviews = ref<string[]>([])
const generatorStore = useGeneratorStore()
const { textModels, load: loadOptions } = useCreationOptions()
const analysisModel = ref(generatorStore.outlineModelName)
onBeforeRouteLeave(() => center.discard())
onMounted(async () => {
  await loadOptions()
  if (!textModels.value.some(model => model.name === analysisModel.value)) {
    analysisModel.value = generatorStore.outlineModelName
  }
})
async function edit(entry?: PromptEntry) {
  center.open(entry)
  await nextTick()
  document.querySelector('.entry-editor')?.scrollIntoView({ block: 'nearest' })
}
function preview(entry: PromptEntry): string {
  if (failedPreviews.value.includes(entry.id)) return ''
  if (entry.module === 'image' && entry.category === 'style') return stylePreview(entry).url
  const referenceAssetId = entry.metadata?.reference_asset_id
  if (typeof referenceAssetId === 'string' && referenceAssetId) return referenceAssetImageUrl(referenceAssetId)
  const previewUrl = entry.metadata?.preview_url
  if (typeof previewUrl === 'string' && /^(\/(?!\/)|https?:\/\/)/.test(previewUrl)) return previewUrl
  if (entry.module === 'image' && entry.category === 'layout') {
    const layoutId = typeof entry.metadata?.preview === 'string' ? entry.metadata.preview : layoutPreviews[entry.name]
    if (layoutId) return `/assets/layouts/${layoutId}.png`
  }
  return ''
}
function stylePreview(entry: PromptEntry) {
  return resolveStylePreview({ ...entry, legacyValue: entry.legacy_value || undefined })
}
function thumbnail(entry: PromptEntry) {
  return entry.category === 'style' ? stylePreview(entry).thumbnail : preview(entry)
}
function summary(entry: PromptEntry): string {
  if (entry.module === 'image' && entry.category === 'layout') {
    const summaries: Record<string, string> = {
      自动: '根据页面信息量自动选择清晰易读的排版。',
      封面: '突出标题和一个视觉主体，适合开场页或主题介绍。',
      清单: '用编号或短标签整齐排列多个要点，适合收藏型内容。',
      步骤: '沿着明确顺序组织内容，适合教程、流程和操作说明。',
      对比: '把两个或多个对象并排展示，方便比较差异。',
      分类: '把内容按类别分组，适合知识整理和主题归纳。',
      关系: '用中心主体、节点和连线表达关联关系。',
      例子: '先突出一个具体示例，再配合解释帮助理解。',
      总结: '集中呈现核心结论和行动提醒，减少装饰干扰。',
    }
    return summaries[entry.name] || entry.description || '用于控制单页内容的排版方式。'
  }
  if (entry.module === 'image' && entry.category === 'style') {
    const detail = typeof entry.metadata?.detail === 'string' ? entry.metadata.detail : ''
    const scenes = typeof entry.metadata?.scenes === 'string' ? entry.metadata.scenes : ''
    return [detail, scenes ? `适合：${scenes}` : ''].filter(Boolean).join('。') || entry.description || '用于控制图片的视觉表现方式。'
  }
  return entry.description || '暂无说明'
}
function openPreview(entry: PromptEntry) {
  const url = preview(entry)
  if (!url) return
  previewImage.value = url
  previewTitle.value = `${entry.name}样图`
  previewCaption.value = entry.category === 'style'
    ? [stylePreview(entry).label, stylePreview(entry).detail].filter(Boolean).join(' · ') : '布局示意图'
  previewDialog.value?.showModal()
}
function date(value?: string) {
  if (!value) return '未记录'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-CN', { hour12: false })
}
</script>

<template>
  <main class="container prompt-center">
    <header class="center-header"><h1>提示词管理中心</h1><span v-if="dirty" class="unsaved">未保存</span>
      <div class="header-actions">
        <button v-if="!legacy" type="button" class="icon" title="重新加载" aria-label="重新加载" :disabled="busy" @click="center.reload"><RefreshCw :size="18" /></button>
        <button v-if="!legacy && activeModule === 'image'" type="button" class="secondary-action" :disabled="busy" @click="imageAnalysisDialog?.showModal()"><Sparkles :size="16" />从图片创建提示词</button>
      </div>
    </header>
    <nav class="module-tabs" aria-label="生成模块">
      <button v-for="module in modules" :key="module.id" type="button" :aria-pressed="!legacy && activeModule === module.id" :disabled="busy" @click="center.switchModule(module.id)">{{ module.name }}</button>
      <button type="button" class="legacy-tab" :aria-pressed="legacy" :disabled="busy" @click="center.switchModule('legacy')">旧版模板</button>
    </nav>
    <KeepAlive><LegacyPromptLibrary v-if="legacy" /></KeepAlive>
    <template v-if="!legacy">
      <nav class="category-tabs" aria-label="提示词分类">
        <button v-for="item in categories" :key="item.id" type="button" :aria-pressed="category === item.id" :disabled="busy" @click="center.switchCategory(item.id)">{{ item.name }}</button>
      </nav>
      <div v-if="error" class="message error" role="alert">{{ error }}<button v-if="conflict" type="button" :disabled="busy" @click="center.reload">重新加载最新版本</button></div>
      <p v-if="notice" class="message success" role="status">{{ notice }}</p>
      <div class="workbench" :class="{ 'has-panel': panelOpen }">
        <section class="entries" aria-label="提示词条目" :aria-busy="loading">
          <div class="toolbar">
            <label class="search"><Search :size="17" /><input v-model="search" type="search" aria-label="搜索条目" placeholder="搜索名称、场景、来源" /></label>
            <span class="count">{{ filtered.length }} 项</span>
            <button v-if="category !== 'base'" type="button" class="primary" :disabled="busy || conflict" @click="edit()"><Plus :size="17" />新增</button>
          </div>
          <p v-if="loading && !filtered.length" class="empty" role="status">加载提示词中...</p>
          <p v-else-if="!filtered.length" class="empty">{{ search ? '没有匹配的条目' : '暂无条目' }}</p>
          <div data-reorder-list>
            <article v-for="(entry, index) in filtered" :key="entry.id" class="entry" :data-reorder-id="entry.category === 'base' ? undefined : entry.id" :data-entry-id="entry.id">
              <div class="entry-main">
                <div v-if="entry.module === 'image' && (entry.category === 'layout' || entry.category === 'style')" class="style-preview">
                  <button v-if="preview(entry)" type="button" class="preview-button" :aria-label="`放大查看${entry.name}样图`" @click="openPreview(entry)">
                    <img :src="thumbnail(entry)" :alt="entry.name + ' 样图'" loading="lazy" @error="failedPreviews.push(entry.id)" />
                  </button>
                  <span v-else><Image :size="22" />{{ failedPreviews.includes(entry.id) ? '样图加载失败' : entry.category === 'style' ? stylePreview(entry).label : '暂无样图' }}</span>
                </div>
                <div class="entry-info">
                  <div class="entry-title"><ShieldCheck v-if="entry.category === 'base'" :size="18" /><h2>{{ entry.name }}</h2><span class="revision">v{{ entry.revision }}</span></div>
                  <p class="description">{{ summary(entry) }}</p>
                  <p v-if="entry.category === 'style' && preview(entry)" class="sample-caption">{{ stylePreview(entry).label }}</p>
                  <p v-else-if="entry.category === 'style' && stylePreview(entry).detail" class="sample-caption">{{ stylePreview(entry).detail }}</p>
                  <div class="entry-meta"><span>{{ entry.builtin ? '内置' : entry.owner_name || '未知来源' }}</span><span>{{ visibility[entry.visibility] }}</span><span :class="entry.enabled ? 'enabled' : 'disabled'">{{ entry.enabled ? '已启用' : '已停用' }}</span></div>
                  <time :datetime="entry.updated_at">{{ date(entry.updated_at) }}</time>
                </div>
              </div>
              <div class="entry-actions">
                <ReorderControls v-if="entry.category !== 'base'" :id="entry.id" :index="index" :total="filtered.length" :disabled="busy || conflict || !!search.trim()" @move="direction => center.step(index, direction)" @drop="target => center.move(entry.id, target)" />
                <button type="button" class="icon" :title="center.editable(entry) ? '编辑' : '查看'" :aria-label="`${center.editable(entry) ? '编辑' : '查看'} ${entry.name}`" :disabled="busy" @click="edit(entry)"><Pencil v-if="center.editable(entry)" :size="17" /><Eye v-else :size="17" /></button>
                <button v-if="entry.category !== 'base'" type="button" class="icon" title="复制" :aria-label="`复制 ${entry.name}`" :disabled="busy || conflict" @click="center.copy(entry)"><Copy :size="17" /></button>
                <template v-if="center.editable(entry)">
                  <button v-if="entry.category !== 'base'" type="button" class="icon" title="配置用户" :aria-label="`配置用户 ${entry.name}`" :disabled="busy || conflict" @click="edit(entry)"><Users :size="17" /></button>
                  <button type="button" class="icon" title="版本记录" :aria-label="`版本记录 ${entry.name}`" :disabled="busy" @click="center.showHistory(entry)"><History :size="17" /></button>
                  <label v-if="entry.category !== 'base'" class="toggle"><input type="checkbox" role="switch" :checked="entry.enabled" :aria-label="`启用 ${entry.name}`" :disabled="busy || conflict" @change="center.toggle(entry)" />启用</label>
                </template>
              </div>
            </article>
          </div>
        </section>
        <PromptEntryEditor v-if="draft" :draft="draft" :readonly="readonly" :admin="auth.isAdmin" :busy="busy || conflict" :users="users" :users-loading="usersLoading" :users-error="usersError" @change="draft = $event" @save="center.save" @close="center.discard" @users="center.loadUsers" />
        <PromptVersionHistory v-else-if="history" :entry="history" :versions="versions" :busy="busy || conflict" :loading="historyLoading" @close="center.discard" @restore="version => history && center.restore(history, version)" />
      </div>
    </template>
    <dialog ref="imageAnalysisDialog" class="image-analysis-dialog">
      <ImageAnalysisPanel
        context="prompt-center"
        :models="textModels"
        :model="analysisModel"
        @update:model="analysisModel = $event"
        @close="imageAnalysisDialog?.close()"
        @saved="center.reload(); imageAnalysisDialog?.close()"
      />
    </dialog>
    <dialog ref="previewDialog" class="preview-dialog" aria-label="样图预览">
      <header><h2>{{ previewTitle }}</h2><button type="button" class="icon" aria-label="关闭样图预览" title="关闭" @click="previewDialog?.close()"><X :size="19" /></button></header>
      <p class="sample-caption">{{ previewCaption }}</p>
      <img v-if="previewImage" :src="previewImage" :alt="previewTitle" />
    </dialog>
  </main>
</template>

<style scoped>
.prompt-center { color:#252c32; }
.center-header { display:flex; align-items:center; gap:12px; margin-bottom:20px; } h1 { font-size:24px; line-height:1.4; overflow-wrap:anywhere; } .header-actions { margin-left:auto; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.image-analysis-dialog { width:min(900px,calc(100% - 24px)); max-height:calc(100dvh - 32px); overflow:auto; padding:0; border:0; background:transparent; } .image-analysis-dialog::backdrop { background:#151d3266; }
.preview-dialog { width:min(860px,calc(100% - 24px)); max-width:none; max-height:calc(100dvh - 32px); padding:16px; border:1px solid #cfd6dc; border-radius:8px; background:#fff; } .preview-dialog::backdrop { background:#151d3266; }
.preview-dialog header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; } .preview-dialog header h2 { margin:0; font-size:18px; }
.preview-dialog>img { display:block; width:100%; max-height:calc(100dvh - 120px); object-fit:contain; background:#f4f6f7; }
button { display:inline-flex; align-items:center; justify-content:center; gap:6px; border:1px solid #bdc5cc; border-radius:4px; background:white; min-height:36px; padding:6px 12px; cursor:pointer; }
button:hover:not(:disabled) { background:#f0f4f3; } button:disabled { opacity:.5; cursor:default; } button.primary { color:white; background:#176b55; border-color:#176b55; }
button.icon { width:36px; flex-shrink:0; padding:0; }
.module-tabs { display:flex; flex-wrap:wrap; gap:4px; border-bottom:1px solid #ccd3d8; margin-bottom:16px; } .module-tabs button { border:0; border-bottom:3px solid transparent; border-radius:0; background:transparent; padding:10px 16px; }
.module-tabs button[aria-pressed=true] { border-bottom-color:#176b55; color:#125441; font-weight:600; } .legacy-tab { margin-left:auto; }
.category-tabs { display:flex; flex-wrap:wrap; gap:4px; margin-bottom:20px; } .category-tabs button { border:0; background:transparent; } .category-tabs button[aria-pressed=true] { background:#e5efe9; color:#125441; font-weight:600; }
.workbench { display:grid; grid-template-columns:minmax(0,1fr); gap:24px; align-items:start; } .workbench.has-panel { grid-template-columns:minmax(0,1fr) minmax(340px,.9fr); } .entries { min-width:0; }
.toolbar { display:flex; align-items:center; gap:10px; margin-bottom:12px; flex-wrap:wrap; } .search { display:flex; align-items:center; gap:8px; border:1px solid #bdc5cc; border-radius:4px; padding:0 10px; flex:1; min-width:140px; background:white; }
.search input { border:0; outline-offset:0; background:transparent; width:100%; min-width:0; padding:8px 0; font-size:14px; } .count { font-size:13px; color:#59636b; white-space:nowrap; }
.entry { border-top:1px solid #dce0e3; padding:16px 0; } .entry:last-child { border-bottom:1px solid #dce0e3; } .entry-main { display:flex; gap:12px; } .entry-info { min-width:0; flex:1; } .entry-title { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
h2 { font-size:16px; overflow-wrap:anywhere; line-height:1.5; } .revision { color:#59636b; font-size:12px; } .description { font-size:14px; color:#59636b; overflow-wrap:anywhere; margin:4px 0; }
.entry-meta { display:flex; gap:12px; flex-wrap:wrap; font-size:12px; } .enabled { color:#176b55; } .disabled { color:#8e493a; } time { color:#59636b; font-size:12px; } .entry-actions { display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-top:12px; }
.toggle { display:flex; align-items:center; gap:6px; font-size:13px; min-height:36px; margin-left:auto; } .empty { padding:40px 0; text-align:center; color:#59636b; }
.message { margin-bottom:16px; padding:12px; border-left:3px solid; overflow-wrap:anywhere; } .message button { margin-left:12px; } .error { background:#fff0ef; border-color:#b33930; color:#86231c; } .success { background:#edf7f0; border-color:#176b55; } .unsaved { color:#8e493a; font-size:13px; }
.style-preview { flex-shrink:0; width:128px; height:168px; background:#eef1f3; overflow:hidden; border-radius:4px; } .preview-button { display:block; width:100%; height:100%; padding:0; border:0; background:transparent; cursor:zoom-in; } .preview-button img { width:100%; height:100%; object-fit:contain; } .style-preview span { display:flex; height:100%; flex-direction:column; align-items:center; justify-content:center; gap:4px; font-size:11px; color:#59636b; }
.sample-caption { font-size:12px; line-height:1.5; color:#59636b; margin:8px 0; overflow-wrap:anywhere; }
@media(max-width:1000px) { .workbench.has-panel { grid-template-columns:minmax(0,1fr); } .has-panel > .entries { order:2; } }
@media(max-width:700px) { button, button.icon, .toggle { min-height:44px; } button.icon { width:44px; } .module-tabs button { padding:8px 10px; } .legacy-tab { margin-left:0; } .search input { font-size:16px; } h1 { font-size:22px; } .entry-actions :deep(.reorder-controls) { margin-right:auto; } }
</style>
