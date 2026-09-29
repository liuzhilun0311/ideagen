<script setup lang="ts">
import { computed } from 'vue'
import { palettes, paletteColors, type PaletteChoice } from '../../features/styles/palette'
const props = defineProps<{ modelValue?: PaletteChoice; disabled?: boolean; label?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: PaletteChoice] }>()
const current = computed(() => props.modelValue || { mode: 'auto' })
const colors = computed(() => paletteColors(current.value))
const paletteName = computed(() => palettes.find(item => item.id === (current.value.mode === 'auto'
  ? current.value.recommendation : current.value.mode))?.name || '')
function choose(event: Event) {
  emit('update:modelValue', { ...current.value, mode: (event.target as HTMLSelectElement).value })
}
function color(key: 'primary' | 'background' | 'accent', event: Event) {
  emit('update:modelValue', { ...current.value, [key]: (event.target as HTMLInputElement).value })
}
</script>
<template>
  <div class="palette-control">
    <label>{{ label || '配色' }}
      <select :value="current.mode" :disabled="disabled" @change="choose">
        <option value="auto">自动推荐</option>
        <option value="reference">参考图配色</option>
        <option v-for="item in palettes" :key="item.id" :value="item.id">{{ item.name }}</option>
        <option value="custom">自定义配色</option>
      </select>
    </label>
    <div v-if="current.mode === 'custom'" class="colors">
      <label v-for="[key, name] in [['primary', '主色'], ['background', '背景色'], ['accent', '强调色']]"
        :key="key">{{ name }}<input type="color" :aria-label="name" :disabled="disabled"
          :value="colors?.[key as 'primary' | 'background' | 'accent']"
          @input="color(key as 'primary' | 'background' | 'accent', $event)" /></label>
    </div>
    <div v-else-if="colors" class="swatches" :aria-label="paletteName"
      :title="[paletteName, current.mode === 'auto' ? current.reason : ''].filter(Boolean).join('：')">
      <span v-for="key in ['primary', 'background', 'accent'] as const" :key="key"
        :style="{ backgroundColor: colors[key] }" :title="colors[key]"></span>
      <small>{{ paletteName }}</small>
    </div>
  </div>
</template>
<style scoped>
.palette-control { display:grid; gap:6px; min-width:0; }
label { display:grid; gap:6px; font-size:13px; }
select { width:100%; min-width:0; min-height:44px; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-card); padding:8px; font:inherit; }
.colors,.swatches { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.colors input { width:42px; height:30px; padding:2px; border:1px solid var(--border-color); background:white; }
.swatches span { width:18px; height:18px; border:1px solid #bbb; border-radius:3px; }
small { color:var(--text-sub); }
</style>
