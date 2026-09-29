<script setup lang="ts">
import { RotateCcw, X } from 'lucide-vue-next'
import type { PromptEntry, PromptVersion } from '../../api/promptCenter'
defineProps<{ entry: PromptEntry; versions: PromptVersion[]; busy: boolean; loading: boolean }>()
const emit = defineEmits<{ restore: [version?: number]; close: [] }>()
</script>

<template>
  <section class="history" aria-labelledby="prompt-history-title">
    <header><h2 id="prompt-history-title">{{ entry.name }} · 版本记录</h2>
      <button class="icon" type="button" title="关闭版本记录" aria-label="关闭版本记录" :disabled="busy" @click="emit('close')"><X :size="18" /></button>
    </header>
    <p class="muted">当前版本 v{{ entry.revision }}</p>
    <button v-if="entry.builtin" type="button" :disabled="busy" @click="emit('restore')"><RotateCcw :size="16" />恢复默认</button>
    <p v-if="loading" role="status">加载版本中...</p>
    <p v-else-if="!versions.length" class="muted">暂无版本记录</p>
    <article v-for="version in versions" :key="version.revision">
      <div class="version-head"><strong>v{{ version.revision }}</strong><span>{{ version.actor_name || '未记录操作者' }}</span><time>{{ version.created_at || '' }}</time></div>
      <details><summary>{{ version.name || version.snapshot?.name || '查看内容' }}</summary><pre>{{ version.content ?? version.snapshot?.content ?? '未记录正文' }}</pre></details>
      <button type="button" :disabled="busy || version.revision === entry.revision" :aria-label="`恢复版本 ${version.revision}`" @click="emit('restore', version.revision)"><RotateCcw :size="16" />恢复此版本</button>
    </article>
  </section>
</template>

<style scoped>
.history { min-width:0; border-left:1px solid var(--border-color, #ddd); padding-left:24px; }
header, .version-head { display:flex; align-items:center; gap:12px; flex-wrap:wrap; } header { justify-content:space-between; margin-bottom:8px; }
h2 { font-size:18px; overflow-wrap:anywhere; } .muted, time { color:#59636b; font-size:13px; } .muted { margin-bottom:12px; }
article { border-top:1px solid #dce0e3; padding:16px 0; margin-top:16px; } details { margin:10px 0; } summary { cursor:pointer; overflow-wrap:anywhere; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font:14px/1.6 ui-monospace,monospace; max-height:320px; overflow:auto; margin-top:8px; }
button { display:inline-flex; align-items:center; justify-content:center; gap:6px; border:1px solid #bdc5cc; border-radius:4px; background:white; min-height:36px; padding:6px 12px; cursor:pointer; }
button:disabled { opacity:.5; cursor:default; } .icon { width:36px; padding:0; flex-shrink:0; }
@media(max-width:1000px) { .history { border-left:0; border-top:2px solid #176b55; padding:20px 0 0; } }
@media(max-width:700px) { button { min-height:44px; } .icon { width:44px; } }
</style>
