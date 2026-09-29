<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { FileSearch, Copy, X } from 'lucide-vue-next'
import { API_BASE_URL } from '../../api/client'
import { getToken } from '../../api/token'
import { useGeneratorStore } from '../../stores/generator'
import { useStudioSession } from '../../stores/studioSession'
import { contentSource } from '../../utils/contentSource'
import { copyPreferences, resolveCopyPreferences, isAutomaticCopy, selectCopyPreference, type CopyField } from '../../features/copyOptions'
import { selectionItems, usePromptCatalog } from '../../features/promptCatalog'
import HelpTip from '../common/HelpTip.vue'

defineProps<{ busy: boolean }>()
const store = useGeneratorStore()
const session = useStudioSession()
const options = computed(() => copyPreferences(store.outline.copy_preferences))
const catalog = usePromptCatalog()
const groups = computed(() => [
  { key: 'style' as const, label: '文案风格' },
  { key: 'structure' as const, label: '正文结构' },
  { key: 'length' as const, label: '文案长度' },
  { key: 'emoji_level' as const, label: '表情与符号丰富度' },
].map(group => ({ ...group, items: group.key === 'emoji_level'
  ? ['无', '克制', '丰富'].map(value => ({ id: value, value, name: value }))
  : selectionItems('content', group.key, options.value[group.key]).map(item => ({
    ...item, name: group.key === 'structure' && item.legacyValue === '自动' ? '跟随整套内容结构' : item.name,
  })) })))
function update(key: CopyField, event: Event) {
  store.outline.copy_preferences = selectCopyPreference(store.outline.copy_preferences, key, (event.target as HTMLSelectElement).value)
}
function automaticLabel(key: CopyField, items: { value: string; name: string }[]) {
  const value = options.value.recommendations?.[key] || copyPreferences()[key]
  const label = items.find(item => item.value === value)?.name || value
  return !label || label === '自动' ? '自动推荐' : `自动推荐（${label}）`
}
const mounted = ref(false)
const dialog = ref<HTMLDialogElement>()
const text = ref<HTMLTextAreaElement>()
const prompt = ref('')
const loading = ref(false)
const error = ref('')
const copied = ref(false)
const summary = ref('')
let version = 0
function close() { version++; dialog.value?.close(); prompt.value = '' }
async function open() {
  const ticket = ++version
  const token = getToken()
  const selected = { ...options.value }
  const input = { ...contentSource(store.topic, store.outline.pages),
    copy_preferences: selected,
    generation_preferences: store.outline.generation_preferences ? { ...store.outline.generation_preferences } : undefined }
  prompt.value = ''; error.value = ''; copied.value = false; loading.value = true
  summary.value = `${selected.style} · ${selected.structure} · ${selected.length}`
  mounted.value = true
  await nextTick()
  dialog.value?.showModal()
  try {
    const { data } = await axios.post(`${API_BASE_URL}/content/preview`, {
      ...input, copy_preferences: resolveCopyPreferences(selected),
    })
    if (ticket !== version || token !== getToken()) return
    prompt.value = data.prompt
    summary.value += ` · 受众：${data.audience.audience === '自定义' ? data.audience.audience_detail : data.audience.audience}`
  } catch {
    if (ticket === version && token === getToken()) error.value = '预览加载失败，请检查页面内容或网络后重试。'
  } finally { if (ticket === version) loading.value = false }
}
async function copy() {
  try { await navigator.clipboard.writeText(prompt.value); copied.value = true }
  catch {
    text.value?.focus(); text.value?.select()
    copied.value = document.execCommand('copy')
    if (!copied.value) error.value = '未能复制，文本已选中。'
  }
}
onBeforeUnmount(() => { version++ })
watch(() => session.revision, close)
</script>

<template>
  <fieldset :disabled="busy">
    <template v-for="group in groups" :key="group.key">
      <label :for="`copy-${group.key}`">{{ group.label }} <HelpTip :text="group.key === 'emoji_level' ? '无：普通编号；克制：少量相关表情和符号；丰富：搭配主题表情、圈号编号、勾选与箭头。严肃主题允许中性编号和提示符号，避免搞笑或夸张表情。' : group.key === 'style' ? '决定文案的整体表达感觉和措辞。' : group.key === 'structure' ? '决定正文如何组织信息，例如清单、步骤或问答。' : '控制文案篇幅，内容越多越详细，但也会增加阅读负担。'" /></label>
      <select :id="`copy-${group.key}`" :value="group.key !== 'structure' && isAutomaticCopy(store.outline.copy_preferences, group.key) ? '__auto__' : options[group.key]" @change="update(group.key, $event)">
      <option v-if="group.key !== 'structure'" value="__auto__">{{ automaticLabel(group.key, group.items) }}</option>
      <option v-for="item in group.items.filter(item => group.key === 'structure' || !('legacyValue' in item && item.legacyValue === '自动'))" :key="item.id" :value="item.value" :disabled="('unavailable' in item && Boolean(item.unavailable))">{{ item.name }}</option>
      </select>
      <p v-if="!group.items.length || group.items.some(item => 'unavailable' in item && item.unavailable)" role="alert">所选提示词不可用，请重新选择。</p>
    </template>
  </fieldset>
  <p v-if="catalog.error.value" role="status">{{ catalog.error.value }} <button type="button" :disabled="busy || catalog.loading.value" @click="catalog.refresh">刷新目录</button></p>
  <button class="btn btn-secondary preview" :disabled="busy || !store.outline.pages.length" @click="open"><FileSearch :size="16" />预览完整文案提示词</button>
  <Teleport v-if="mounted" to="body">
    <dialog ref="dialog" aria-labelledby="copy-preview-title" @cancel="close">
      <header><h2 id="copy-preview-title">文案提示词 · 预览</h2><button class="icon-button" aria-label="关闭文案预览" @click="close"><X :size="20" /></button></header>
      <p>{{ summary }}</p>
      <p v-if="loading" role="status">正在加载…</p>
      <p v-if="error" role="alert">{{ error }} <button class="btn btn-secondary" @click="open">重试</button></p>
      <template v-if="prompt">
        <textarea ref="text" readonly :value="prompt" aria-label="完整文案生成提示词"></textarea>
        <footer><span>{{ prompt.length }} 字符</span><button class="btn btn-primary" @click="copy"><Copy :size="16" />{{ copied ? '已复制' : '复制完整提示词' }}</button></footer>
      </template>
    </dialog>
  </Teleport>
</template>

<style scoped>
fieldset { border:0; padding:0; min-width:0; }
label { display:block; margin:14px 0 7px; font-size:13px; }
select { width:100%; min-height:44px; padding:8px; border:1px solid var(--border-color); border-radius:4px; background:white; }
.preview { width:100%; margin-top:18px; font-size:13px; }
dialog { width:min(860px,calc(100% - 24px)); max-height:calc(100dvh - 32px); overflow:auto; margin:auto; padding:20px; border:1px solid var(--border-color); border-radius:8px; }
dialog::backdrop { background:#0006; }
header,footer { display:flex; align-items:center; justify-content:space-between; gap:12px; }
h2 { font-size:18px; margin:0; }
p { margin:14px 0; overflow-wrap:anywhere; }
textarea { width:100%; height:48dvh; padding:12px; border:1px solid var(--border-color); line-height:1.65; resize:vertical; }
footer { margin-top:14px; }
@media(max-width:700px) { dialog { padding:14px; } select,textarea { font-size:16px; } h2 { font-size:16px; } }
</style>
