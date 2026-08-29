<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="image-viewer"
      @click="$emit('close')"
      @wheel.prevent="onWheel"
    >
      <button class="viewer-close" type="button" @click.stop="$emit('close')">×</button>
      <img
        :src="fullSrc"
        :alt="alt"
        class="viewer-img"
        :style="{ transform: `scale(${scale})` }"
        @click.stop
      />
      <div class="viewer-hint">滚轮缩放 · 点击背景关闭</div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { getToken } from '../../api/token'

const props = defineProps<{
  visible: boolean
  src: string
  alt?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const scale = ref(1)

const fullSrc = computed(() => {
  if (!props.src) return ''
  const baseUrl = props.src.split('?')[0]
  const token = getToken()
  return `${baseUrl}?thumbnail=false${token ? `&token=${encodeURIComponent(token)}` : ''}`
})

const onWheel = (e: WheelEvent) => {
  const delta = e.deltaY > 0 ? -0.15 : 0.15
  scale.value = Math.max(0.3, Math.min(5, scale.value + delta))
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') emit('close')
}

watch(
  () => props.visible,
  (v) => {
    scale.value = 1
    if (v) document.addEventListener('keydown', onKeydown)
    else document.removeEventListener('keydown', onKeydown)
  },
)

onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.image-viewer {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.92);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  cursor: zoom-out;
}
.viewer-img {
  max-width: 95vw;
  max-height: 95vh;
  object-fit: contain;
  transition: transform 0.15s ease;
  user-select: none;
  pointer-events: none;
}
.viewer-close {
  position: fixed;
  top: 16px;
  right: 24px;
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.15);
  border: none;
  border-radius: 50%;
  color: #fff;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.2s;
}
.viewer-close:hover {
  background: rgba(255, 255, 255, 0.3);
}
.viewer-hint {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  pointer-events: none;
}
</style>