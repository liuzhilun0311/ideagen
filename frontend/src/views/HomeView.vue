<template>
  <div class="home-page">
    <header class="home-heading">
      <h1>新建创作</h1>
      <p>从一个想法开始。</p>
    </header>
    <ComposerInput
      v-model="store.topic"
      v-model:reference-content="store.referenceContent"
      :images="store.userImages"
      :loading="generating"
      :cancelling="cancelling"
      :locked="otherTaskBusy || cancelling"
      :disabled="optionsLoading || !!optionsError || !modelsReady || otherTaskBusy"
      @images-change="store.userImages = $event"
      @generate="handleGenerate"
      @cancel="handleCancel"
    >
      <template #options>
        <div class="model-settings">
          <div v-for="group in settingGroups" :key="group.kind" class="model-group">
            <label :for="`${group.kind}-model`">{{ group.label }}模型</label>
            <select
              :id="`${group.kind}-model`"
              v-model="store[group.modelKey]"
              class="field"
              :disabled="session.busy || optionsLoading || !!optionsError"
            >
              <option v-if="!group.models.length" value="">暂无可用模型</option>
              <option v-for="model in group.models" :key="model.name" :value="model.name">{{ model.label }}</option>
            </select>
            <label :for="`${group.kind}-prompt`">{{ group.label }}提示词</label>
            <select
              :id="`${group.kind}-prompt`"
              v-model="store[group.promptKey]"
              class="field"
              :disabled="session.busy || optionsLoading || !!optionsError"
            >
              <option value="">系统默认</option>
              <option v-for="prompt in prompts[group.kind]" :key="prompt.name" :value="prompt.name">{{ prompt.name }}</option>
            </select>
          </div>
        </div>
      </template>
    </ComposerInput>
    <div class="home-feedback" aria-live="polite">
      <p v-if="optionsLoading" role="status">正在加载创作选项…</p>
      <div v-else-if="optionsError" class="feedback-error" role="alert">
        <p>{{ optionsError.title }}：{{ optionsError.detail }}</p>
        <button type="button" class="btn" :disabled="generating" @click="loadOptions"><RefreshCw :size="16" aria-hidden="true" />重试</button>
      </div>
      <p v-else-if="!modelsReady">
        尚未配置可用的{{ !textModels.length ? '文字' : '图片' }}模型。
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
import { ArrowUpRight, RefreshCw } from 'lucide-vue-next'
import ComposerInput from '../components/home/ComposerInput.vue'
import { useCreationOptions } from '../composables/useCreationOptions'
import { useOutlineGeneration } from '../composables/useOutlineGeneration'
import { inspirations } from '../features/templates/catalog'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
import { useStudioSession } from '../stores/studioSession'

const store = useGeneratorStore()
const router = useRouter()
const route = useRoute()
const session = useStudioSession()
const { loading: optionsLoading, refreshNeeded, error: optionsError, textModels, imageModels, prompts, load: loadOptions } = useCreationOptions()
const { generating, cancelling, error: generationError, start, cancel } = useOutlineGeneration()
const localError = ref<AppError | null>(null)
const notice = ref('')
const visibleError = computed(() => localError.value || generationError.value)
const otherTaskBusy = computed(() => session.workspaceBusy)
watch(() => generating.value || cancelling.value, value => {
  session.homeBusy = value
}, { immediate: true, flush: 'sync' })
watch([() => session.busy, optionsLoading, refreshNeeded], ([isBusy, isLoading, needsRefresh]) => {
  if (!isBusy && !isLoading && needsRefresh && route.path === '/') void loadOptions()
})
const modelsReady = computed(() =>
  textModels.value.some(model => model.name === store.outlineModelName)
  && textModels.value.some(model => model.name === store.contentModelName)
  && imageModels.value.some(model => model.name === store.imageModelName),
)
const settingGroups = computed(() => [
  { kind: 'outline', label: '大纲', modelKey: 'outlineModelName', promptKey: 'outlinePromptName', models: textModels.value },
  { kind: 'image', label: '图片', modelKey: 'imageModelName', promptKey: 'imagePromptName', models: imageModels.value },
  { kind: 'content', label: '文案', modelKey: 'contentModelName', promptKey: 'contentPromptName', models: textModels.value },
] as const)

function chooseInspiration(topic: string) {
  if (generating.value || otherTaskBusy.value) return
  if (store.topic.trim() && store.topic !== topic && !window.confirm('用这条灵感替换当前主题？参考资料和其他设置会保留。')) return
  store.topic = topic
}

async function handleGenerate() {
  if (generating.value || cancelling.value || optionsLoading.value || otherTaskBusy.value) return
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
  if (hasResults && !window.confirm('开始新创作会清除当前工作台的大纲、图片和文案。已保存的历史记录不受影响，是否继续？')) return
  if (!session.replaceDraft()) return
  store.setEntrySource('home')
  store.prepareNewOutline()
  if (await start()) {
    session.notice = '大纲已生成'
    try {
      if (route.path === '/') await router.push('/workspace')
    } catch (cause) {
      localError.value = normalizeApiError(cause, '无法打开工作台')
    }
  } else if (generationError.value) {
    session.notice = '大纲生成失败，请返回创作查看详情'
  }
}

async function handleCancel() {
  localError.value = null
  await cancel()
  notice.value = '已取消，主题和参考资料已保留。'
  session.notice = notice.value
}

function guardUnload(event: BeforeUnloadEvent) {
  if (!generating.value && !cancelling.value) return
  event.preventDefault()
  event.returnValue = ''
}
let initialActivation = true
onMounted(() => {
  if (!session.busy) void loadOptions()
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
.home-page { width: 100%; max-width: 960px; min-width: 0; margin: 0 auto; padding: 40px 24px 56px; color: #252935; }
.home-heading { margin-bottom: 28px; }
.home-heading h1 { margin: 0; font-size: 28px; line-height: 1.3; font-weight: 650; letter-spacing: 0; }
.home-heading p { margin: 10px 0 0; color: #656b78; font-size: 16px; }
.model-settings { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
.model-group { display: grid; gap: 10px; min-width: 0; align-content: start; }
.model-group label { font-size: 16px; font-weight: 500; }
.model-group select { min-width: 0; max-width: 100%; font-size: 16px; text-overflow: ellipsis; }
.model-group label:not(:first-child) { margin-top: 6px; }
.home-feedback { font-size: 16px; line-height: 1.65; color: #656b78; overflow-wrap: anywhere; }
.home-feedback:has(> *) { margin-top: 18px; }
.home-feedback a { color: #315ee8; display: inline-flex; align-items: center; min-height: 44px; text-decoration: underline; }
.feedback-error { color: #a62b35; }
.inspiration-section { margin-top: 44px; }
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
  .home-page { padding: 24px 16px 40px; }
  .home-heading { margin-bottom: 24px; }
  .model-settings { grid-template-columns: 1fr; gap: 24px; }
  .inspiration-grid { grid-template-columns: 1fr; gap: 16px; }
  .inspiration-card { display: grid; grid-template-columns: 112px minmax(0, 1fr); align-items: center; }
  .inspiration-card > img { height: 100%; min-height: 112px; aspect-ratio: 1; }
  .inspiration-copy { padding: 12px; }
  .inspiration-section { margin-top: 32px; }
}
@media (prefers-reduced-motion: reduce) { .inspiration-card { transition: none; } }
</style>
