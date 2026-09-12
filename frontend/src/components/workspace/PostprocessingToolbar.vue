<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RotateCw, WandSparkles } from 'lucide-vue-next'
import type { ProcessingPage, ProcessingState, ProcessingStrength } from '../../api/postprocessing'

const props = defineProps<{
  pages: ProcessingPage[]
  preferences?: ProcessingState['preferences']
  submitting: boolean
  savingPreferences: boolean
}>()
const emit = defineEmits<{
  process: [indices: number[], strength: ProcessingStrength, force: boolean]
  preferences: [automatic: boolean, strength: ProcessingStrength]
}>()
const strength = ref<ProcessingStrength>('light')
const automatic = ref(true)
watch(() => props.preferences, value => {
  if (!value || props.savingPreferences) return
  automatic.value = value.automatic
  strength.value = value.strength
}, { immediate: true })
watch(() => props.savingPreferences, (saving, previous) => {
  if (previous && !saving) {
    automatic.value = props.preferences?.automatic ?? true
    strength.value = props.preferences?.strength || 'light'
  }
})
const isRunning = (page: ProcessingPage) => ['queued', 'processing'].includes(page.status)
const pending = computed(() => props.pages.filter(page => !page.processed_url && !isRunning(page)))
const failed = computed(() => props.pages.filter(page => page.status === 'error'))
function process(force = false, failuresOnly = false) {
  const selection = failuresOnly ? failed.value : force ? props.pages.filter(page => !isRunning(page)) : pending.value
  const indices = selection.map(page => page.index)
  const selectedStrength = strength.value
  const replaceExisting = force || selection.some(page => !!page.processed_url)
  if (!indices.length || props.submitting || props.savingPreferences) return
  if (replaceExisting && !window.confirm(`${failuresOnly ? '重试失败的' : '按此强度重新处理全部'} ${indices.length} 张图片？现有处理图将在新结果成功后替换。`)) return
  emit('process', indices, selectedStrength, replaceExisting)
}
function savePreferences() {
  emit('preferences', automatic.value, strength.value)
}
</script>

<template>
  <section class="processing-toolbar" aria-label="整套图片后处理">
    <div class="batch-controls">
      <label>去AI化强度
        <select v-model="strength" aria-label="去AI化强度" :disabled="savingPreferences" @change="savePreferences">
          <option value="light">轻度</option><option value="medium">中度</option><option value="heavy">重度</option>
        </select>
      </label>
      <button class="btn btn-secondary" :disabled="submitting || savingPreferences || !pending.length" @click="process()">
        <WandSparkles :size="16" />全部去AI化 {{ pending.length }} 张
      </button>
      <button class="btn btn-secondary" :disabled="submitting || savingPreferences || !pages.some(page => !isRunning(page))" @click="process(true)">
        <RotateCw :size="16" />重新去AI化 {{ pages.length }} 张
      </button>
      <button v-if="failed.length" class="btn btn-secondary" :disabled="submitting || savingPreferences" @click="process(false, true)">
        <RotateCw :size="16" />重试失败页 · {{ failed.length }}
      </button>
    </div>
    <div class="automatic-controls">
      <label class="automatic-toggle">
        自动去AI化
        <select v-model="automatic" :disabled="savingPreferences" aria-label="生成后自动去AI化" @change="savePreferences">
          <option :value="true">是</option>
          <option :value="false">否</option>
        </select>
      </label>
      <span v-if="savingPreferences" role="status">正在保存偏好</span>
    </div>
  </section>
</template>

<style scoped>
.processing-toolbar { padding:0; margin:0; font-size:13px; min-width:0; }
.batch-controls,.automatic-controls { display:flex; align-items:center; flex-wrap:wrap; gap:10px 16px; }
label { display:flex; align-items:center; gap:8px; }
select { min-height:36px; border:1px solid var(--border-color); border-radius:5px; background:#fff; color:var(--text-main); padding:6px 26px 6px 8px; font:inherit; }
.btn { min-height:38px; height:auto; white-space:normal; font-size:13px; padding:8px 12px; }
.btn svg { flex-shrink:0; }
.processing-summary { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; color:var(--text-sub); line-height:1.7; }
.automatic-toggle select { min-height:30px; padding:4px 22px 4px 6px; }
.automatic-controls>span { color:var(--text-sub); }
@media(max-width:700px) { .batch-controls { align-items:stretch; } .batch-controls>.btn { flex:1 1 100%; } }
</style>
