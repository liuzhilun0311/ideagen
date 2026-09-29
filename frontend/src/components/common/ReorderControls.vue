<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { ArrowDown, ArrowUp, GripVertical } from 'lucide-vue-next'

const props = defineProps<{ id: string; index: number; total: number; disabled?: boolean }>()
const emit = defineEmits<{ move: [direction: -1 | 1]; drop: [targetId: string] }>()
const dragging = ref(false)
let handle: HTMLElement | null = null
let list: HTMLElement | null = null
let target: HTMLElement | null = null
let pointer: number | null = null
function clear() {
  target?.classList.remove('reorder-target')
  if (handle && pointer !== null && handle.hasPointerCapture?.(pointer)) handle.releasePointerCapture(pointer)
  handle = list = target = null
  pointer = null
  dragging.value = false
}
function start(event: PointerEvent) {
  if (props.disabled || event.button !== 0) return
  handle = event.currentTarget as HTMLElement
  list = handle.closest<HTMLElement>('[data-reorder-list]')
  if (!list) return
  event.preventDefault()
  pointer = event.pointerId
  handle.setPointerCapture(pointer)
  dragging.value = true
}
function drag(event: PointerEvent) {
  if (!dragging.value || event.pointerId !== pointer) return
  const hovered = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-reorder-id]') || null
  const eligible = hovered?.closest('[data-reorder-list]') === list ? hovered : null
  target?.classList.remove('reorder-target')
  target = eligible?.dataset.reorderId !== props.id ? eligible : null
  target?.classList.add('reorder-target')
  if (event.clientY < 70) window.scrollBy(0, -24)
  else if (event.clientY > window.innerHeight - 70) window.scrollBy(0, 24)
}
function end(event: PointerEvent) {
  if (event.pointerId !== pointer) return
  const destination = target?.dataset.reorderId
  clear()
  if (!props.disabled && destination) emit('drop', destination)
}
onBeforeUnmount(clear)
</script>

<template>
  <div class="reorder-controls">
    <button type="button" class="reorder-handle" :class="{ dragging }" :disabled="disabled" title="拖动排序" aria-label="拖动排序"
      @pointerdown="start" @pointermove="drag" @pointerup="end" @pointercancel="clear" @lostpointercapture="clear">
      <GripVertical :size="18" />
    </button>
    <button type="button" :disabled="disabled || index === 0" title="上移" aria-label="上移" @click="emit('move', -1)"><ArrowUp :size="15" /></button>
    <button type="button" :disabled="disabled || index === total - 1" title="下移" aria-label="下移" @click="emit('move', 1)"><ArrowDown :size="15" /></button>
  </div>
</template>

<style scoped>
.reorder-controls { display:inline-flex; align-items:center; gap:2px; flex-shrink:0; }
button { display:inline-flex; align-items:center; justify-content:center; width:30px; height:36px; padding:0; background:transparent; border:0; color:#657183; border-radius:4px; }
button:hover:not(:disabled) { background:#e9eff5; color:#243c60; }
button:disabled { opacity:.35; cursor:default; }
.reorder-handle { touch-action:none; cursor:grab; }
.reorder-handle.dragging { cursor:grabbing; background:#e9eff5; }
button:focus-visible { outline:2px solid #315ee8; outline-offset:1px; }
@media(max-width:700px) { button { width:44px; height:44px; } }
:global(.reorder-target) { outline:2px solid #315ee8; outline-offset:-2px; }
</style>
