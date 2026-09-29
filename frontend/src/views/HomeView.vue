<template>
  <div class="home-page">
    <header class="home-heading">
      <div>
        <p class="eyebrow">创作工作台</p>
        <h1>{{ store.outline.pages.length ? '创作设置' : '新建创作' }}</h1>
        <p>{{ store.outline.pages.length ? store.topic || '未命名作品' : '输入主题，先生成一套可编辑的大纲。' }}</p>
      </div>
      <div class="heading-actions">
        <NewCreationButton />
        <button class="btn btn-primary heading-enter-button" :disabled="!store.outline.pages.length || generating || cancelling || session.draftSaving" @click="enterImage制作">{{ store.outline.pages.length ? '继续图文制作' : '进入图文制作' }}</button>
      </div>
    </header>
    <div class="home-workspace">
    <ComposerInput
      v-model="store.topic"
      v-model:reference-content="store.referenceContent"
      :images="store.userImages"
      :loading="generating"
      :cancelling="cancelling"
      :locked="otherTaskBusy || cancelling || session.referenceLoading"
      :show-actions="false"
      :reference-mode="referenceMode"
      @update:reference-mode="referenceMode = $event"
      :disabled="optionsLoading || !!optionsError || !modelsReady || otherTaskBusy"
      @images-change="store.userImages = $event"
      @generate="handleGenerate"
      @cancel="handleCancel"
    />
    <aside class="home-actions-panel" aria-label="大纲生成设置与操作">
      <button class="btn btn-primary home-generate-button" :disabled="!store.topic.trim() || generating || cancelling || optionsLoading || !!optionsError || !modelsReady || otherTaskBusy || session.referenceLoading" @click="handleGenerate">{{ cancelling ? '正在取消' : generating ? '正在生成大纲' : store.outline.pages.length ? '重新生成大纲' : '生成大纲' }}</button>
      <button v-if="generating || cancelling" class="btn btn-secondary" :disabled="cancelling" @click="handleCancel"><Square :size="16" />{{ cancelling ? '正在取消' : '取消生成' }}</button>
      <GrowthTargetOptions :disabled="session.busy" />
      <OutlineOptions id="outline-home" :disabled="session.busy" :show-growth="false" :show-advanced="false" />
      <div class="model-settings">
        <div v-for="group in settingGroups" :key="group.kind" class="model-group">
          <label :for="`${group.kind}-model-home`">{{ group.label }}模型 <HelpTip text="模型决定生成大纲时使用的文本模型。" /></label>
          <select :id="`${group.kind}-model-home`" v-model="store[group.modelKey]" class="field" :disabled="session.busy || optionsLoading || !!optionsError">
            <option v-if="!group.models.length" value="">暂无可用模型</option>
            <option v-for="model in group.models" :key="model.name" :value="model.name">{{ model.label }}</option>
          </select>
        </div>
      </div>
      <div class="home-outline-actions">
      <button class="btn btn-secondary" :disabled="!store.outline.pages.length || session.busy" @click="openOutlineEditor"><FilePenLine :size="18" aria-hidden="true" />查看|编辑大纲</button>
      <OutlineRecommendation label="查看图文推荐方案" />
      <OutlinePromptInspector :busy="session.busy" home />
      <OutlineDiagnostics :record-id="generating || cancelling ? undefined : store.outline.diagnostic_record_id || store.outline.generation_record_id" />
      </div>
    </aside>
    </div>
    <dialog ref="outlineDialog" class="home-diagnostics" aria-labelledby="outline-editor-heading">
      <header><h2 id="outline-editor-heading">查看|编辑大纲</h2><button class="icon-button" aria-label="关闭大纲" @click="outlineDialog?.close()"><X :size="20" /></button></header>
      <OutlineParameterSummary />
      <article v-for="(page, index) in editablePages" :key="page.index">
        <label :for="`outline-edit-${page.index}`">P{{ index + 1 }} · {{ page.type === 'cover' ? '封面' : page.type === 'summary' ? '总结' : page.type === 'infographic' ? '信息图' : '内容' }}</label>
        <textarea :id="`outline-edit-${page.index}`" v-model="page.content" class="field outline-page-editor" rows="8" :disabled="session.busy" />
      </article>
      <p v-if="outlineEditError" role="alert" class="feedback-error">{{ outlineEditError }}</p>
      <footer class="outline-editor-actions">
        <button class="btn btn-secondary" @click="outlineDialog?.close()">取消</button>
        <button class="btn btn-primary" :disabled="session.busy" @click="saveOutlineEdits"><Save :size="18" />保存</button>
      </footer>
    </dialog>
    <div class="home-feedback" aria-live="polite">
      <p v-if="session.referenceLoading" role="status">正在恢复参考图片…</p>
      <p v-else-if="session.referenceSaving" role="status">正在保存参考图片到本机…</p>
      <p v-if="optionsLoading" role="status">正在加载创作选项…</p>
      <div v-else-if="optionsError" class="feedback-error" role="alert">
        <p>{{ optionsError.title }}：{{ optionsError.detail }}</p>
      </div>
      <p v-else-if="!modelsReady">
        尚未配置可用的大纲模型。
        <RouterLink to="/settings">前往设置</RouterLink>
      </p>
      <p v-if="otherTaskBusy" role="status">已有任务正在生成，请先返回工作台完成或取消。<RouterLink to="/workspace">返回工作台</RouterLink></p>
      <p v-if="visibleError" class="feedback-error" role="alert">{{ visibleError.title }}：{{ visibleError.detail }}</p>
      <p v-if="notice" role="status">{{ notice }}</p>
    </div>
    <section class="inspiration-section" aria-labelledby="inspiration-heading">
      <div class="section-heading">
        <h2 id="inspiration-heading">创作灵感</h2>
        <span>生活里的新题材</span>
      </div>
      <div class="inspiration-grid">
        <button
          v-for="item in inspirations"
          :key="item.id"
          type="button"
          class="inspiration-card"
          :disabled="generating || otherTaskBusy"
          :aria-label="`选用灵感：${item.title}`"
          @click="chooseInspiration(item.topic)"
        >
          <img :src="item.image" :alt="item.alt" width="600" height="400" loading="lazy" />
          <span class="inspiration-copy">
            <span class="inspiration-category">{{ item.category }} · 灵感</span>
            <span class="inspiration-title">{{ item.title }}<ArrowUpRight :size="18" aria-hidden="true" /></span>
          </span>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowUpRight, FilePenLine, Save, Square, X } from 'lucide-vue-next'
import ComposerInput from '../components/home/ComposerInput.vue'
import GrowthTargetOptions from '../components/home/GrowthTargetOptions.vue'
import OutlineOptions from '../components/workspace/OutlineOptions.vue'
import OutlineRecommendation from '../components/workspace/OutlineRecommendation.vue'
import OutlinePromptInspector from '../components/workspace/OutlinePromptInspector.vue'
import HelpTip from '../components/common/HelpTip.vue'
import { useCreationOptions } from '../composables/useCreationOptions'
import { useOutlineGeneration } from '../composables/useOutlineGeneration'
import { inspirations } from '../features/templates/catalog'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
import { useStudioSession } from '../stores/studioSession'
import OutlineDiagnostics from '../components/workspace/OutlineDiagnostics.vue'
import NewCreationButton from '../components/workspace/NewCreationButton.vue'
import { useOutlineEditor } from '../composables/useOutlineEditor'
import OutlineParameterSummary from '../components/workspace/OutlineParameterSummary.vue'

const store = useGeneratorStore()
const router = useRouter()
const route = useRoute()
const session = useStudioSession()
const { loading: optionsLoading, refreshNeeded, error: optionsError, textModels, load: loadOptions } = useCreationOptions()
const { generating, cancelling, error: generationError, start, cancel } = useOutlineGeneration({ home: true })
const localError = ref<AppError | null>(null)
const notice = ref('')
const visibleError = computed(() => localError.value || generationError.value)
const otherTaskBusy = computed(() => session.workspaceBusy || session.trialBusy || session.draftSaving)
const referenceMode = computed({
  get: () => store.referenceRoles,
  set: value => { store.referenceRoles = value },
})
const outlineDialog = ref<HTMLDialogElement | null>(null)
const { pages: editablePages, error: outlineEditError, open: beginOutlineEdit, save: applyOutlineEdits } = useOutlineEditor()
function openOutlineEditor() {
  beginOutlineEdit()
  outlineDialog.value?.showModal()
}
function saveOutlineEdits() {
  if (!applyOutlineEdits()) return
  outlineDialog.value?.close()
  notice.value = '大纲修改已保存到当前草稿。已生成的图片和文案保持不变，重新生成时将使用新大纲。'
}
watch(() => generating.value || cancelling.value, value => {
  session.homeBusy = value
}, { immediate: true, flush: 'sync' })
watch([() => session.busy, optionsLoading, refreshNeeded], ([isBusy, isLoading, needsRefresh], previous) => {
  if (!isBusy && !isLoading && (needsRefresh || previous[0]) && route.path === '/') void loadOptions()
})
const modelsReady = computed(() =>
  textModels.value.some(model => model.name === store.outlineModelName)
)
const settingGroups = computed(() => [
  { kind: 'outline', label: '大纲', modelKey: 'outlineModelName', promptKey: 'outlinePromptName', models: textModels.value },
] as const)

function chooseInspiration(topic: string) {
  if (generating.value || otherTaskBusy.value) return
  if (store.topic.trim() && store.topic !== topic && !window.confirm('用这条灵感替换当前主题？参考资料和其他设置会保留。')) return
  store.topic = topic
}


async function handleGenerate() {
  if (generating.value || cancelling.value || optionsLoading.value || session.busy) return
  localError.value = null
  notice.value = ''
  if (!store.topic.trim()) {
    localError.value = normalizeApiError('请先输入主题', '无法开始创作')
    return
  }
  if (optionsError.value || !modelsReady.value) {
    localError.value = normalizeApiError('请在设置中配置可用模型，并重新加载创作选项', '模型不可用')
    return
  }
  const hasResults = !!(store.outline.raw || store.outline.pages.length || store.images.length
    || store.content.titles.length || store.content.copywriting || store.content.tags.length || store.recordId || store.taskId)
  if (store.userImages.length && !store.referenceRoles.length) {
    localError.value = normalizeApiError('已添加参考图片，请先选择需要参考的图片维度。', '请选择图片参考选项')
    return
  }
  if (hasResults && !window.confirm('新大纲成功后将替换当前大纲、图片和文案；失败或取消会保留旧稿。已保存的作品不会被覆盖，是否继续？')) return
  session.notice = ''
  if (await start()) {
    session.notice = '大纲已生成'
    try {
      notice.value = '大纲已生成，请检查内容后进入图片制作。'
    } catch (cause) {
      localError.value = normalizeApiError(cause, '无法打开工作台')
    }
  } else if (generationError.value) {
    session.notice = '大纲生成失败，请返回创作查看详情'
  }
}
async function enterImage制作() {
  if (!store.outline.pages.length || generating.value || cancelling.value || session.draftSaving) return
  store.saveToStorage()
  await router.push(session.workspacePath === '/workspace/copy' ? '/workspace/copy' : '/workspace')
}

async function handleCancel() {
  localError.value = null
  await cancel()
  notice.value = generationError.value
    ? '已停止接收生成结果，但服务端取消尚未确认。旧稿和参考资料已保留。'
    : '已取消，旧稿、主题和参考资料已保留。'
  session.notice = notice.value
}

function guardUnload(event: BeforeUnloadEvent) {
  if (!generating.value && !cancelling.value) return
  event.preventDefault()
  event.returnValue = ''
}
let initialActivation = true
onMounted(() => {
  void loadOptions()
  window.addEventListener('beforeunload', guardUnload)
})
onActivated(() => {
  // KeepAlive invokes activated immediately after mounted on the first visit.
  if (initialActivation) { initialActivation = false; return }
  if (!session.busy) void loadOptions()
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', guardUnload))
</script>

<style scoped>
.home-page { width: 100%; max-width: 1240px; min-width: 0; margin: 0 auto; padding: 0 28px 64px; color: #252935; }
.home-heading { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom:28px; }
.home-heading > div:first-child { flex:1 1 auto; min-width:0; max-width:calc(100% - 300px); }
.home-heading .heading-actions { flex:0 0 auto; min-width:max-content; }
.eyebrow { margin:0 0 8px !important; color:#315ee8 !important; font-size:12px !important; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.home-heading h1 { margin: 0; font-size: 30px; line-height: 1.25; font-weight: 650; letter-spacing: 0; }
.home-heading p:not(.eyebrow) { max-width:100%; margin: 9px 0 0; color: #656b78; font-size: 15px; overflow-wrap:anywhere; }
.home-workspace { display:grid; grid-template-columns:minmax(0,1fr) 380px; gap:24px; align-items:start; }
.home-actions-panel { display:grid; gap:14px; padding:20px; border:1px solid #e2e5eb; border-radius:8px; background:#fff; }
.home-actions-heading { display:grid; gap:4px; padding-bottom:6px; border-bottom:1px solid #e2e5eb; }
.home-actions-heading span { color:#656b78; font-size:12px; }
.home-actions-panel :deep(.outline-options) { margin:0; }
.home-actions-panel :deep(.model-settings) { display:grid; gap:12px; }
.home-actions-panel :deep(.model-group) { gap:7px; }
.home-outline-actions { display:grid; gap:14px; }
.home-outline-actions :deep(.prompt-inspector) { margin:0; }
.home-outline-actions > :deep(.btn),
.home-outline-actions :deep(.prompt-inspector > .btn) {
  display:flex; align-items:center; justify-content:center; gap:8px;
  width:100%; min-height:44px; padding:10px 12px;
  font-family:inherit; font-size:14px; font-weight:500; line-height:1.5;
}
.home-outline-actions > :deep(.btn > svg),
.home-outline-actions :deep(.prompt-inspector > .btn > svg) { width:18px; height:18px; flex-shrink:0; }
.home-actions-panel .btn { width:100%; min-height:44px; }
.heading-hint { flex:0 0 auto; color:#656b78; font-size:13px; }
.heading-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.model-settings { display: grid; grid-template-columns: 1fr; gap: 12px; }
.model-group { display: grid; gap: 10px; min-width: 0; align-content: start; }
.model-group label { display:flex; align-items:center; gap:7px; font-size:13px; font-weight:400; }
.model-group select { width:100%; min-width:0; max-width:100%; min-height:44px; padding:10px; font-size:14px; text-overflow:ellipsis; }
.model-group label:not(:first-child) { margin-top: 6px; }
.home-feedback {
  min-height: 52px; display: flex; flex-direction: column; justify-content: center;
  font-size: 16px; line-height: 1.65; color: #656b78; overflow-wrap: anywhere;
}
.outline-result { margin-top:24px; padding:22px; border:1px solid #e2e5eb; border-radius:8px; background:#fff; }
.outline-result-header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:16px; }
.outline-result-header h2 { margin:0 0 5px; font-size:20px; }
.outline-result-header span { color:#656b78; font-size:13px; }
.outline-result-actions { display:flex; gap:8px; flex-wrap:wrap; }
.outline-result-page { padding:14px 0; border-top:1px solid #e2e5eb; }
.outline-result-page strong { font-size:14px; }
.outline-result-page p { margin:8px 0 0; white-space:pre-wrap; line-height:1.7; }
.home-diagnostics { width:min(760px,calc(100% - 24px)); max-height:calc(100dvh - 32px); overflow:auto; padding:20px; border:1px solid #e2e5eb; border-radius:8px; background:#fff; }
.home-diagnostics::backdrop { background:#151d3266; }
.home-diagnostics header { display:flex; justify-content:space-between; align-items:center; }
.home-diagnostics h2 { margin:0; font-size:18px; }
.home-diagnostics article { margin-top:14px; border-top:1px solid #e2e5eb; padding-top:12px; }
.outline-page-editor { display:block; width:100%; min-height:160px; margin-top:8px; resize:vertical; line-height:1.6; }
.outline-editor-actions { display:flex; justify-content:flex-end; gap:12px; position:sticky; bottom:-20px; padding:16px 0; background:#fff; }
.home-diagnostics pre { max-height:300px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; font:12px/1.5 ui-monospace,Consolas,monospace; }
.home-feedback:has(> *) { margin-top: 0; }
.home-feedback a { color: #315ee8; display: inline-flex; align-items: center; min-height: 44px; text-decoration: underline; }
.feedback-error { color: #a62b35; }
.inspiration-section { margin-top: 52px; padding-top: 28px; border-top: 1px solid #e2e5eb; }
.section-heading { display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px 20px; margin-bottom: 18px; }
.section-heading h2 { margin: 0; font-size: 20px; line-height: 1.4; }
.section-heading > span { color: #656b78; font-size: 16px; }
.inspiration-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
.inspiration-card { min-width: 0; text-align: left; padding: 0; border: 1px solid #e2e5eb; border-radius: 8px; overflow: hidden; background: white; color: inherit; font: inherit; cursor: pointer; transition: border-color 180ms ease; }
.inspiration-card:hover { border-color: #315ee8; }
.inspiration-card:focus-visible { outline: 2px solid #315ee8; outline-offset: 3px; }
.inspiration-card:disabled { opacity: .6; cursor: not-allowed; }
.inspiration-card > img { display: block; width: 100%; height: auto; aspect-ratio: 3 / 2; object-fit: cover; background: #f7f8fa; }
.inspiration-copy { display: grid; gap: 8px; padding: 16px; }
.inspiration-category { color: #656b78; font-size: 16px; }
.inspiration-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 17px; font-weight: 600; overflow-wrap: anywhere; }
.inspiration-title svg { flex-shrink: 0; }
@media (max-width: 700px) {
  .home-page { padding: 0 16px 40px; }
  .home-heading { align-items:flex-start; flex-direction:column; gap:12px; margin-bottom:24px; }
  .heading-hint { font-size:12px; }
  .home-heading { margin-bottom: 24px; }
  .home-heading > div:first-child { max-width:none; }
  .home-workspace { grid-template-columns:1fr; }
  .outline-result { padding:16px; }
  .outline-result-header { flex-direction:column; }
  .outline-result-actions { width:100%; }
  .outline-result-actions .btn { flex:1; }
  .model-settings { grid-template-columns: 1fr; gap: 24px; }
  .inspiration-grid { grid-template-columns: 1fr; gap: 16px; }
  .inspiration-card { display: grid; grid-template-columns: 112px minmax(0, 1fr); align-items: center; }
  .inspiration-card > img { height: 100%; min-height: 112px; aspect-ratio: 1; }
  .inspiration-copy { padding: 12px; }
  .inspiration-section { margin-top: 32px; }
}
@media (min-width: 701px) and (max-width: 1100px) {
  .home-workspace { grid-template-columns:minmax(0,1fr) 320px; }
}
@media (prefers-reduced-motion: reduce) { .inspiration-card { transition: none; } }
</style>
