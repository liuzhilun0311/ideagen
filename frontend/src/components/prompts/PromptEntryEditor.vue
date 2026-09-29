<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Save, X, RefreshCw } from 'lucide-vue-next'
import type { PromptDraft, PromptUser } from '../../api/promptCenter'

const props = defineProps<{
  draft: PromptDraft; readonly: boolean; admin: boolean; busy: boolean
  users: PromptUser[]; usersLoading: boolean; usersError: string
}>()
const emit = defineEmits<{
  change: [draft: PromptDraft]; save: []; close: []; users: []
}>()
const userSearch = ref('')
const nameInput = ref<HTMLInputElement>()
const matchingUsers = computed(() => props.users.filter(user => user.username.toLowerCase().includes(userSearch.value.toLowerCase())))
const base = computed(() => props.draft.category === 'base')
const imageStyle = computed(() => props.draft.module === 'image' && props.draft.category === 'style')
function set<K extends keyof PromptDraft>(key: K, value: PromptDraft[K]) {
  emit('change', { ...props.draft, [key]: value })
}
function metadata(key: string, value: string) { set('metadata', { ...props.draft.metadata, [key]: value }) }
function userToggle(id: string, checked: boolean) {
  set('allowed_users', checked ? [...new Set([...props.draft.allowed_users, id])] : props.draft.allowed_users.filter(value => value !== id))
}
watch(() => props.draft.id, () => nameInput.value?.focus(), { flush: 'post' })
</script>

<template>
  <section class="entry-editor" aria-labelledby="entry-editor-title">
    <header>
      <h2 id="entry-editor-title">{{ readonly ? '查看条目' : draft.id ? '编辑条目' : '新增条目' }}</h2>
      <span v-if="draft.revision" class="muted">v{{ draft.revision }}</span>
      <button type="button" class="icon" title="关闭编辑器" aria-label="关闭编辑器" :disabled="busy" @click="emit('close')"><X :size="18" /></button>
    </header>
    <form @submit.prevent="emit('save')">
      <fieldset :disabled="readonly || busy">
        <label for="prompt-name">名称</label>
        <input id="prompt-name" ref="nameInput" :value="draft.name" maxlength="100" required :disabled="base" @input="set('name', ($event.target as HTMLInputElement).value)" />
        <label for="prompt-description">场景说明</label>
        <textarea id="prompt-description" :value="draft.description" rows="2" @input="set('description', ($event.target as HTMLTextAreaElement).value)" />
        <div class="label-row"><label for="prompt-content">指令正文</label><span class="muted">{{ draft.content.length }} 字符</span></div>
        <textarea id="prompt-content" class="content" :value="draft.content" rows="14" required spellcheck="false" @input="set('content', ($event.target as HTMLTextAreaElement).value)" />
        <template v-if="imageStyle">
          <div class="style-fields">
            <div><label for="prompt-color">颜色</label><input id="prompt-color" type="color" :value="draft.metadata.color || '#3b82f6'" @input="metadata('color', ($event.target as HTMLInputElement).value)" /></div>
            <div><label for="prompt-group">风格分组</label><input id="prompt-group" :value="draft.metadata.group || ''" @input="metadata('group', ($event.target as HTMLInputElement).value)" /></div>
          </div>
        </template>
        <template v-if="!base">
          <label class="check"><input type="checkbox" role="switch" :checked="draft.enabled" @change="set('enabled', ($event.target as HTMLInputElement).checked)" />启用</label>
          <label for="prompt-visibility">可用范围</label>
          <select id="prompt-visibility" :value="draft.visibility" @change="set('visibility', ($event.target as HTMLSelectElement).value as PromptDraft['visibility'])">
            <option value="private">仅自己</option><option value="selected">指定用户</option>
            <option v-if="admin || draft.visibility === 'public'" value="public" :disabled="!admin">所有用户</option>
          </select>
          <section v-if="draft.visibility === 'selected'" class="users" aria-label="配置用户">
            <div class="label-row"><label for="prompt-user-search">指定用户（{{ draft.allowed_users.length }}）</label>
              <button type="button" class="icon" title="刷新用户" aria-label="刷新用户" :disabled="usersLoading" @click="emit('users')"><RefreshCw :size="16" /></button>
            </div>
            <input id="prompt-user-search" v-model="userSearch" type="search" placeholder="搜索用户名" />
            <p v-if="usersError" role="alert">{{ usersError }}</p>
            <p v-else-if="usersLoading" role="status">加载用户中...</p>
            <div v-else class="user-list">
              <label v-for="user in matchingUsers" :key="user.id" class="check">
                <input type="checkbox" :checked="draft.allowed_users.includes(user.id)" @change="userToggle(user.id, ($event.target as HTMLInputElement).checked)" />{{ user.username }}
              </label>
              <span v-for="id in draft.allowed_users.filter(id => !users.some(user => user.id === id))" :key="id" class="check">
                <input type="checkbox" :checked="true" :aria-label="`移除用户 ${id}`" @change="userToggle(id, false)" />{{ id }}
              </span>
              <p v-if="!matchingUsers.length" class="muted">没有匹配的用户</p>
            </div>
          </section>
        </template>
      </fieldset>
      <footer>
        <button v-if="!readonly" type="submit" class="primary" :disabled="busy"><Save :size="16" />{{ busy ? '保存中...' : '保存' }}</button>
        <button type="button" :disabled="busy" @click="emit('close')">{{ readonly ? '关闭' : '取消' }}</button>
        <span v-if="readonly" class="muted">{{ base ? '基础规则仅管理员可编辑' : '共享条目 · 只读' }}</span>
      </footer>
    </form>
  </section>
</template>

<style scoped>
.entry-editor { min-width:0; border-left:1px solid var(--border-color, #ddd); padding-left:24px; }
header, .label-row, footer, .style-fields { display:flex; align-items:center; gap:12px; }
header { margin-bottom:16px; } h2 { font-size:18px; } header .icon { margin-left:auto; }
fieldset { border:0; padding:0; min-width:0; } label { display:block; font-size:14px; font-weight:600; margin:12px 0 6px; }
input:not([type=checkbox]):not([type=color]), textarea, select { width:100%; min-width:0; border:1px solid #bdc5cc; border-radius:4px; padding:8px 10px; background:white; color:#20272d; }
textarea { resize:vertical; line-height:1.6; } .content { font-family:ui-monospace,monospace; font-size:14px; }
.label-row { justify-content:space-between; } .muted { font-size:13px; color:#59636b; } .style-fields > div:last-child { flex:1; min-width:0; }
input[type=color] { width:48px; height:38px; padding:2px; border:1px solid #bdc5cc; background:white; }
.check { display:flex; align-items:center; gap:10px; min-height:36px; overflow-wrap:anywhere; font-weight:400; }
.check input { flex-shrink:0; } .user-list { max-height:220px; overflow:auto; } footer { margin-top:20px; flex-wrap:wrap; }
button { display:inline-flex; align-items:center; justify-content:center; gap:6px; min-height:36px; border:1px solid #bdc5cc; border-radius:4px; background:white; padding:6px 12px; cursor:pointer; }
button.icon { width:36px; padding:0; flex-shrink:0; } button.primary { background:#176b55; color:white; border-color:#176b55; }
button:disabled { opacity:.5; cursor:default; } :disabled { cursor:default; } button:hover:not(:disabled) { filter:brightness(.95); }
@media(max-width:1000px) { .entry-editor { border-left:0; border-top:2px solid #176b55; padding:20px 0 0; } }
@media(max-width:700px) { button, button.icon, .check { min-height:44px; } button.icon { width:44px; } input, select, textarea, .content { font-size:16px; } }
</style>
