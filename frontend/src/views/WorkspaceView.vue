<script setup lang="ts">
import { computed, onActivated, onDeactivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Check, Copy, Eye, Save, ListTree, SlidersHorizontal, PencilLine, FileText, Type, Hash, Image, Download, Square, Plus, X } from 'lucide-vue-next'
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
import PageStyleTrials from '../components/workspace/PageStyleTrials.vue'
import { usePageTrials } from '../composables/usePageTrials'
import { availableImageStyles, effectiveStyle, type StyleChoice } from '../features/styles/catalog'
import { withLayout } from '../features/generationOptions'
import { getContentDiagnostics, type GenerationDiagnostic } from '../api/diagnostics'
import { getHistory, updateHistory } from '../api/history'
import type { Page } from '../api'
import { getToken } from '../api/token'
import { publicationText as buildPublicationText } from '../utils/publicationContent'
import { normalizeApiError } from '../utils/errors'
import NewCreationButton from '../components/workspace/NewCreationButton.vue'
import ImagePromptInspector from '../components/workspace/ImagePromptInspector.vue'
import SuiteDiagnostics from '../components/workspace/SuiteDiagnostics.vue'

defineOptions({ name: 'WorkspaceView' })
const router = useRouter()
const route = useRoute()
const studio = useStudio()
const session = useStudioSession()
const { store, error, phase, busy, cancelling, editingLocked } = studio
const suiteStyle = computed(() => {
  const preset = effectiveStyle(store.imageStyle).preset
  return availableImageStyles().find(style => style.id === preset || style.catalogId === preset)
})
const failedSuitePreview = ref('')
const trials = usePageTrials(studio.save, value => { error.value = value })
const pageSettingsHost = ref<HTMLElement | null>(null)
const mobileSettingsHost = ref<HTMLElement | null>(null)
const copySettingsHost = ref<HTMLElement | null>(null)
const processing = usePostprocessing(computed(() => store.recordId))
const { state: processingState, pages: processingPages, error: processingError } = processing
const unavailable = computed(() => !!store.recordId && (
  [403, 404].includes(processingError.value?.status || 0)
  || [403, 404].includes(studio.saver.error.value?.status || 0)
))
const recoveryNotice = ref('')
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
  if (mode.value === 'copy') {
    copySettingsHost.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
    return
  }
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
const structureLocked = computed(() => session.busy || busy.value || trials.busy.value || unavailable.value)
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
const tags = computed({
  get: () => store.content.tags.map(tag => tag.replace(/^#+/, '')).filter(Boolean).map(tag => `#${tag}`).join(' '),
  set: value => { store.content.tags = value.split(/\s+/).map(tag => tag.replace(/^#+/, '')).filter(Boolean); store.content.status = 'done' },
})
const publicationText = computed(() => buildPublicationText(store.content, store.content.selectedTitleIndex))
const copying = ref(false)
const copyMessage = ref('')
const copyFailed = ref(false)
const copyDiagnostics = ref<GenerationDiagnostic[]>([])
const copyDiagnosticsDialog = ref<HTMLDialogElement | null>(null)
const copyDiagnosticsError = ref('')
const copyDiagnosticsLoading = ref(false)
async function showCopyDiagnostics() {
  copyDiagnostics.value = []
  copyDiagnosticsError.value = ''
  copyDiagnosticsDialog.value?.showModal()
  const recordId = store.content.diagnostic_record_id
  const token = getToken()
  if (!recordId) return
  copyDiagnosticsLoading.value = true
  try {
    const result = await getContentDiagnostics(recordId)
    if (getToken() === token && store.content.diagnostic_record_id === recordId) copyDiagnostics.value = result.events
  } catch {
    copyDiagnosticsError.value = '文案诊断加载失败，请重新打开重试。'
  } finally { copyDiagnosticsLoading.value = false }
}
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
async function copyTitle(index: number) {
  const title = store.content.titles[index]?.trim()
  if (title) await copyPublication(title)
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
async function changeStructure(pages: Page[], selection: number) {
  if (structureLocked.value) return
  if ((store.images.length || trials.candidates.value.length)
    && !window.confirm('修改页面结构会清除当前图片和候选图，是否继续？')) return
  session.structureBusy = true
  const revision = session.revision
  const token = getToken()
  const active = () => revision === session.revision && token === getToken()
  try {
    const nextPages = pages.map((page, index) => ({ ...page, index }))
    if (store.recordId) {
      if (!await studio.save() || !active()) return
      const recordId = store.recordId
      const previous = await getHistory(recordId)
      if (!active() || recordId !== store.recordId) return
      if (!previous.success || !previous.record) throw previous.error || '无法读取作品'
      if (JSON.stringify(previous.record.outline.pages) !== JSON.stringify(store.outline.pages)) {
        throw new Error('大纲已被修改，请刷新后重试。')
      }
      const outline = { ...previous.record.outline, pages: nextPages,
        raw: nextPages.map(page => page.content).join('\n\n<page>\n\n') }
      const result = await updateHistory(recordId, {
        structure_change: { expected_outline: previous.record.outline, outline },
      })
      if (!active() || recordId !== store.recordId) return
      if (!result.success) throw result.error || result.error_message || '页面结构保存失败'
    }
    store.outline.pages = nextPages
    store.syncRawFromPages()
    store.images = []
    store.taskId = null
    trials.clear()
    store.progress = { current: 0, total: nextPages.length, status: 'idle' }
    store.stage = 'outline'
    selected.value = Math.max(0, Math.min(selection, nextPages.length - 1))
    store.saveToStorage()
    await processing.refresh()
  } catch (cause) {
    if (active()) error.value = normalizeApiError(cause, '页面修改失败，原页面和图片已保留')
  } finally {
    session.structureBusy = false
  }
}
async function movePage(from: number, to: number) {
  const pages = [...store.outline.pages]
  if (from === to || from < 0 || to < 0 || from >= pages.length || to >= pages.length) return
  const [page] = pages.splice(from, 1)
  pages.splice(to, 0, page)
  await changeStructure(pages, to)
}
async function deletePage(index: number) {
  if (structureLocked.value || store.outline.pages.length <= 1 || !window.confirm('确定删除这一页？')) return
  await changeStructure(store.outline.pages.filter(page => page.index !== index), selected.value)
}
async function addPage() {
  await changeStructure([...store.outline.pages, { index: store.outline.pages.length, type: 'content', content: '' }], store.outline.pages.length)
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
  session.workspacePath = route.path === '/workspace/copy' ? '/workspace/copy' : '/workspace'
  store.saveToStorage()
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
        <button class="icon-button back-button" title="返回创作设置" aria-label="返回创作设置"
          @click="goBackFromWorkspace"><ArrowLeft :size="19" /></button>
        <div><span class="studio-kicker">创作工作台</span><h1>{{ store.topic || '未命名作品' }}</h1></div>
      </div>
      <div class="studio-controls">
        <span class="save-state" role="status"><Check v-if="!dirty && !saving" :size="14" />{{ saving ? '正在保存' : dirty ? '有未保存的修改' : '已保存' }}</span>
        <button v-if="mode === 'images'" class="icon-button export-button" title="导出大纲" aria-label="导出大纲" :disabled="!store.outline.pages.length" @click="exportOutline"><Download :size="17" /></button>
        <NewCreationButton />
        <button class="btn btn-secondary" :disabled="busy || session.structureBusy || unavailable" @click="studio.save"><Save :size="16" /><span>保存</span></button>
        <button class="btn btn-primary" :disabled="busy || session.structureBusy || unavailable || !store.images.some(image => image.status === 'done')" @click="preview"><Eye :size="16" /><span>预览作品</span></button>
      </div>
    </header>
    <nav class="workspace-navigation" aria-label="创作页面">
      <RouterLink to="/workspace" :class="{ active: mode === 'images' }"><Image :size="18" />图片制作</RouterLink>
      <RouterLink to="/workspace/copy" :class="{ active: mode === 'copy' }"><FileText :size="18" />文案制作</RouterLink>
    </nav>
    <section v-if="unavailable" class="draft-recovery" role="status">
      <div><strong>原作品已删除或无法访问</strong><p>当前文字草稿仍保留，旧图片已不可用。</p></div>
      <button class="btn btn-primary" :disabled="session.busy" @click="recoverDraft"><Plus :size="18" />转为新作品继续</button>
    </section>
    <p v-if="recoveryNotice" class="recovery-notice" role="status">{{ recoveryNotice }}</p>
    <section v-if="mode === 'images'" class="generation-toolbar" aria-label="整套生成工具栏">
      <div class="generation-controls">
        <div class="toolbar-section-heading"><strong>生成设置</strong><span>当前作品</span></div>
        <GenerationPanel class="suite-generation-panel" :mode="mode" :text-models="textModels" :image-models="imageModels" :prompts="prompts"
          :busy="controlsBusy" :phase="phase" @run="studio.run" />
      </div>
      <section class="creation-actions" aria-label="创作操作">
        <div class="toolbar-section-heading"><strong>生成操作</strong><span>按需执行</span></div>
        <button v-if="!trials.busy.value && (!phase || phase === 'retry')" class="btn btn-primary image-action" title="只生成尚未生成的页面" :disabled="!canGenerateImages || !trials.missing.value.length" @click="trials.batch()">
          <Image :size="18" />生成剩余 {{ trials.missing.value.length }} 张
        </button>
        <button v-if="mode === 'images' && store.outline.pages.length" class="btn btn-secondary regenerate-action" title="重新生成当前作品的全部页面" :disabled="!canGenerateImages" @click="trials.batch(true)">
          <Image :size="18" />重新生成 {{ store.outline.pages.length }} 张
        </button>
        <button v-if="trials.busy.value" class="btn btn-secondary image-action stop-action"
          :title="trials.stopping.value ? '本张完成后停止' : '停止后续生成'"
          :aria-label="trials.stopping.value ? '本张完成后停止' : '停止后续生成'"
          :disabled="trials.stopping.value" @click="trials.stop"><Square :size="16" />{{ trials.stopping.value ? '停止中' : '停止生成' }}</button>
        <button v-if="!trials.busy.value && phase && phase !== 'retry'" class="btn btn-secondary image-action cancel-action" :disabled="cancelling" @click="studio.cancel">
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
      <figure class="suite-style-reference">
        <figcaption>风格参考图</figcaption>
        <div class="suite-reference-content">
        <button v-if="suiteStyle?.previewUrl && failedSuitePreview !== suiteStyle.previewUrl" type="button"
          :aria-label="`查看${suiteStyle.name}风格参考图`" title="放大查看风格参考图"
          @click="openCandidateImage(suiteStyle.previewUrl)">
          <img :src="suiteStyle.previewUrl" :alt="`${suiteStyle.name}风格参考图`"
            @error="failedSuitePreview = suiteStyle?.previewUrl || ''" />
        </button>
        <span v-else>暂无参考图</span>
        <div v-if="suiteStyle" class="suite-reference-description" tabindex="0" role="region" aria-label="风格参考图描述">
          <strong>{{ suiteStyle.name }}</strong>
          <p v-if="suiteStyle.detail || suiteStyle.scenes">{{ suiteStyle.detail || suiteStyle.scenes }}</p>
          <small>{{ failedSuitePreview === suiteStyle.previewUrl ? '参考图暂不可用' : suiteStyle.previewLabel }}</small>
        </div>
        </div>
      </figure>
      <div class="suite-prompt-action">
        <ImagePromptInspector :index="store.outline.pages[0]?.index ?? 0" :style="store.imageStyle" suite
          :disabled="controlsBusy || !store.outline.pages.length" />
      </div>
      <div class="suite-diagnostics-action"><SuiteDiagnostics /></div>
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
          :controls-host="mobilePanel === 'tools' ? mobileSettingsHost : pageSettingsHost" :has-image="!!currentImage?.url" :page-content="current.content"
          @trial="runPageTrial" @adopt="trials.adopt" @apply="trials.applyStyle" @refresh="trials.refresh"
          @layout-change="updateCurrentLayout" @preview="openCandidateImage">
        <PageEditor :page="current" :image="currentImage" :locked="editingLocked || trials.busy.value || session.structureBusy"
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
        <PageEditor v-if="mode === 'images'" :page="current" :locked="editingLocked || trials.busy.value || session.structureBusy"
          :show-canvas="unavailable" :can-retry="false"
          @update="current && store.updatePage(current.index, $event)" />
        <section v-else class="copy-editor" aria-label="文案制作">
          <div class="copy-heading">
            <div><span class="copy-kicker">内容工作区</span><h2>文案制作</h2><p>整理标题、正文和标签，生成后可直接编辑。</p></div>
            <button class="btn btn-secondary copy-all-button" aria-label="复制全部文案" :disabled="copying || !publicationText" @click="copyPublication(publicationText)"><Copy :size="16" />复制全部</button>
          </div>
          <p v-if="store.content.status === 'generating'" role="status">正在生成文案</p>
          <p v-if="store.content.error" class="copy-error" role="alert">{{ store.content.error }}</p>
          <p v-if="copyMessage" :class="{ 'copy-error': copyFailed }" :role="copyFailed ? 'alert' : 'status'">{{ copyMessage }}</p>
          <fieldset class="title-options copy-section" :disabled="editingLocked">
            <legend><Type :size="18" aria-hidden="true" />标题备选</legend>
            <div v-if="!store.content.titles.length" class="copy-title-empty">
              <span>{{ store.content.status === 'generating' ? '正在生成标题…' : '待生成标题' }}</span>
              <button class="btn btn-secondary" @click="store.content.titles.push('')"><Plus :size="16" />添加标题</button>
            </div>
            <div v-for="(_, index) in store.content.titles" :key="index" class="title-option">
              <div class="title-choice">
                <input v-model="store.content.selectedTitleIndex" type="radio" name="workspace-title" :value="index" :aria-label="`采用标题 ${index + 1}`" />
                <input v-model="store.content.titles[index]" class="field" :aria-label="`标题 ${index + 1}`" placeholder="作品标题" />
              </div>
              <button class="icon-button title-copy" type="button" :title="`复制标题 ${index + 1}`" :aria-label="`复制标题 ${index + 1}`"
                :disabled="copying || !store.content.titles[index]?.trim()" @click="copyTitle(index)">
                <Copy :size="16" />
              </button>
            </div>
          </fieldset>
          <section class="copy-section" aria-labelledby="copy-body-heading">
          <div class="copy-field-heading">
            <label id="copy-body-heading" for="copy-body"><FileText :size="18" aria-hidden="true" />正文</label>
            <button class="icon-button" title="复制正文" aria-label="复制正文" :disabled="copying || !store.content.copywriting" @click="copyPublication(store.content.copywriting)"><Copy :size="17" /></button>
          </div>
          <textarea id="copy-body" v-model="store.content.copywriting" :disabled="editingLocked" rows="12"
            :placeholder="store.content.status === 'generating' ? '正在生成正文…' : '待生成正文'" @input="store.content.status = 'done'"></textarea>
          </section>
          <section class="copy-section" aria-labelledby="copy-tags-heading">
            <div class="copy-field-heading">
              <label id="copy-tags-heading" for="copy-tags"><Hash :size="18" aria-hidden="true" />标签</label>
              <button type="button" class="icon-button" title="复制全部标签" aria-label="复制全部标签" :disabled="copying || !tags" @click="copyPublication(tags)"><Copy :size="17" /></button>
            </div>
            <input id="copy-tags" v-model="tags" :disabled="editingLocked" class="field" :placeholder="store.content.status === 'generating' ? '正在生成标签…' : '待生成标签'" />
          </section>
        </section>
      </section>
      <aside v-if="mode === 'copy'" ref="copySettingsHost" class="copy-settings-column" aria-label="文案制作设置">
        <button class="btn btn-primary copy-action" :disabled="!canGenerateCopy" @click="generateCopy">
          <FileText :size="18" />{{ phase === 'content' ? '正在生成文案' : store.content.copywriting.trim() ? '重新生成文案' : '生成文案' }}
        </button>
        <button v-if="phase && phase !== 'retry'" class="btn btn-secondary" :disabled="cancelling" @click="studio.cancel"><Square :size="16" />{{ cancelLabel }}</button>
        <button v-if="trials.busy.value" class="btn btn-secondary" :disabled="trials.stopping.value" @click="trials.stop"><Square :size="16" />停止后续生成</button>
        <GenerationPanel :mode="mode" :text-models="textModels" :image-models="imageModels" :prompts="prompts"
          :busy="controlsBusy" :phase="phase" @run="studio.run" />
        <section class="copy-diagnostics-section" aria-label="诊断与生成详情">
          <button class="btn btn-secondary" @click="showCopyDiagnostics"><FileText :size="16" />查看请求与响应</button>
        </section>
      </aside>
      <aside v-if="mode === 'images'" ref="pageSettingsHost" class="page-settings-column" aria-label="当前页设置"></aside>
    </div>
    <dialog ref="copyDiagnosticsDialog" class="diagnostics-dialog">
      <header><h2>文案生成诊断</h2><button class="icon-button" aria-label="关闭诊断" @click="copyDiagnosticsDialog?.close()"><X :size="20" /></button></header>
      <p v-if="copyDiagnosticsLoading" role="status">正在加载文案请求与响应…</p>
      <p v-else-if="copyDiagnosticsError" role="alert">{{ copyDiagnosticsError }}</p>
      <p v-else-if="!copyDiagnostics.length">尚无可查看的文案生成记录；新生成的文案请求会独立记录。</p>
      <article v-for="(event, index) in copyDiagnostics" :key="`${event.at}-${index}`"><strong>{{ event.source === 'upstream' ? '中转站 · ' : '本地摘要 · ' }}{{ event.event === 'request' ? '发送请求' : '返回结果' }}</strong><pre>{{ JSON.stringify(event, null, 2) }}</pre></article>
    </dialog>
    <dialog ref="settingsDialog" class="mobile-settings-dialog" @close="mobilePanel = 'editor'" @click="($event.target === settingsDialog) && settingsDialog?.close()">
      <header><strong>生成设置</strong><button class="icon-button" aria-label="关闭生成设置" @click="settingsDialog?.close()"><X :size="20" /></button></header>
      <div ref="mobileSettingsHost"></div>
    </dialog>
    <nav class="studio-mobile-nav" aria-label="工作台分区">
      <button v-if="mode === 'images'" :aria-pressed="mobilePanel === 'structure'" @click="mobilePanel = 'structure'"><ListTree :size="19" />结构</button>
      <button :aria-pressed="mobilePanel === 'editor'" @click="mobilePanel = 'editor'"><PencilLine :size="19" />编辑</button>
      <button :aria-pressed="mobilePanel === 'tools'" @click="openTools"><SlidersHorizontal :size="19" />{{ mode === 'images' ? '试用与设置' : '文案设置' }}</button>
    </nav>
    <ImageViewer :visible="!!viewer" :src="viewer" :alt="`第 ${selected + 1} 页${viewerLabel}`" @close="viewer = ''" />
  </div>
</template>

<style scoped>
.studio { max-width:1440px; width:100%; margin:0 auto; }
.generation-toolbar {
  display:grid; grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
  align-items:end; gap:12px; margin-bottom:16px; padding:16px;
  border-block:1px solid var(--border-color); background:var(--bg-card);
}
/* All parameter groups participate in the same grid, without fixed column indices. */
.generation-toolbar .generation-controls,
.generation-toolbar .creation-actions,
.generation-toolbar .suite-processing-settings,
.generation-toolbar .suite-generation-panel,
.suite-generation-panel :deep(.image-settings-section),
.suite-generation-panel :deep(.image-parameters),
.suite-generation-panel :deep(.parameter-grid),
.suite-processing-settings :deep(.processing-toolbar),
.suite-processing-settings :deep(.batch-controls),
.suite-processing-settings :deep(.automatic-controls) {
  display:contents;
}
.generation-toolbar .toolbar-section-heading,
.suite-generation-panel :deep(.panel-intro),
.suite-generation-panel :deep(.style-select>.scene),
.suite-generation-panel :deep(.style-picker>details),
.suite-generation-panel :deep(.style-picker>p),
.suite-generation-panel :deep(.outline-adjustments),
.suite-generation-panel :deep(.advanced-settings),
.suite-generation-panel :deep(.page-tools-divider) { display:none; }
.suite-generation-panel :deep(.panel-intro) { display:flex; grid-column:1/-1; order:-3; margin:0; }
.suite-generation-panel :deep(.style-picker>.selection-status) { display:block; grid-column:1/-1; }
.suite-generation-panel :deep(.style-picker) {
  grid-column:span 2; min-width:0; padding:0; border:0; align-self:end;
}
.suite-generation-panel :deep(.generation-group) {
  grid-column:span 2; order:4; display:grid; gap:6px;
  min-width:0; margin:0; padding:0; border:0;
}
.suite-generation-panel :deep(.style-picker) { order:-1; }
.suite-generation-panel :deep(.parameter-grid label),
.suite-generation-panel :deep(.reference-toggle),
.suite-generation-panel :deep(.style-select>label),
.suite-processing-settings :deep(label) {
  display:grid; gap:6px; min-width:0; margin:0;
  color:var(--text-sub); font-size:13px; line-height:20px; white-space:nowrap;
}
.suite-generation-panel :deep(.generation-group>label) {
  margin:0; font-size:13px; line-height:20px; color:var(--text-sub);
}
.generation-toolbar :deep(.field),
.suite-generation-panel :deep(.reference-toggle select),
.suite-generation-panel :deep(.selection-row select),
.suite-processing-settings :deep(select) {
  width:100%; min-width:0; height:44px; min-height:44px; margin:0;
  padding:8px 10px; font-size:13px; border:1px solid var(--border-color);
  border-radius:6px; background:var(--bg-card); text-overflow:ellipsis;
}
.generation-toolbar .creation-actions>.btn,
.suite-processing-settings :deep(.batch-controls>.btn) {
  min-width:0; width:100%; height:44px; min-height:44px; margin:0;
  padding:8px; font-size:13px; line-height:20px; white-space:nowrap;
}
.generation-toolbar .creation-actions>.btn { order:2; }
.suite-processing-settings :deep(.batch-controls>.btn) { order:3; }
.suite-processing-settings :deep(.automatic-controls>span) { grid-column:1/-1; order:5; font-size:13px; }
.generation-toolbar.copy-toolbar { grid-template-columns:minmax(0,1fr) auto; }
.copy-toolbar .suite-generation-panel :deep(.generation-group) { grid-column:1; }
.copy-toolbar .creation-actions>.btn { width:auto; padding-inline:16px; }
.copy-toolbar .suite-generation-panel :deep(.generation-group) { grid-template-columns:minmax(180px,1.35fr) repeat(3,minmax(130px,1fr)); align-items:end; column-gap:12px; row-gap:6px; }
.copy-toolbar .suite-generation-panel :deep(.generation-group>label) { grid-column:1; grid-row:1; }
.copy-toolbar .suite-generation-panel :deep(.generation-group>select) { grid-column:1; grid-row:2; }
.copy-toolbar .suite-generation-panel :deep(.generation-group>fieldset) { grid-column:2/-1; grid-row:1/3; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0 12px; align-items:end; }
.copy-toolbar .suite-generation-panel :deep(.generation-group>fieldset>label) { grid-row:1; margin:0 0 6px; min-width:0; }
.copy-toolbar .suite-generation-panel :deep(.generation-group>fieldset>select) { grid-row:2; min-width:0; }
.page-settings-column { min-width:0; border-left:1px solid var(--border-color); background:#fff; }
.copy-settings-column { min-width:0; border-left:1px solid var(--border-color); background:#fff; padding:22px 18px; }
.copy-settings-column .copy-action { width:100%; min-height:44px; margin:0 0 20px; }
.copy-diagnostics-section { display:grid; gap:10px; margin-top:20px; padding-top:18px; border-top:1px solid var(--border-color); }
.copy-diagnostics-section button { min-height:44px; width:100%; }
.diagnostics-dialog { width:min(760px,calc(100% - 24px)); max-height:calc(100dvh - 32px); overflow:auto; margin:auto; padding:20px; border:1px solid var(--border-color); border-radius:8px; background:#fff; }
.diagnostics-dialog::backdrop { background:#151d3266; }
.diagnostics-dialog header { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.diagnostics-dialog h2 { margin:0; font-size:18px; }
.diagnostics-dialog article { margin-top:14px; border-top:1px solid var(--border-color); padding-top:12px; }
.diagnostics-dialog pre { max-height:300px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; font:12px/1.5 ui-monospace,Consolas,monospace; }
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
.studio-grid.copy-grid { grid-template-columns:minmax(0,1fr) 300px; }
.studio-center { min-width:0; }
.copy-editor { box-sizing:border-box; min-width:0; width:100%; padding:24px; }
.copy-editor h2 { font-size:22px; margin:3px 0 6px; }
.copy-kicker { color:var(--primary); font-size:12px; font-weight:650; letter-spacing:.04em; }
.copy-heading p { margin:0; color:var(--text-sub); font-size:13px; }
.copy-heading { align-items:flex-start; }
.copy-all-button { min-height:40px; white-space:nowrap; }
.copy-editor label { display:block; margin:22px 0 9px; font-size:13px; font-weight:650; color:var(--text-main); }
.copy-editor textarea { width:100%; padding:12px; border:1px solid var(--border-color); border-radius:6px; font:inherit; font-size:15px; line-height:1.8; resize:vertical; }
.copy-editor textarea:focus, .copy-editor .field:focus { border-color:var(--primary); box-shadow:0 0 0 3px rgba(47,91,234,.12); outline:0; }
.title-options { min-width:0; margin:16px 0 0; padding:0; border:0; }
.title-options legend { margin-bottom:7px; font-size:13px; font-weight:650; color:var(--text-main); }
.copy-editor .title-option { display:grid; grid-template-columns:minmax(0,1fr) 40px; align-items:center; gap:8px; margin:0 0 6px; }
.copy-editor .title-choice { display:grid; grid-template-columns:18px minmax(0,1fr); align-items:center; gap:8px; margin:0; }
.title-option input[type="radio"] { width:16px; height:16px; margin:0; accent-color:var(--primary); }
.title-option .field { width:100%; min-height:38px; padding:7px 10px; }
.title-copy { width:40px; height:38px; }
.title-empty { color:var(--text-sub); font-size:13px; }
.copy-editor #copy-body { min-height:300px; }
.copy-editor .field { width:100%; min-height:44px; }
.copy-editor .copy-section { min-width:0; margin:20px 0 0; padding:20px 0 0; border:0; border-top:1px solid var(--border-color); }
.copy-editor .title-options { padding-top:16px; }
.copy-editor .title-options legend { display:flex; align-items:center; gap:8px; margin:0; padding:0 12px 0 0; font-size:14px; }
.copy-editor .copy-field-heading { min-height:32px; margin:0 0 10px; }
.copy-editor .copy-field-heading label { display:flex; align-items:center; gap:8px; margin:0; font-size:14px; }
.copy-title-empty { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; min-height:72px; padding:12px 16px; border:1px dashed var(--border-color); border-radius:6px; background:#f8fafc; color:var(--text-sub); font-size:14px; }
.copy-title-empty .btn { min-height:36px; padding:6px 12px; font-size:13px; }
.copy-editor .copy-section textarea, .copy-editor .copy-section > .field { box-sizing:border-box; background:#f8fafc; }
.copy-editor .copy-section textarea:focus, .copy-editor .copy-section > .field:focus { background:#fff; }
.copy-editor .copy-section ::placeholder { color:#788397; opacity:1; }
.copy-error { color:#b33d26; font-size:14px; }
.studio-mobile-nav { display:none; }
.suite-style-reference { grid-column:1/-1; order:5; margin:0; display:grid; gap:6px; min-width:0; align-self:start; }
.suite-style-reference figcaption { font-size:13px; color:var(--text-sub); }
.suite-style-reference button { padding:0; width:100%; height:110px; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-card); cursor:zoom-in; }
.suite-style-reference img { width:100%; height:100%; object-fit:contain; display:block; }
.suite-reference-content { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.2fr); gap:10px; align-items:center; min-width:0; }
.suite-reference-content>span { color:var(--text-sub); font-size:13px; }
.suite-reference-description { min-width:0; min-height:0; max-height:110px; overflow-y:auto; overflow-x:hidden; overflow-wrap:anywhere; scrollbar-gutter:stable; overscroll-behavior:contain; padding-right:4px; }
.suite-reference-description:focus-visible { outline:2px solid var(--primary); outline-offset:2px; }
.suite-reference-description strong { display:block; font-size:12px; line-height:1.5; }
.suite-reference-description p { margin:6px 0; font-size:12px; line-height:1.6; color:var(--text-sub); }
.suite-reference-description small { font-size:11px; line-height:1.5; color:var(--text-sub); }
.suite-prompt-action,.suite-diagnostics-action { order:4; min-width:0; }
.suite-prompt-action :deep(button.prompt-preview-button),
.suite-diagnostics-action :deep(button.suite-diagnostics-button) { width:100%; min-height:44px; margin:0; font-size:12px; padding:4px; gap:4px; }
@media(min-width:1101px) {
  .generation-toolbar { grid-template-columns:repeat(24,minmax(0,1fr)); gap:12px 4px; }
  .suite-generation-panel :deep(.panel-intro) { display:none; }
  .suite-generation-panel :deep(.style-picker) { display:contents; }
  .suite-generation-panel :deep(.style-picker>.style-select) { grid-column:17/21; grid-row:1; order:-2; align-self:start; }
  .suite-generation-panel :deep(.style-picker>.palette-control) { grid-column:1/3; grid-row:1; order:-1; align-self:start; }
  .suite-generation-panel :deep(.palette-control) { position:relative; }
  .suite-generation-panel :deep(.palette-control>label) { color:var(--text-sub); line-height:20px; }
  .suite-generation-panel :deep(.palette-control select) { height:44px; }
  .suite-generation-panel :deep(.palette-control>.swatches),
  .suite-generation-panel :deep(.palette-control>.colors) {
    position:absolute; top:0; right:0; height:20px; gap:3px; flex-wrap:nowrap;
  }
  .suite-generation-panel :deep(.palette-control>.swatches span) { width:12px; height:12px; flex-shrink:0; }
  .suite-generation-panel :deep(.palette-control>.swatches small) { display:none; }
  .suite-generation-panel :deep(.palette-control>.colors label) { font-size:0; gap:0; }
  .suite-generation-panel :deep(.palette-control>.colors input) { width:14px; height:20px; padding:0; margin:0; }
  .suite-generation-panel :deep(.parameter-grid label) { grid-column:span 2; grid-row:1; }
  .suite-generation-panel :deep(.reference-toggle) { grid-column:11/13; grid-row:1; }
  .suite-processing-settings :deep(.batch-controls>label) { grid-column:13/15; grid-row:1; }
  .suite-processing-settings :deep(.automatic-toggle) { grid-column:15/17; grid-row:1; }
  .generation-toolbar .creation-actions>.image-action { grid-column:5/7; grid-row:2; }
  .generation-toolbar .creation-actions>.regenerate-action { grid-column:7/9; grid-row:2; }
  .generation-toolbar .creation-actions>.stop-action { white-space:nowrap; }
  .suite-processing-settings :deep(.process-pending) { grid-column:9/12; grid-row:2; }
  .suite-processing-settings :deep(.process-again) { grid-column:12/15; grid-row:2; }
  .suite-generation-panel :deep(.generation-group) { grid-column:1/5; grid-row:2; }
  .suite-prompt-action { grid-column:15/18; grid-row:2; }
  .suite-diagnostics-action { grid-column:18/21; grid-row:2; }
  .suite-style-reference { grid-column:21/25; grid-row:1/3; }
  .generation-toolbar .creation-actions>.btn,
  .suite-processing-settings :deep(.batch-controls>.btn) { padding:4px; gap:4px; font-size:12px; line-height:16px; white-space:normal; }
  .generation-toolbar .creation-actions>.btn svg,
  .suite-processing-settings :deep(.batch-controls>.btn svg) { width:14px; height:14px; flex-shrink:0; }
  .suite-generation-panel :deep(.parameter-grid label),
  .suite-generation-panel :deep(.reference-toggle) { align-self:start; }
  .suite-processing-settings :deep(.batch-controls>label),
  .suite-processing-settings :deep(.automatic-toggle) { align-self:start; }
}
@media(max-width:1100px) and (min-width:701px) {
  .studio-grid { grid-template-columns:150px minmax(0,1fr) 280px; }
  .studio-grid.copy-grid { grid-template-columns:minmax(0,1fr) 250px; }
  .copy-grid .generation-panel { grid-column:auto; }
  .save-state { display:none; }
}
@media(max-width:700px) {
  .generation-toolbar, .generation-toolbar.copy-toolbar { grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; padding:12px 0; }
  .copy-toolbar .suite-generation-panel :deep(.generation-group) { grid-column:1/-1; }
  .generation-toolbar :deep(.field), .suite-generation-panel :deep(.selection-row select),
  .suite-generation-panel :deep(.reference-toggle select), .suite-processing-settings :deep(select) { font-size:16px; }
  .studio { padding-bottom:84px; }
  .studio-header { flex-direction:column; align-items:stretch; gap:16px; margin-bottom:18px; padding:10px 0 8px; }
  .studio-heading { gap:8px; }
  h1 { font-size:19px; }
  .studio-controls { justify-content:flex-end; flex-wrap:wrap; gap:7px; }
  .save-state { margin-right:auto; font-size:11px; }
  .studio-controls>.export-button { display:none; }
  .studio-controls .btn { padding:0 11px; }
  .studio-grid { display:block; min-height:600px; }
  .page-settings-column { border-left:0; border-top:1px solid var(--border-color); }
  .copy-settings-column { border-left:0; border-top:1px solid var(--border-color); }
  .mobile-hidden { display:none !important; }
  .studio-mobile-nav { display:flex; position:fixed; bottom:0; left:0; right:0; border-top:1px solid var(--border-color); background:#fff; padding:8px 12px calc(8px + env(safe-area-inset-bottom)); z-index:30; }
  .studio-mobile-nav button { flex:1; min-height:48px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; border:0; background:transparent; color:var(--text-sub); font-size:12px; }
  .studio-mobile-nav button[aria-pressed=true] { color:var(--primary); background:#eef3ff; border-radius:6px; }
  .copy-editor { padding:22px 16px; }
  .copy-all-button { min-height:40px; }
  .copy-toolbar .suite-generation-panel :deep(.generation-group) { grid-template-columns:1fr; }
  .copy-toolbar .suite-generation-panel :deep(.generation-group>label),
  .copy-toolbar .suite-generation-panel :deep(.generation-group>select),
  .copy-toolbar .suite-generation-panel :deep(.generation-group>fieldset) { grid-column:1; grid-row:auto; }
  .copy-toolbar .suite-generation-panel :deep(.generation-group>fieldset) { grid-template-columns:1fr; gap:0; }
  .copy-toolbar .suite-generation-panel :deep(.generation-group>fieldset>label),
  .copy-toolbar .suite-generation-panel :deep(.generation-group>fieldset>select) { grid-column:1; grid-row:auto; }
  .copy-editor textarea { font-size:16px; }
}
</style>
