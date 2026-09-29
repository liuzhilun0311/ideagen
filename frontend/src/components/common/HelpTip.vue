<script setup lang="ts">
import { ref } from 'vue'
import { HelpCircle } from 'lucide-vue-next'
defineProps<{ text: string; label?: string }>()
const open = ref(false)
</script>
<template><span class="help-tip"><button type="button" class="help-button" :aria-label="label || '查看帮助'" :aria-expanded="open" @click.stop="open = !open"><HelpCircle :size="15" /></button><span v-if="open" class="help-popover" role="note">{{ text }}</span></span></template>
<style scoped>
.help-tip{position:relative;display:inline-flex;vertical-align:middle}.help-button{width:22px;height:22px;padding:0;border:0;border-radius:50%;background:transparent;color:var(--text-sub,#667085);cursor:pointer;display:grid;place-items:center}.help-button:hover,.help-button:focus-visible{color:var(--primary,#2f60e8);background:#edf3ff;outline:none}.help-popover{position:absolute;z-index:20;top:calc(100% + 7px);left:0;width:min(280px,calc(100vw - 40px));padding:10px 12px;border:1px solid var(--border-color,#d9e0ea);border-radius:6px;background:#fff;color:var(--text-main,#1f2937);box-shadow:0 5px 18px #172b4d22;font-size:12px;line-height:1.6;font-weight:400}
</style>
