<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { Check, Copy, FileText, Hash, List } from 'lucide-vue-next'
import { useGeneratorStore } from '../../stores/generator'
import { selectedTitle, selectedTitleIndex } from '../../utils/publicationContent'

const props = defineProps<{ selectedOnly?: boolean }>()
const store = useGeneratorStore()
const content = computed(() => {
  if (!props.selectedOnly) return store.content
  return {
    ...store.content,
    titles: store.content.titles.length
      ? [selectedTitle(store.content.titles, store.content.selectedTitleIndex)] : [],
    selectedTitleIndex: 0,
  }
})
const hasContent = computed(() => content.value.titles.length || content.value.copywriting || content.value.tags.length)
const copiedKey = ref('')
const copyError = ref('')
const copyMessage = ref('')
const copying = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
onUnmounted(() => clearTimeout(timer))

async function copyText(text: string, key: string, label: string) {
  if (!text || copying.value) return
  copying.value = true
  copiedKey.value = ''
  copyError.value = ''
  copyMessage.value = ''
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
    copiedKey.value = key
    copyMessage.value = `${label}已复制`
    clearTimeout(timer)
    timer = setTimeout(() => { copiedKey.value = ''; copyMessage.value = '' }, 2000)
  } catch {
    copyError.value = `${label}复制失败，剪贴板不可用或未获授权。`
  } finally {
    copying.value = false
  }
}
const tagsText = computed(() => content.value.tags.map(t => `#${t}`).join(' '))
</script>

<template>
  <div class="content-display">
    <slot name="toolbar" />
    <p v-if="content.status === 'generating'" class="content-status" role="status">正在生成标题、文案和标签…</p>
    <p v-if="content.status === 'error'" class="content-error" role="alert">{{ content.error || '文案生成失败' }}</p>
    <p v-if="!hasContent && content.status !== 'generating'" class="content-status">暂无标题、文案和标签</p>
    <p v-if="copyError" class="content-error" role="alert">{{ copyError }}</p>
    <p class="copy-status" role="status" aria-live="polite">{{ copyMessage }}</p>

    <div v-if="hasContent" class="content-sections">
      <section class="content-section" aria-label="标题">
        <header>
          <h2><List :size="20" aria-hidden="true" />标题</h2>
          <button type="button" class="icon-button" :title="selectedOnly ? '复制标题' : '复制全部标题'" :aria-label="selectedOnly ? '复制标题' : '复制全部标题'" :disabled="copying || !content.titles.length" @click="copyText(content.titles.join('\n'), 'titles', '标题')">
            <Check v-if="copiedKey === 'titles'" :size="18" aria-hidden="true" /><Copy v-else :size="18" aria-hidden="true" />
          </button>
        </header>
        <p v-if="!content.titles.length" class="muted">暂无标题</p>
        <ol v-else class="titles-list">
          <li v-for="(title, index) in content.titles" :key="index">
            <span class="title-number">{{ index + 1 }}</span>
            <span class="title-text">{{ title }}<small v-if="index === selectedTitleIndex(content.titles, content.selectedTitleIndex)" class="adopted-title">已选</small></span>
            <button type="button" class="icon-button" :title="`复制标题 ${index + 1}`" :aria-label="`复制标题 ${index + 1}`" :disabled="copying || !title" @click="copyText(title, `title-${index}`, `标题 ${index + 1}`)">
              <Check v-if="copiedKey === `title-${index}`" :size="18" aria-hidden="true" /><Copy v-else :size="18" aria-hidden="true" />
            </button>
          </li>
        </ol>
      </section>

      <section class="content-section" aria-label="文案">
        <header>
          <h2><FileText :size="20" aria-hidden="true" />文案</h2>
          <button type="button" class="icon-button" title="复制文案" aria-label="复制文案" :disabled="copying || !content.copywriting" @click="copyText(content.copywriting, 'copywriting', '文案')">
            <Check v-if="copiedKey === 'copywriting'" :size="18" aria-hidden="true" /><Copy v-else :size="18" aria-hidden="true" />
          </button>
        </header>
        <p class="copywriting" :class="{ muted: !content.copywriting }">{{ content.copywriting || '暂无文案' }}</p>
      </section>

      <section class="content-section" aria-label="标签">
        <header>
          <h2><Hash :size="20" aria-hidden="true" />标签</h2>
          <button type="button" class="icon-button" title="复制全部标签" aria-label="复制全部标签" :disabled="copying || !content.tags.length" @click="copyText(tagsText, 'tags', '标签')">
            <Check v-if="copiedKey === 'tags'" :size="18" aria-hidden="true" /><Copy v-else :size="18" aria-hidden="true" />
          </button>
        </header>
        <p v-if="!content.tags.length" class="muted">暂无标签</p>
        <ul v-else class="tags-list">
          <li v-for="(tag, index) in content.tags" :key="index">
            <span>#{{ tag }}</span>
            <button type="button" class="icon-button" :title="`复制标签 ${tag}`" :aria-label="`复制标签 ${tag}`" :disabled="copying || !tag" @click="copyText(`#${tag}`, `tag-${index}`, '标签')">
              <Check v-if="copiedKey === `tag-${index}`" :size="18" aria-hidden="true" /><Copy v-else :size="18" aria-hidden="true" />
            </button>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.content-display { min-width: 0; padding: 0; color: #252935; overflow-wrap: anywhere; }
.content-section { padding: 24px 0; border-top: 1px solid #dfe2e8; min-width: 0; }
header, h2 { display: flex; align-items: center; gap: 10px; }
header { justify-content: space-between; margin-bottom: 16px; }
h2 { font-size: 18px; line-height: 1.4; margin: 0; }
h2 svg { color: #606674; }
p { font-size: 16px; line-height: 1.8; margin: 0; }
.content-status, .content-error { margin: 16px 0; }
.muted, .content-status, .title-number { color: #606674; }
.content-error { color: #a82936; white-space: pre-wrap; }
.copy-status { color: #087967; }
.copy-status:empty { position: absolute; width: 1px; height: 1px; overflow: hidden; }
.titles-list, .tags-list { list-style: none; padding: 0; margin: 0; }
.titles-list li { display: grid; grid-template-columns: 24px minmax(0, 1fr) 44px; gap: 10px; align-items: start; padding: 10px 0; }
.title-number, .title-text { font-size: 16px; line-height: 1.75; padding-top: 8px; }
.copywriting { white-space: pre-wrap; }
.adopted-title { color:#087967; font-size:12px; margin-left:8px; white-space:nowrap; }
.tags-list { display: flex; flex-wrap: wrap; gap: 8px 24px; }
.tags-list li { display: flex; align-items: center; gap: 8px; max-width: 100%; min-width: 0; color: #315ee8; font-size: 16px; line-height: 1.65; }
.tags-list li > span { min-width: 0; overflow-wrap: anywhere; }
.icon-button { display: inline-flex; justify-content: center; align-items: center; width: 44px; height: 44px; flex: 0 0 44px; }
button:focus-visible { outline: 3px solid #315ee8; outline-offset: 3px; }
button:disabled { cursor: not-allowed; opacity: .55; }
@media (max-width: 700px) {
  .content-section { padding: 20px 0; }
  .titles-list li { gap: 8px; }
}
</style>
