<script setup lang="ts">
import { computed, nextTick, onDeactivated, ref, useId } from 'vue'
import { HelpCircle, X } from 'lucide-vue-next'
import { generationGuides, type GenerationGuideKind } from '../../features/generationGuides'

const props = defineProps<{ kind: GenerationGuideKind }>()
const guide = computed(() => generationGuides[props.kind])
const dialog = ref<HTMLDialogElement>()
const trigger = ref<HTMLButtonElement>()
const titleId = useId()
const opened = ref(false)
const mounted = ref(false)
async function open() {
  mounted.value = true
  await nextTick()
  dialog.value?.showModal()
  opened.value = true
}
function close() { dialog.value?.close() }
function closed() {
  opened.value = false
  trigger.value?.focus()
}
onDeactivated(close)
</script>

<template>
  <button ref="trigger" type="button" class="guide-trigger" :title="guide.title"
    :aria-label="guide.title" aria-haspopup="dialog" :aria-expanded="opened" @click.stop="open">
    <HelpCircle :size="17" aria-hidden="true" />
  </button>
  <Teleport v-if="mounted" to="body">
  <dialog ref="dialog" class="generation-guide" :aria-labelledby="titleId" @close="closed">
    <header>
      <h2 :id="titleId">{{ guide.title }}</h2>
      <button type="button" class="icon-button" :title="`关闭${guide.title}`" :aria-label="`关闭${guide.title}`"
        autofocus @click="close"><X :size="20" aria-hidden="true" /></button>
    </header>
    <div class="guide-content">
      <section>
        <h3>内容由什么组成</h3>
        <p>{{ guide.composition }}</p>
      </section>
      <section>
        <h3>各项设置影响什么</h3>
        <dl>
          <div v-for="factor in guide.factors" :key="factor.name">
            <dt>{{ factor.name }}</dt><dd>{{ factor.effect }}</dd>
          </div>
        </dl>
      </section>
      <section><h3>举个例子</h3><p>{{ guide.example }}</p></section>
      <section><h3>什么时候生效</h3><ul><li v-for="rule in guide.rules" :key="rule">{{ rule }}</li></ul></section>
    </div>
  </dialog>
  </Teleport>
</template>

<style scoped>
.guide-trigger { display:inline-grid; place-items:center; vertical-align:middle; flex:0 0 28px; width:28px; height:28px; padding:0; border:0; border-radius:4px; background:transparent; color:var(--text-sub,#667085); cursor:pointer; }
.guide-trigger:hover { color:var(--primary,#315ee8); background:var(--primary-light,#edf3ff); }
.guide-trigger:focus-visible { outline:2px solid var(--primary,#315ee8); outline-offset:2px; }
.generation-guide { box-sizing:border-box; width:min(720px,calc(100% - 32px)); max-height:calc(100dvh - 32px); margin:auto; padding:0; overflow:auto; border:1px solid var(--border-color,#d9e0ea); border-radius:8px; background:var(--bg-card,#fff); color:var(--text-main,#252935); text-align:left; font-weight:400; }
.generation-guide::backdrop { background:#151d3266; }
.generation-guide header { position:sticky; top:0; z-index:1; display:flex; align-items:center; justify-content:space-between; gap:16px; padding:12px 24px; border-bottom:1px solid var(--border-color,#d9e0ea); background:var(--bg-card,#fff); }
.generation-guide h2 { margin:0; font-size:18px; line-height:1.4; }
.guide-content { padding:20px 24px 24px; font-size:14px; line-height:1.75; overflow-wrap:anywhere; }
.guide-content section + section { margin-top:24px; }
.guide-content h3 { margin:0 0 10px; font-size:15px; }
.guide-content p,.guide-content dl { margin:0; }
.guide-content dl > div { display:grid; grid-template-columns:150px minmax(0,1fr); gap:16px; padding:12px 0; border-bottom:1px solid var(--border-color,#d9e0ea); }
.guide-content dt { font-weight:600; }
.guide-content dd { margin:0; }
.guide-content ul { margin:0; padding-left:20px; }
.guide-content li + li { margin-top:8px; }
@media(max-width:700px) {
  .guide-trigger { width:44px; height:44px; flex-basis:44px; }
  .generation-guide header { padding:10px 16px; }
  .guide-content { padding:16px; }
  .guide-content dl > div { grid-template-columns:minmax(0,1fr); gap:4px; }
}
</style>
