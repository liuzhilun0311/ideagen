<script setup lang="ts">
import { computed } from 'vue'
import { useGeneratorStore } from '../../stores/generator'
import { effectiveStyle, availableImageStyles, imageStyleChanged } from '../../features/styles/catalog'
import StyleSelect from './StyleSelect.vue'
import PaletteSelect from './PaletteSelect.vue'

defineProps<{ disabled?: boolean; id?: string }>()
const store = useGeneratorStore()
const selected = computed(() => {
  const preset = effectiveStyle(store.imageStyle).preset
  return availableImageStyles().find(style => style.id === preset || style.catalogId === preset)
})
const changed = computed(() => store.images.length > 0 && imageStyleChanged(store.imageStyle))
</script>

<template>
  <section class="style-picker" aria-label="图片风格">
    <StyleSelect :id="`${id || 'image'}-style`" v-model="store.imageStyle.preset" label="图片风格"
      :disabled="disabled" :recommendation="store.imageStyle.recommendation" />
    <PaletteSelect v-model="store.imageStyle.palette" :disabled="disabled" />
    <p v-if="['auto', 'image.style.auto'].includes(store.imageStyle.preset) && store.outline.pages.length">本次生效：{{ selected?.name || '暂无可用风格' }}</p>
    <p v-if="changed" role="status">图片风格已变化，已有图片保持不变。</p>
  </section>
</template>

<style scoped>
.style-picker { display:grid; gap:9px; padding-block:16px; min-width:0; border-top:1px solid var(--border-color); }
summary { min-height:36px; padding:8px 0; cursor:pointer; font-size:13px; }
label { display:flex; align-items:center; gap:7px; font-size:13px; }
.field, textarea { width:100%; min-width:0; font:inherit; font-size:14px; }
textarea { resize:vertical; padding:10px; border:1px solid var(--border-color); border-radius:6px; line-height:1.6; background:var(--bg-card, #fff); }
.style-description { display:flex; align-items:center; gap:7px; color:var(--text-sub); font-size:12px; }
.style-description span { width:12px; height:12px; border-radius:2px; flex-shrink:0; }
.style-preview { margin:0; max-width:360px; }
.style-preview img { width:100%; height:auto; aspect-ratio:3 / 2; display:block; object-fit:cover; border:1px solid var(--border-color); border-radius:6px; }
.style-preview figcaption { color:var(--text-sub); font-size:11px; margin-top:4px; }
p { color:var(--text-sub); font-size:13px; line-height:1.6; margin:0; }
@media(max-width:700px) { .field, textarea { font-size:16px; } }
</style>
