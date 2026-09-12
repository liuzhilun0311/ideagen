<script setup lang="ts">
import { computed, onActivated, onDeactivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Check, Copy, Eye, Save, ListTree, SlidersHorizontal, PencilLine, FileText, Image, Download, Square, Plus, X } from 'lucide-vue-next'
import PageList from '../components/workspace/PageList.vue'
import PageEditor from '../components/workspace/PageEditor.vue'
import GenerationPanel from '../components/workspace/GenerationPanel.vue'
import ImageViewer from '../components/common/ImageViewer.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import { useStudio } from '../composables/useStudio'
import { useStudioSession } from '../stores/studioSession'
import { usePostprocessing } from '../composables/usePostprocessing'
import PostprocessingToolbar from '../components/workspace/PostprocessingToolbar.vue'
import type { ProcessingStrength, ProcessingVersion } from '../api/postprocessing'
import { contentSource } from '../utils/contentSource'
import PageStyleTrials from '../components/workspace/PageStyleTrials.vue'
import { usePageTrials } from '../composables/usePageTrials'
import type { StyleChoice } from '../features/styles/catalog'
import { withLayout } from '../features/generationOptions'

defineOptions({ name: 'WorkspaceView' })
const router = useRouter()
const route = useRoute()
const studio = useStudio()
const session = useStudioSession()
const { store, error, phase, busy, cancelling, editingLocked } = studio
const trials = usePageTrials(studio.save, value => { error.value = value })
const pageSettingsHost = ref<HTMLElement | null>(null)
const processing = usePostprocessing(computed(() => store.recordId))
const { state: processingState, pages: processingPages, error: processingError } = processing
const unavailable = computed(() => !!store.recordId && (
  [403, 404].includes(processingError.value?.status || 0)
  || [403, 404].includes(studio.saver.error.value?.status || 0)
))
const recoveryNotice = ref('')
const copySourceNotice = computed(() => {
  if (!store.content.copywriting && !store.content.titles.length && !store.content.tags.length) return ''
  const source = store.content.source
  if (!source) return '现有文案尚未与当前页面核对，请检查内容是否一致。'
  const currentSource = contentSource(store.topic, store.outline.pages)
  return source.topic !== currentSource.topic || source.outline !== currentSource.outline
    ? '页面内容已变化，建议更新发布文案。原文案和手动修改已保留。' : ''
})
function recoverDraft() {
  if (!unavailable.value || session.busy || !session.replaceDraft()) return
  const workspacePath = route.path === '/workspace/copy' ? '/workspace/copy' : '/workspace'
  store.$patch({
    recordId: null, taskId: null, images: [], lastSavedAt: null, entrySource: 'home',
    progress: { current: 0, total: 0, status: 'idle' },
    stage: 'outline',
  })
  session.workspacePath = workspacePath
  studio.saver.resetBaseline()
  error.value = null
  processingError.value = null
  session.dirty = true
  store.saveToStorage()
  recoveryNotice.value = '已转为新草稿，文字和生成设置已保留。'
}
const submittingPages = ref<number[]>([])
const savingPreferences = ref(false)
const eligibleProcessingPages = computed(() => processingPages.value.filter(page =>
  store.images.some(image => image.index === page.index && image.status === 'done' && image.url)))
const processingCurrent = computed(() => eligibleProcessingPages.value.find(page => page.index === current.value?.index))
async function processImages(indices: number[], strength: ProcessingStrength, force: boolean) {
  if (unavailable.value) return
  const record = store.recordId
  submittingPages.value = [...new Set([...submittingPages.value, ...indices])]
  try { await processing.process(indices, strength, force) }
  finally {
    if (record === store.recordId) submittingPages.value = submittingPages.value.filter(index => !indices.includes(index))
  }
}
async function processCurrent(strength: ProcessingStrength, force: boolean) {
  if (current.value) await processImages([current.value.index], strength, force)
}
async function adoptCurrent(version: ProcessingVersion, sourceRevision: string) {
  if (unavailable.value) return
  if (current.value) await processing.adopt(current.value.index, version, sourceRevision)
}
async function saveProcessingPreferences(automatic: boolean, strength: ProcessingStrength) {
  if (savingPreferences.value || unavailable.value) return
  const revision = session.revision
  savingPreferences.value = true
  try {
    if (!store.recordId && !await studio.save()) return
    if (revision !== session.revision) return
    await processing.preferences(automatic, strength)
  } finally {
    if (revision === session.revision) savingPreferences.value = false
  }
}
watch(() => store.recordId, () => { submittingPages.value = [] })
watch(() => session.revision, () => { savingPreferences.value = false })
watch(() => store.images.map(image => `${image.index}:${image.status}:${image.url}`).join('|'), () => { void processing.refresh() })
const { saving, dirty } = studio.saver
const cancelLabel = computed(() => `${cancelling.value ? '正在取消' : '取消'}${phase.value === 'images' ? '图片' : phase.value === 'content' ? '文案' : '大纲'}生成`)
const selected = ref(0)
const mobilePanel = ref<'structure' | 'editor' | 'tools'>('editor')
const settingsDialog = ref<HTMLDialogElement | null>(null)
function openTools() {
  mobilePanel.value = 'tools'
  settingsDialog.value?.showModal?.()
}
async function runPageTrial(style: StyleChoice) {
  if (!current.value || !canGenerateImages.value) return
  settingsDialog.value?.close?.()
  await trials.trial(current.value.index, style)
}
const mode = computed(() => route.path === '/workspace/copy' ? 'copy' : 'images')
const current = computed(() => store.outline.pages[selected.value])
const currentImage = computed(() => unavailable.value ? undefined : store.images.find(image => image.index === current.value?.index))
const structureLocked = computed(() => busy.value || trials.busy.value || store.images.length > 0 || trials.candidates.value.length > 0)
const viewer = ref('')
const viewerVersion = ref<ProcessingVersion>('original')
const viewerLabel = ref('原图')
const optionState = studio.options
const { textModels, imageModels, prompts } = optionState
const controlsBusy = computed(() => session.busy || unavailable.value || optionState.loading.value || !!optionState.error.value)
const canGenerateCopy = computed(() => !controlsBusy.value && textModels.value.some(model => model.name === store.contentModelName))
const canGenerateImages = computed(() => !controlsBusy.value && imageModels.value.some(model => model.name === store.imageModelName))
async function generateCopy() {
  if (!canGenerateCopy.value) return
  mobilePanel.value = 'editor'
  await studio.run('content')
}
async function newCreation() {
  if (session.busy) return
  if ((dirty.value || store.outline.pages.length) && !window.confirm('开始新创作会替换当前工作台，是否继续？')) return
  if (!session.replaceDraft()) return
  store.reset()
  await router.push('/')
}
const titles = computed({
  get: () => store.content.titles.join('\n'),
  set: value => { store.content.titles = value.split('\n'); store.content.status = 'done' },
})
const tags = computed({
  get: () => store.content.tags.join(' '),
  set: value => { store.content.tags = value.split(/\s+/).map(tag => tag.replace(/^#/, '')).filter(Boolean); store.content.status = 'done' },
})
const publicationText = computed(() => [
  titles.value.trim(),
  store.content.copywriting.trim(),
  store.content.tags.map(tag => `#${tag}`).join(' '),
].filter(Boolean).join('\n\n'))
const copying = ref(false)
const copyMessage = ref('')
const copyFailed = ref(false)
async function copyPublication(text: string) {
  if (!text || copying.value) return
  copying.value = true
  copyMessage.value = ''
  copyFailed.value = false
  try {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const previousFocus = document.activeElement
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      try {
        textarea.select()
        if (!document.execCommand('copy')) throw new Error('复制失败')
      } finally {
        textarea.remove()
        if (previousFocus instanceof HTMLElement) previousFocus.focus()
      }
    }
    copyMessage.value = '已复制'
  } catch {
    copyFailed.value = true
    copyMessage.value = '复制失败，剪贴板不可用或未获授权。'
  } finally {
    copying.value = false
  }
}
watch(mode, () => {
  settingsDialog.value?.close?.()
  mobilePanel.value = 'editor'
  viewer.value = ''
  copyMessage.value = ''
})

watch(() => store.outline.pages.length, length => {
  selected.value = Math.max(0, Math.min(selected.value, length - 1))
})
watch(() => session.revision, () => {
  selected.value = 0
  mobilePanel.value = 'editor'
  viewer.value = ''
  copyMessage.value = ''
  recoveryNotice.value = ''
}, { flush: 'sync' })

function selectPage(index: number) {
  selected.value = index
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
function openViewedImage(src: string, version: ProcessingVersion) {
  viewer.value = src
  viewerVersion.value = version
  viewerLabel.value = version === 'processed' ? '处理图' : '原图'
}
function openCandidateImage(src: string) {
  viewer.value = src
  viewerVersion.value = 'original'
  viewerLabel.value = '候选图'
}
function updateCurrentLayout(layout: string) {
  if (current.value) store.updatePage(current.value.index, withLayout(current.value.content, layout))
}
function goBackFromWorkspace() {
  // Exit editing, discard the loaded work, and return to a genuinely new creation form.
  if (session.busy) return
  if (!session.replaceDraft()) return
  store.setEntrySource('home')
  store.prepareNewOutline()
  void router.push('/')
}
async function preview() {
  if (busy.value || unavailable.value || !store.images.some(image => image.status === 'done')) return
  const originPath = route.path
  const revision = session.revision
  if (await studio.save() && visible && route.path === originPath
    && ['/workspace', '/workspace/copy'].includes(originPath) && revision === session.revision) {
    await router.push('/result')
  }
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
let visible = false
async function refreshOptions() {
  if (session.busy || optionState.loading.value) return
  await optionState.load()
  if (optionState.error.value) error.value = optionState.error.value
}
onMounted(() => {
  // Persisted running flags do not imply a live request after a reload.
  if (store.progress.status === 'generating') store.stopGeneration('上次连接已中断')
  if (store.content.status === 'generating') store.setContentError('上次文案生成已中断')
  if (store.outlineStatus === 'generating') store.setOutlineStatus('idle')
})
onActivated(() => {
  visible = true
  void refreshOptions()
})
onDeactivated(() => { visible = false; viewer.value = ''; settingsDialog.value?.close?.() })
watch([() => session.busy, optionState.loading, optionState.refreshNeeded], ([isBusy, isLoading, needsRefresh], previous) => {
  if (!isBusy && !isLoading && visible && (needsRefresh || previous[0])) void refreshOptions()
})
</script>

<template>
  <div class="studio">
    <header class="studio-header">
      <div class="studio-heading">
        <button class="icon-button back-button" title="返回作品" aria-label="返回作品"
          @click="goBackFromWorkspace"><ArrowLeft :size="19" /></button>
        <div><span class="studio-kicker">创作工作台</span><h1>{{ store.topic || '未命名作品' }}</h1></div>
      </div>
      <div class="studio-controls">
        <span class="save-state" role="status"><Check v-if="!dirty && !saving" :size="14" />{{ saving ? '正在保存' : dirty ? '有未保存的修改' : '已保存' }}</span>
        <button v-if="mode === 'images'" class="icon-button export-button" title="导出大纲" aria-label="导出大纲" :disabled="!store.outline.pages.length" @click="exportOutline"><Download :size="17" /></button>
        <button class="icon-button" title="新建创作" aria-label="新建创作" :disabled="session.busy" @click="newCreation"><Plus :size="18" /></button>
        <button class="btn btn-secondary" :disabled="busy || unavailable" @click="studio.save"><Save :size="16" /><span>保存</span></button>
        <button class="btn btn-primary" :disabled="busy || unavailable || !store.images.some(image => image.status === 'done')" @click="preview"><Eye :size="16" /><span>预览作品</span></button>
      </div>
    </header>
    <nav class="workspace-navigation" aria-label="创作页面">
      <RouterLink to="/workspace" :class="{ active: mode === 'images' }"><Image :size="18" />图片制作</RouterLink>
      <RouterLink to="/workspace/copy" :class="{ active: mode === 'copy' }"><FileText :size="18" />发布文案</RouterLink>
    </nav>
    <section v-if="unavailable" class="draft-recovery" role="status">
      <div><strong>原作品已删除或无法访问</strong><p>当前文字草稿仍保留，旧图片已不可用。</p></div>
      <button class="btn btn-primary" :disabled="session.busy" @click="recoverDraft"><Plus :size="18" />转为新作品继续</button>
    </section>
    <p v-if="recoveryNotice" class="recovery-notice" role="status">{{ recoveryNotice }}</p>
    <p v-if="copySourceNotice" class="recovery-notice" role="status">{{ copySourceNotice }}</p>
    <section class="generation-toolbar" :class="{ 'copy-toolbar': mode === 'copy' }" aria-label="整套生成工具栏">
      <div class="generation-controls">
        <div class="toolbar-section-heading"><strong>生成设置</strong><span>当前作品</span></div>
        <GenerationPanel class="suite-generation-panel" :mode="mode" :text-models="textModels" :image-models="imageModels" :prompts="prompts"
          :busy="controlsBusy" :phase="phase" @run="studio.run" />
      </div>
      <section class="creation-actions" aria-label="创作操作">
        <div class="toolbar-section-heading"><strong>生成操作</strong><span>按需执行</span></div>
        <button v-if="mode === 'copy'" class="btn btn-primary copy-action" :disabled="!canGenerateCopy" @click="generateCopy">
          <FileText :size="20" />{{ phase === 'content' ? '正在生成文案' : store.content.copywriting.trim() ? '重新生成文案' : '生成文案' }}
        </button>
        <button v-else class="btn btn-primary image-action" title="只生成尚未生成的页面" :disabled="!canGenerateImages || !trials.missing.value.length" @click="trials.batch()">
          <Image :size="18" />生成剩余 {{ trials.missing.value.length }} 张
        </button>
        <button v-if="mode === 'images' && store.outline.pages.length" class="btn btn-secondary" title="重新生成当前作品的全部页面" :disabled="!canGenerateImages" @click="trials.batch(true)">
          <Image :size="18" />重新生成 {{ store.outline.pages.length }} 张
        </button>
        <button v-if="trials.busy.value" class="btn btn-secondary" :disabled="trials.stopping.value" @click="trials.stop"><Square :size="16" />{{ trials.stopping.value ? '本张完成后停止' : '停止后续生成' }}</button>
        <button v-if="phase && phase !== 'retry'" class="btn btn-secondary cancel-action" :disabled="cancelling" @click="studio.cancel">
          <Square :size="16" />{{ cancelLabel }}
        </button>
      </section>
      <section v-if="mode === 'images' && !unavailable" class="processing-settings suite-processing-settings" aria-label="整套图片后处理">
        <div class="toolbar-section-heading"><strong>批量处理</strong><span>生成后优化</span></div>
        <PostprocessingToolbar :key="store.recordId || 'unsaved'"
          :pages="eligibleProcessingPages" :preferences="processingState?.preferences"
          :submitting="!!submittingPages.length" :saving-preferences="savingPreferences"
          @process="processImages" @preferences="saveProcessingPreferences" />
      </section>
    </section>
    <p v-if="mode === 'images' && trials.notice.value" class="recovery-notice" role="status">{{ trials.notice.value }}</p>
    <ErrorCard v-if="processingError && !unavailable" :error="processingError" dismissible @dismiss="processingError = null" />
    <ErrorCard v-if="error && !unavailable" :error="error" dismissible @dismiss="error = null" />
    <div class="studio-grid" :class="{ 'copy-grid': mode === 'copy' }">
      <PageList v-if="mode === 'images'" :pages="store.outline.pages" :images="unavailable ? [] : store.images" :selected="selected" :locked="structureLocked"
        :candidates="trials.candidates.value"
        :processing-pages="eligibleProcessingPages"
        :class="{ 'mobile-hidden': mobilePanel !== 'structure' }"
        @select="selectPage" @move="movePage" @remove="deletePage" @add="addPage" />
      <section class="studio-center" :class="{ 'mobile-hidden': mobilePanel === 'structure' }">
        <PageStyleTrials v-if="mode === 'images' && current && !unavailable" :key="store.recordId || 'unsaved'" :task-id="store.taskId"
          :index="current.index" :default-style="store.imageStyle" :candidates="trials.candidates.value" :disabled="!canGenerateImages"
          :controls-host="pageSettingsHost" :has-image="!!currentImage?.url" :page-content="current.content"
          @trial="runPageTrial" @adopt="trials.adopt" @apply="trials.applyStyle" @refresh="trials.refresh"
          @layout-change="updateCurrentLayout" @preview="openCandidateImage">
        <PageEditor :page="current" :image="currentImage" :locked="editingLocked || trials.busy.value"
          :show-retry="false" :show-content="false" aria-label="当前采用图片"
          :processing-page="processingCurrent" :processing-strength="processingState?.preferences.strength"
          :processing-submitting="!!current && submittingPages.includes(current.index)"
          :processing-loading="processing.loading.value && !processingState"
          :processing-error="processingError?.detail"
          :can-retry="canGenerateImages"
          @update="current && store.updatePage(current.index, $event)"
          @process="processCurrent" @adopt="adoptCurrent"
          @retry="current && trials.trial(current.index, store.imageStyle)" @preview="openViewedImage" />
        </PageStyleTrials>
        <PageEditor v-if="mode === 'images'" :page="current" :locked="editingLocked || trials.busy.value"
          :show-canvas="unavailable" :can-retry="false"
          @update="current && store.updatePage(current.index, $event)" />
        <section v-else class="copy-editor" aria-label="整套发布文案">
          <div class="copy-heading">
            <h2>发布文案</h2>
            <button class="icon-button" title="复制全部文案" aria-label="复制全部文案" :disabled="copying || !publicationText" @click="copyPublication(publicationText)"><Copy :size="18" /></button>
          </div>
          <p v-if="store.content.status === 'generating'" role="status">正在生成文案</p>
          <p v-if="store.content.error" class="copy-error" role="alert">{{ store.content.error }}</p>
          <p v-if="copyMessage" :class="{ 'copy-error': copyFailed }" :role="copyFailed ? 'alert' : 'status'">{{ copyMessage }}</p>
          <label for="copy-titles">标题备选</label>
          <textarea id="copy-titles" v-model="titles" :disabled="editingLocked" rows="3" placeholder="作品标题"></textarea>
          <div class="copy-field-heading">
            <label for="copy-body">正文</label>
            <button class="icon-button" title="复制正文" aria-label="复制正文" :disabled="copying || !store.content.copywriting" @click="copyPublication(store.content.copywriting)"><Copy :size="17" /></button>
          </div>
          <textarea id="copy-body" v-model="store.content.copywriting" :disabled="editingLocked" rows="12"
            placeholder="发布正文" @input="store.content.status = 'done'"></textarea>
          <label for="copy-tags">标签</label>
          <input id="copy-tags" v-model="tags" :disabled="editingLocked" class="field" placeholder="城市漫步 周末生活" />
        </section>
      </section>
      <aside v-if="mode === 'images'" ref="pageSettingsHost" class="page-settings-column" aria-label="当前页设置"></aside>
    </div>
    <dialog ref="settingsDialog" class="mobile-settings-dialog" @close="mobilePanel = 'editor'" @click="($event.target === settingsDialog) && settingsDialog?.close()">
      <header><strong>生成设置</strong><button class="icon-button" aria-label="关闭生成设置" @click="settingsDialog?.close()"><X :size="20" /></button></header>
      <p class="mobile-settings-note">请在桌面布局右侧查看当前页设置。</p>
    </dialog>
    <nav class="studio-mobile-nav" aria-label="工作台分区">
      <button v-if="mode === 'images'" :aria-pressed="mobilePanel === 'structure'" @click="mobilePanel = 'structure'"><ListTree :size="19" />结构</button>
      <button :aria-pressed="mobilePanel === 'editor'" @click="mobilePanel = 'editor'"><PencilLine :size="19" />编辑</button>
      <button :aria-pressed="mobilePanel === 'tools'" @click="openTools"><SlidersHorizontal :size="19" />试图与设置</button>
    </nav>
    <ImageViewer :visible="!!viewer" :src="viewer" :alt="`第 ${selected + 1} 页${viewerLabel}`" @close="viewer = ''" />
  </div>
</template>

<style scoped>
.studio { max-width:1440px; width:100%; margin:0 auto; }
.processing-settings { margin-bottom:16px; border-bottom:1px solid var(--border-color); }
.generation-toolbar { display:grid; grid-template-columns:118px repeat(4,64px) 116px 86px 100px 108px 112px 112px 112px 112px; align-items:start; gap:7px; margin-bottom:12px; padding:9px 10px 8px; border:1px solid #dbe3ef; border-radius:8px; background:#f8fafc; box-shadow:0 1px 2px #15233d0a; }
.generation-toolbar.copy-toolbar { grid-template-columns:1fr; }
.suite-generation-panel { border:0; min-width:0; }
.suite-generation-panel { display:contents; }
.suite-generation-panel :deep(.generation-panel) { display:block; border-left:0; padding:0; }
.suite-generation-panel :deep(.generation-panel>h2) { display:none; }
.suite-generation-panel :deep(.image-settings-section) { display:contents; }
.suite-generation-panel :deep(.section-title) { display:none; }
.suite-generation-panel :deep(.style-picker) { grid-column:1; grid-row:1; min-width:0; padding:0; border:0; }
.suite-generation-panel :deep(.style-select>.scene) { display:none; }
.suite-generation-panel :deep(.style-select label) { font-size:11px; line-height:18px; gap:5px; }
.suite-generation-panel :deep(.style-picker>label) { display:grid; min-width:0; align-self:start; color:#52627a; font-weight:600; }
.suite-generation-panel :deep(.style-picker>details), .suite-generation-panel :deep(.style-picker>p) { display:none; }
.suite-generation-panel :deep(.style-picker>label) { display:grid; gap:5px; }
.suite-generation-panel :deep(.image-parameters), .suite-generation-panel :deep(.parameter-grid) { display:contents; }
.suite-generation-panel :deep(.parameter-grid label) { grid-row:1; margin:0; min-width:0; width:auto; font-size:11px; line-height:18px; color:#52627a; font-weight:600; }
.suite-generation-panel :deep(.parameter-grid label:nth-child(1)) { grid-column:2; }
.suite-generation-panel :deep(.parameter-grid label:nth-child(2)) { grid-column:3; }
.suite-generation-panel :deep(.parameter-grid label:nth-child(3)) { grid-column:4; }
.suite-generation-panel :deep(.parameter-grid label:nth-child(4)) { grid-column:5; }
.suite-generation-panel :deep(.parameter-grid select) { width:100%; margin-top:6px; }
.suite-generation-panel :deep(.reference-toggle) { display:grid; grid-column:7; grid-row:1; gap:4px; margin:0; min-width:0; font-size:11px; line-height:18px; }
.suite-generation-panel :deep(.reference-toggle select) { width:100%; min-height:44px; }
.suite-generation-panel :deep(.generation-group) { grid-column:6; grid-row:1; display:grid; gap:6px; margin:0; padding:0; border:0; }
.suite-generation-panel :deep(.generation-group label) { display:block; margin:0; font-size:11px; line-height:18px; color:#52627a; font-weight:600; }
.suite-generation-panel :deep(select) { height:44px; min-height:44px; width:100%; }
.suite-generation-panel :deep(.generation-group .field) { width:100%; min-height:44px; }
.generation-toolbar :deep(select) { border-color:#cbd5e1; border-radius:6px; background:#fff; color:#17233b; transition:border-color .2s, box-shadow .2s; }
.generation-toolbar :deep(select:focus-visible) { border-color:#3867e8; box-shadow:0 0 0 3px #3867e81f; outline:0; }
.suite-generation-panel :deep(.outline-adjustments), .suite-generation-panel :deep(.advanced-settings), .suite-generation-panel :deep(.page-tools-divider) { display:none; }
.generation-toolbar .creation-actions { display:contents; }
.generation-toolbar .creation-actions .btn { width:100%; min-width:0; min-height:40px; padding:0 7px; border-radius:6px; font-size:11px; line-height:1.25; white-space:normal; overflow:hidden; text-overflow:ellipsis; justify-content:center; }
.generation-toolbar .creation-actions .image-action { box-shadow:0 2px 4px #2f5fe626; }
.generation-toolbar .creation-actions .btn:disabled,
.suite-processing-settings :deep(.batch-controls > .btn:disabled) { opacity:.58; box-shadow:none; }
.generation-toolbar .creation-actions .image-action { grid-column:10; grid-row:1; }
.generation-toolbar .creation-actions .image-action + .btn { grid-column:11; grid-row:1; }
.generation-toolbar .creation-actions .cancel-action,
.generation-toolbar .creation-actions .btn:has(+ .cancel-action) { grid-row:2; }
.suite-processing-settings { display:contents; }
.suite-processing-settings :deep(.processing-toolbar) { display:contents; }
.suite-processing-settings :deep(.batch-controls) { display:contents; }
.suite-processing-settings :deep(.batch-controls > label) { grid-column:8; grid-row:1; display:grid; gap:4px; min-width:0; font-size:11px; color:#52627a; font-weight:600; }
.suite-processing-settings :deep(.automatic-controls) { display:contents; }
.suite-processing-settings :deep(.automatic-toggle) { grid-column:9; grid-row:1; display:grid; gap:4px; min-width:0; font-size:11px; color:#52627a; font-weight:600; }
.suite-processing-settings :deep(.batch-controls > .btn) { grid-row:1; min-height:40px; padding:0 7px; border-radius:6px; font-size:11px; line-height:1.25; white-space:normal; }
.suite-processing-settings :deep(.batch-controls > .btn:nth-of-type(1)) { grid-column:12; }
.suite-processing-settings :deep(.batch-controls > .btn:nth-of-type(2)) { grid-column:13; }
.suite-processing-settings :deep(.processing-toolbar .btn) { min-height:30px; padding:4px 8px; font-size:11px; }
.suite-processing-settings :deep(.processing-toolbar select) { min-height:30px; padding:4px 20px 4px 6px; font-size:11px; }
.generation-toolbar > .suite-processing-settings { border-left:1px solid #dbe3ef; padding-left:8px; }
.generation-toolbar > .creation-actions { border-left:1px solid #dbe3ef; padding-left:8px; }
.page-settings-column { min-width:0; border-left:1px solid var(--border-color); background:#fff; }
.page-settings-column:empty { display:none; }
.processing-settings>summary { min-height:44px; padding:10px 0; cursor:pointer; font-size:13px; }
.processing-settings>summary span { color:var(--text-sub); margin-left:12px; font-size:12px; }
.mobile-settings-dialog { width:min(390px, calc(100% - 24px)); max-height:100dvh; height:100dvh; margin:0 0 0 auto; border:0; border-left:1px solid var(--border-color); padding:0; color:var(--text-main); background:white; overflow:auto; }
.mobile-settings-dialog::backdrop { background:#151d3260; }
.mobile-settings-dialog>header { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border-bottom:1px solid var(--border-color); position:sticky; top:0; background:white; z-index:1; }
.mobile-settings-dialog :deep(.generation-panel>h2) { display:none; }
.draft-recovery { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; padding:16px 0; border-block:1px solid var(--border-color); margin-bottom:16px; }
.draft-recovery strong { font-size:16px; }
.draft-recovery p { margin:6px 0 0; color:var(--text-sub); font-size:14px; }
.draft-recovery .btn { min-height:44px; white-space:normal; }
.recovery-notice { color:var(--text-sub); font-size:14px; margin:12px 0; }
.creation-actions { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:20px; padding:16px 0; border-block:1px solid var(--border-color); }
.creation-actions .btn { min-height:48px; font-size:16px; padding:0 24px; }
.workspace-navigation { display:flex; gap:24px; flex-wrap:wrap; margin-bottom:12px; }
.workspace-navigation a { display:flex; align-items:center; gap:8px; min-height:44px; border-bottom:2px solid transparent; color:var(--text-sub); font-size:15px; text-decoration:none; }
.workspace-navigation a.active { border-bottom-color:var(--primary); color:var(--primary); }
.workspace-navigation a:focus-visible { outline:2px solid var(--primary); outline-offset:3px; }
.copy-field-heading { display:flex; align-items:center; justify-content:space-between; margin-top:12px; }
.copy-field-heading label { margin:0; }
.copy-heading { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:20px; }
.copy-heading h2 { margin:0; }
.studio-header { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-bottom:24px; }
.studio-heading { display:flex; gap:12px; align-items:center; min-width:0; }
.studio-heading>div { min-width:0; }
.studio-kicker { font-size:12px; color:var(--text-sub); }
h1 { font-size:21px; font-weight:650; line-height:1.5; overflow-wrap:anywhere; margin-top:3px; }
.studio-controls { display:flex; align-items:center; gap:8px; flex-shrink:0; }
.studio-controls .btn { font-size:13px; padding:0 14px; }
.save-state { display:flex; align-items:center; gap:5px; font-size:12px; color:var(--text-sub); margin-right:6px; white-space:nowrap; }
.studio-grid { display:grid; grid-template-columns:208px minmax(0,1fr) 320px; min-height:760px; border:1px solid var(--border-color); background:#fff; }
.studio-grid.copy-grid { grid-template-columns:minmax(0,1fr) 280px; }
.studio-center { min-width:0; }
.copy-editor { padding:26px; }
.copy-editor h2 { font-size:18px; margin-bottom:20px; }
.copy-editor label { display:block; margin:20px 0 9px; font-size:13px; }
.copy-editor textarea { width:100%; padding:12px; border:1px solid var(--border-color); border-radius:6px; font:inherit; font-size:15px; line-height:1.8; resize:vertical; }
.copy-error { color:#b33d26; font-size:14px; }
.studio-mobile-nav { display:none; }
@media(min-width:701px) {
  .generation-toolbar { grid-template-columns:minmax(0,1.2fr) minmax(250px,.8fr) minmax(0,1.25fr); gap:0; padding:14px 16px; }
  .generation-controls, .creation-actions, .suite-processing-settings { min-width:0; padding:0 16px; }
  .generation-controls { grid-column:1; }
  .creation-actions { grid-column:2; display:flex; align-items:flex-start; flex-wrap:wrap; align-content:flex-start; gap:8px; border-left:1px solid #dbe3ef; }
  .suite-processing-settings { grid-column:3; border-left:1px solid #dbe3ef; }
  .toolbar-section-heading { display:flex; align-items:baseline; justify-content:space-between; gap:8px; margin-bottom:10px; }
  .toolbar-section-heading strong { font-size:12px; }
  .toolbar-section-heading span { color:var(--text-sub); font-size:11px; }
  .generation-controls .suite-generation-panel { display:block; }
  .generation-controls .suite-generation-panel :deep(.generation-panel) { display:block; }
  .generation-controls .suite-generation-panel :deep(.image-settings-section) { display:grid; }
  .generation-controls .suite-generation-panel :deep(.image-parameters),
  .generation-controls .suite-generation-panel :deep(.parameter-grid) { display:block; }
  .generation-controls .suite-generation-panel :deep(.parameter-grid) { display:grid; }
  .generation-controls .suite-generation-panel :deep(.parameter-grid label) { grid-row:auto; }
  .generation-controls .suite-generation-panel :deep(.generation-group) { display:block; }
  .creation-actions .toolbar-section-heading { width:100%; }
  .creation-actions .btn { flex:1 1 100%; min-height:40px; }
  .suite-processing-settings :deep(.processing-toolbar) { display:block; }
  .suite-processing-settings :deep(.batch-controls),
  .suite-processing-settings :deep(.automatic-controls) { display:flex; }
  .suite-processing-settings :deep(.batch-controls > .btn) { flex:1 1 100%; }
}
@media(max-width:1100px) and (min-width:701px) {
  .studio-grid { grid-template-columns:150px minmax(0,1fr) 280px; }
  .studio-grid.copy-grid { grid-template-columns:minmax(0,1fr) 250px; }
  .copy-grid .generation-panel { grid-column:auto; }
  .save-state { display:none; }
}
@media(max-width:700px) {
  .generation-toolbar { display:grid; grid-template-columns:1fr; gap:10px; padding:10px; }
  .suite-generation-panel :deep(.image-settings-section) { display:contents; }
  .suite-generation-panel :deep(.style-picker) { grid-column:1; width:auto; }
  .suite-generation-panel :deep(.image-parameters) { display:contents; }
  .suite-generation-panel :deep(.parameter-grid) { display:contents; }
  .suite-generation-panel :deep(.parameter-grid label:nth-child(n)) { grid-column:auto; }
  .suite-generation-panel :deep(.parameter-grid label), .suite-generation-panel :deep(.parameter-grid select) { width:auto; }
  .suite-generation-panel :deep(.generation-group) { grid-column:1; grid-row:auto; }
  .suite-generation-panel :deep(.generation-group .field) { width:100%; }
  .suite-generation-panel :deep(.reference-toggle) { grid-column:1; grid-row:auto; }
  .suite-generation-panel :deep(.parameter-grid) { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); }
  .suite-generation-panel :deep(.parameter-grid label:nth-child(n)) { grid-column:auto; }
  .suite-generation-panel :deep(.reference-toggle) { white-space:normal; }
  .generation-toolbar .creation-actions { display:grid; grid-template-columns:1fr; }
  .generation-controls, .creation-actions, .suite-processing-settings { min-width:0; }
  .toolbar-section-heading { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:8px; }
  .toolbar-section-heading strong { font-size:12px; }
  .toolbar-section-heading span { color:var(--text-sub); font-size:11px; }
  .creation-actions { display:grid; grid-template-columns:minmax(0,1fr); gap:10px; padding:12px 0; margin-bottom:8px; }
  .creation-actions .btn { width:100%; padding:0 8px; font-size:15px; }
  .cancel-action { grid-column:1/-1; }
  .studio { padding-bottom:84px; }
  .studio-header { flex-direction:column; align-items:stretch; gap:16px; margin-bottom:18px; }
  .studio-heading { gap:8px; }
  h1 { font-size:19px; }
  .studio-controls { justify-content:flex-end; flex-wrap:wrap; gap:7px; }
  .save-state { margin-right:auto; font-size:11px; }
  .studio-controls>.export-button { display:none; }
  .studio-controls .btn { padding:0 11px; }
  .studio-grid { display:block; min-height:600px; }
  .page-settings-column { border-left:0; border-top:1px solid var(--border-color); }
  .mobile-hidden { display:none !important; }
  .studio-mobile-nav { display:flex; position:fixed; bottom:0; left:0; right:0; border-top:1px solid var(--border-color); background:#fff; padding:8px 12px calc(8px + env(safe-area-inset-bottom)); z-index:30; }
  .studio-mobile-nav button { flex:1; min-height:48px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; border:0; background:transparent; color:var(--text-sub); font-size:12px; }
  .studio-mobile-nav button[aria-pressed=true] { color:var(--primary); background:#eef3ff; border-radius:6px; }
  .copy-editor { padding:20px 16px; }
  .copy-editor textarea { font-size:16px; }
}
</style>
