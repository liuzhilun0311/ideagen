<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { ArrowLeft, Check, Eye, Save, ListTree, SlidersHorizontal, PencilLine, FileText, Image, Download } from 'lucide-vue-next'
import PageList from '../components/workspace/PageList.vue'
import PageEditor from '../components/workspace/PageEditor.vue'
import GenerationPanel from '../components/workspace/GenerationPanel.vue'
import ImageViewer from '../components/common/ImageViewer.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import { useStudio } from '../composables/useStudio'
import { normalizeApiError } from '../utils/errors'

defineOptions({ name: 'WorkspaceView' })
const router = useRouter()
const studio = useStudio()
const { store, error, phase, busy, cancelling, editingLocked } = studio
const { saving, dirty } = studio.saver
const selected = ref(0)
const mobilePanel = ref<'structure' | 'editor' | 'tools'>('editor')
const editorTab = ref<'page' | 'copy'>('page')
const current = computed(() => store.outline.pages[selected.value])
const currentImage = computed(() => store.images.find(image => image.index === current.value?.index))
const structureLocked = computed(() => busy.value || store.images.length > 0)
const viewer = ref('')
const optionState = studio.options
const { textModels, imageModels, prompts } = optionState
const titles = computed({
  get: () => store.content.titles.join('\n'),
  set: value => { store.content.titles = value.split('\n'); store.content.status = 'done' },
})
const tags = computed({
  get: () => store.content.tags.join(' '),
  set: value => { store.content.tags = value.split(/\s+/).map(tag => tag.replace(/^#/, '')).filter(Boolean); store.content.status = 'done' },
})

watch(() => store.outline.pages.length, length => {
  selected.value = Math.max(0, Math.min(selected.value, length - 1))
})

function selectPage(index: number) {
  selected.value = index
  editorTab.value = 'page'
  mobilePanel.value = 'editor'
}
function movePage(from: number, to: number) {
  if (structureLocked.value) return
  store.movePage(from, to)
  selected.value = to
}
function deletePage(index: number) {
  if (structureLocked.value || store.outline.pages.length <= 1) return
  if (window.confirm('确定删除这一页？')) store.deletePage(index)
}
function addPage() {
  if (structureLocked.value) return
  store.addPage('content')
  selectPage(store.outline.pages.length - 1)
}
function openOriginal(src: string) {
  viewer.value = src
}
async function preview() {
  if (busy.value || !store.images.some(image => image.status === 'done')) return
  if (await studio.save()) await router.push('/result')
}
function exportOutline() {
  const blob = new Blob([JSON.stringify(store.outline, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'ideagen-outline.json'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (busy.value || dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
onBeforeRouteLeave(() => {
  if (busy.value) {
    error.value = normalizeApiError('当前任务尚未结束，请先取消或等待完成', '创作进行中')
    return false
  }
  return !dirty.value || window.confirm('尚有未保存到服务器的修改，确定离开？')
})
onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload)
  if (!store.outline.pages.length) {
    await router.replace('/')
    return
  }
  // Persisted running flags do not imply a live request after a reload.
  if (store.progress.status === 'generating') store.stopGeneration('上次连接已中断')
  if (store.content.status === 'generating') store.setContentError('上次文案生成已中断')
  if (store.outlineStatus === 'generating') store.setOutlineStatus('idle')
  await optionState.load()
  if (optionState.error.value) error.value = optionState.error.value
})
onUnmounted(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<template>
  <div class="studio">
    <header class="studio-header">
      <div class="studio-heading">
        <button class="icon-button back-button" title="返回作品" aria-label="返回作品"
          @click="router.push(store.entrySource === 'history' ? '/history' : '/')"><ArrowLeft :size="19" /></button>
        <div><span class="studio-kicker">创作工作台</span><h1>{{ store.topic || '未命名作品' }}</h1></div>
      </div>
      <div class="studio-controls">
        <span class="save-state" role="status"><Check v-if="!dirty && !saving" :size="14" />{{ saving ? '正在保存' : dirty ? '有未保存的修改' : '已保存' }}</span>
        <button class="icon-button" title="导出大纲" aria-label="导出大纲" :disabled="!store.outline.pages.length" @click="exportOutline"><Download :size="17" /></button>
        <button class="btn btn-secondary" :disabled="busy" @click="studio.save"><Save :size="16" /><span>保存</span></button>
        <button class="btn btn-primary" :disabled="busy || !store.images.some(image => image.status === 'done')" @click="preview"><Eye :size="16" /><span>预览作品</span></button>
      </div>
    </header>
    <ErrorCard v-if="error" :error="error" dismissible @dismiss="error = null" />
    <div class="studio-grid">
      <PageList :pages="store.outline.pages" :images="store.images" :selected="selected" :locked="structureLocked"
        :class="{ 'mobile-hidden': mobilePanel !== 'structure' }"
        @select="selectPage" @move="movePage" @remove="deletePage" @add="addPage" />
      <section class="studio-center" :class="{ 'mobile-hidden': mobilePanel !== 'editor' }">
        <div class="editor-tabs" role="tablist" aria-label="编辑内容">
          <button role="tab" :aria-selected="editorTab === 'page'" :class="{ active: editorTab === 'page' }"
            @click="editorTab = 'page'"><Image :size="16" />页面图文</button>
          <button role="tab" :aria-selected="editorTab === 'copy'" :class="{ active: editorTab === 'copy' }"
            @click="editorTab = 'copy'"><FileText :size="16" />发布文案</button>
        </div>
        <PageEditor v-if="editorTab === 'page'" :page="current" :image="currentImage" :locked="editingLocked"
          :can-retry="!!store.taskId && !busy && !!currentImage && ['done', 'error'].includes(currentImage.status)"
          @update="current && store.updatePage(current.index, $event)"
          @retry="current && studio.retryPage(current.index)" @preview="openOriginal" />
        <section v-else class="copy-editor" aria-label="整套发布文案">
          <h2>发布文案</h2>
          <p v-if="store.content.status === 'generating'" role="status">正在生成文案</p>
          <p v-if="store.content.error" class="copy-error" role="alert">{{ store.content.error }}</p>
          <label for="copy-titles">标题备选</label>
          <textarea id="copy-titles" v-model="titles" :disabled="editingLocked" rows="3" placeholder="作品标题"></textarea>
          <label for="copy-body">正文</label>
          <textarea id="copy-body" v-model="store.content.copywriting" :disabled="editingLocked" rows="12"
            placeholder="发布正文" @input="store.content.status = 'done'"></textarea>
          <label for="copy-tags">标签</label>
          <input id="copy-tags" v-model="tags" :disabled="editingLocked" class="field" placeholder="城市漫步 周末生活" />
        </section>
      </section>
      <GenerationPanel :text-models="textModels" :image-models="imageModels" :prompts="prompts"
        :busy="busy || optionState.loading.value" :phase="phase" :cancelling="cancelling"
        :class="{ 'mobile-hidden': mobilePanel !== 'tools' }" @run="studio.run" @cancel="studio.cancel" />
    </div>
    <nav class="studio-mobile-nav" aria-label="工作台分区">
      <button :aria-pressed="mobilePanel === 'structure'" @click="mobilePanel = 'structure'"><ListTree :size="19" />结构</button>
      <button :aria-pressed="mobilePanel === 'editor'" @click="mobilePanel = 'editor'"><PencilLine :size="19" />编辑</button>
      <button :aria-pressed="mobilePanel === 'tools'" @click="mobilePanel = 'tools'"><SlidersHorizontal :size="19" />生成</button>
    </nav>
    <ImageViewer :visible="!!viewer" :src="viewer" :alt="`第 ${selected + 1} 页`" @close="viewer = ''" />
  </div>
</template>

<style scoped>
.studio { max-width:1440px; width:100%; margin:0 auto; }
.studio-header { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-bottom:24px; }
.studio-heading { display:flex; gap:12px; align-items:center; min-width:0; }
.studio-heading>div { min-width:0; }
.studio-kicker { font-size:12px; color:var(--text-sub); }
h1 { font-size:21px; font-weight:650; line-height:1.5; overflow-wrap:anywhere; margin-top:3px; }
.studio-controls { display:flex; align-items:center; gap:8px; flex-shrink:0; }
.studio-controls .btn { font-size:13px; padding:0 14px; }
.save-state { display:flex; align-items:center; gap:5px; font-size:12px; color:var(--text-sub); margin-right:6px; white-space:nowrap; }
.studio-grid { display:grid; grid-template-columns:208px minmax(0,1fr) 280px; min-height:760px; border:1px solid var(--border-color); background:#fff; }
.studio-center { min-width:0; }
.editor-tabs { display:flex; gap:24px; padding:0 22px; height:60px; border-bottom:1px solid var(--border-color); }
.editor-tabs button { background:none; border:0; border-bottom:2px solid transparent; color:var(--text-sub); display:flex; align-items:center; gap:8px; font-size:13px; }
.editor-tabs button.active { color:var(--primary); border-bottom-color:var(--primary); }
.copy-editor { padding:26px; }
.copy-editor h2 { font-size:18px; margin-bottom:20px; }
.copy-editor label { display:block; margin:20px 0 9px; font-size:13px; }
.copy-editor textarea { width:100%; padding:12px; border:1px solid var(--border-color); border-radius:6px; font:inherit; font-size:15px; line-height:1.8; resize:vertical; }
.copy-error { color:#b33d26; font-size:14px; }
.studio-mobile-nav { display:none; }
@media(max-width:1100px) and (min-width:701px) {
  .studio-grid { grid-template-columns:180px minmax(0,1fr); }
  .page-list { grid-row:1/3; }
  .generation-panel { grid-column:2; }
  .save-state { display:none; }
}
@media(max-width:700px) {
  .studio { padding-bottom:84px; }
  .studio-header { flex-direction:column; align-items:stretch; gap:16px; margin-bottom:18px; }
  .studio-heading { gap:8px; }
  h1 { font-size:19px; }
  .studio-controls { justify-content:flex-end; flex-wrap:wrap; gap:7px; }
  .save-state { margin-right:auto; font-size:11px; }
  .studio-controls>.icon-button { display:none; }
  .studio-controls .btn { padding:0 11px; }
  .studio-grid { display:block; min-height:600px; }
  .mobile-hidden { display:none !important; }
  .studio-mobile-nav { display:flex; position:fixed; bottom:0; left:0; right:0; border-top:1px solid var(--border-color); background:#fff; padding:8px 12px calc(8px + env(safe-area-inset-bottom)); z-index:30; }
  .studio-mobile-nav button { flex:1; min-height:48px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; border:0; background:transparent; color:var(--text-sub); font-size:12px; }
  .studio-mobile-nav button[aria-pressed=true] { color:var(--primary); background:#eef3ff; border-radius:6px; }
  .copy-editor { padding:20px 16px; }
  .copy-editor textarea { font-size:16px; }
}
</style>
