<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Save, X } from 'lucide-vue-next'
import { useGeneratorStore } from '../../stores/generator'
import { useStudioSession } from '../../stores/studioSession'
import { useDraftSave } from '../../composables/useDraftSave'

const store = useGeneratorStore()
const session = useStudioSession()
const router = useRouter()
const saver = useDraftSave()
const dialog = ref<HTMLDialogElement>()
const trigger = ref<HTMLButtonElement>()
const saving = ref(false)
const error = ref('')
const titleId = useId()
const canSave = computed(() => !!store.topic.trim() && !!store.outline.pages.length)
const hasDraft = computed(() => !!(
  store.topic.trim() || store.referenceContent.trim() || store.userImages.length
  || store.outline.pages.length || store.images.length || store.content.copywriting
  || store.content.titles.length || store.content.tags.length || store.recordId
))

function close() {
  if (saving.value) return
  dialog.value?.close()
  trigger.value?.focus()
}

async function replace() {
  if (!session.replaceDraft()) return
  store.reset()
  store.setEntrySource('home')
  store.saveToStorage()
  close()
  await router.push('/')
}

function open() {
  if (session.busy) return
  error.value = ''
  if (!hasDraft.value) { void replace(); return }
  dialog.value?.showModal()
}

async function saveAndNew() {
  if (session.busy || saving.value || !canSave.value) return
  saving.value = true
  session.draftSaving = true
  let success = false
  try {
    success = await saver.save()
    if (!success) error.value = saver.error.value?.detail || '保存失败，当前创作已保留。'
  } finally {
    saving.value = false
    session.draftSaving = false
  }
  if (success) await replace()
}
</script>

<template>
  <button ref="trigger" class="icon-button" type="button" title="新建创作" aria-label="新建创作"
    :disabled="session.busy" @click="open"><Plus :size="18" /></button>
  <dialog ref="dialog" class="new-creation-dialog" :aria-labelledby="titleId"
    @cancel="saving && $event.preventDefault()">
    <header>
      <h2 :id="titleId">开始新创作？</h2>
      <button type="button" class="icon-button" title="关闭" aria-label="关闭新建确认"
        :disabled="saving" @click="close"><X :size="18" /></button>
    </header>
    <p>新建将清空当前工作台。已保存的作品可在作品列表中重新打开。</p>
    <p v-if="!canSave">当前尚无完整大纲，暂不能保存为作品；取消可继续编辑。</p>
    <p v-if="error" class="save-error" role="alert">{{ error }}</p>
    <footer>
      <button type="button" class="btn btn-secondary" autofocus :disabled="saving" @click="close">取消</button>
      <button type="button" class="btn btn-secondary" :disabled="session.busy" @click="replace">放弃并新建</button>
      <button type="button" class="btn btn-primary" :disabled="session.busy || !canSave" @click="saveAndNew">
        <Save :size="16" />{{ saving ? '正在保存' : '保存并新建' }}
      </button>
    </footer>
  </dialog>
</template>

<style scoped>
.new-creation-dialog { width:min(480px,calc(100% - 32px)); max-height:calc(100dvh - 32px); overflow:auto; padding:24px; border:1px solid var(--border-color); border-radius:8px; color:var(--text-main); background:var(--bg-card); }
.new-creation-dialog::backdrop { background:#151d3266; }
header { display:flex; align-items:center; justify-content:space-between; gap:16px; }
h2 { margin:0; font-size:18px; }
p { font-size:14px; line-height:1.7; overflow-wrap:anywhere; }
footer { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; margin-top:24px; }
footer .btn { min-height:44px; }
.save-error { color:var(--danger, #b42318); }
</style>
