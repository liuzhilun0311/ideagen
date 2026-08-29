<template>
  <div class="container">
    <div class="page-header">
      <div>
        <h1 class="page-title">提示词设计</h1>
      </div>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- 类型切换 -->
    <div class="kind-tabs">
      <button
        v-for="kind in kinds"
        :key="kind"
        class="kind-tab"
        :class="{ active: activeKind === kind }"
        @click="switchKind(kind)"
      >
        {{ kindLabels[kind] }}
      </button>
    </div>

    <!-- 新建按钮 -->
    <div class="toolbar">
      <button class="btn btn-primary btn-small" @click="startCreate">+ 新建提示词</button>
    </div>

    <!-- 编辑面板 -->
    <div v-if="editing" class="card editor-card">
      <div class="editor-head">
        <h3>{{ editing.isBase ? '编辑默认提示词' : (editing.originalName ? '编辑提示词' : '新建提示词') }}</h3>
        <button class="icon-btn" title="关闭" @click="editing = null">✕</button>
      </div>
      <div class="editor-body">
        <div class="field">
          <label>提示词名称</label>
          <input
            v-model="editing.name"
            class="input"
            type="text"
            maxlength="50"
            placeholder="给这个提示词起个名字，如：电商风格"
            :disabled="!!editing.isBase"
            :title="editing.isBase ? '系统默认提示词名称不可修改' : ''"
          />
          <span v-if="editing.isBase" class="base-editor-tip">系统默认提示词，修改内容后对所有用户生效</span>
        </div>
        <div class="field">
          <label>提示词内容</label>
          <textarea
            v-model="editing.content"
            class="textarea"
            rows="12"
            placeholder="输入完整提示词内容"
          ></textarea>
        </div>
        <div class="editor-actions">
          <button class="btn btn-purple btn-small" :disabled="saving" @click="save">
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button class="btn btn-ghost btn-small" @click="editing = null">取消</button>
        </div>
      </div>
    </div>

    <!-- 提示词列表 -->
    <div class="prompt-list">
      <div v-for="item in activePrompts" :key="item.name" class="card prompt-card">
        <div class="prompt-head">
          <span class="prompt-name">{{ item.name }}</span>
          <span v-if="item.is_base" class="base-badge">系统默认</span>
          <span v-else-if="item.is_shared" class="shared-badge">来自 {{ item.owner }}</span>
          <span v-else class="mine-badge">我的</span>
        </div>
        <p class="prompt-preview" :class="{ expanded: expandedName === item.name }">
          {{ item.content }}
        </p>
        <button
          v-if="item.content.length > 120 || expandedName === item.name"
          class="expand-btn"
          @click="toggleExpand(item.name)"
        >
          {{ expandedName === item.name ? '收起' : '展开全文' }}
        </button>

        <!-- 管理员：查看共享名单 -->
        <div v-if="isAdmin && item.is_shared" class="allowed-users">
          <span class="allowed-label">可用用户：</span>
          <span v-if="!item.allowed_users || item.allowed_users.length === 0" class="allowed-empty">仅拥有者（未共享）</span>
          <span v-for="u in item.allowed_users" :key="u" class="allowed-chip">{{ u }}</span>
        </div>

        <div v-if="item.is_base" class="prompt-actions">
          <template v-if="item.can_edit">
            <button class="btn btn-info btn-small" @click="startEdit(item)">编辑</button>
            <span class="base-tip">系统默认提示词，修改后对所有用户生效</span>
          </template>
          <span v-else class="base-tip">系统默认提示词，不可编辑</span>
        </div>
        <div v-else-if="item.can_edit" class="prompt-actions">
          <button class="btn btn-info btn-small" @click="startEdit(item)">编辑</button>
          <button v-if="isAdmin" class="btn btn-ghost btn-small" @click="openUsersModal(item)">配置用户</button>
          <button class="btn btn-danger btn-small" @click="remove(item)">删除</button>
        </div>
        <div v-else-if="isAdmin" class="prompt-actions">
          <button class="btn btn-ghost btn-small" @click="openUsersModal(item)">配置用户</button>
          <button class="btn btn-danger btn-small" @click="remove(item)">删除</button>
        </div>
        <div v-else class="prompt-actions base-actions">
          <span class="base-tip">共享提示词，仅拥有者可编辑</span>
        </div>
      </div>

      <div v-if="!loading && activePrompts.length === 0" class="empty-tip">
        该分类下还没有自定义提示词，点"新建提示词"开始创建。
      </div>
    </div>

    <!-- 配置用户弹窗 -->
    <div v-if="usersModalOpen" class="modal-overlay" @click.self="usersModalOpen = false">
      <div class="modal card">
        <div class="editor-head">
          <h3>配置可用用户 - {{ usersModalItem?.name }}</h3>
          <button class="icon-btn" title="关闭" @click="usersModalOpen = false">✕</button>
        </div>
        <div class="editor-body">
          <p class="modal-sub">
            勾选后，这些用户可在自己的提示词界面看到并使用该提示词。拥有者
            <strong>{{ usersModalItem?.owner }}</strong> 已默认勾选、始终可见。
          </p>
          <div class="user-check-list">
            <label v-for="u in adminUsers" :key="u.id" class="user-check">
              <input type="checkbox" :value="u.username" v-model="usersModalSelected" :disabled="u.username === usersModalItem?.owner" />
              {{ u.username }}
              <span v-if="u.id === usersModalItem?.owner_id" class="owner-flag">（拥有者，始终可见）</span>
            </label>
          </div>
          <div class="editor-actions">
            <button class="btn btn-purple btn-small" :disabled="savingUsers" @click="saveUsersModal">
              {{ savingUsers ? '保存中...' : '保存' }}
            </button>
            <button class="btn btn-ghost btn-small" @click="usersModalOpen = false">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  getPrompts,
  savePrompt,
  saveBasePrompt,
  deletePrompt,
  setPromptUsers,
  adminDeletePrompt,
  type PromptItem,
  type PromptKind
} from '../api'
import { listUsers } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const kinds: PromptKind[] = ['outline', 'content', 'image']

const kindLabels: Record<PromptKind, string> = {
  outline: '大纲提示词',
  content: '文案提示词',
  image: '图片提示词'
}

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

const prompts = ref<Record<PromptKind, PromptItem[]> | null>(null)
const activeKind = ref<PromptKind>('outline')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const expandedName = ref<string | null>(null)

const editing = ref<{ originalName: string; name: string; content: string; isBase?: boolean } | null>(null)

// 配置用户弹窗
const usersModalOpen = ref(false)
const usersModalItem = ref<PromptItem | null>(null)
const usersModalSelected = ref<string[]>([])
const adminUsers = ref<{ id: string; username: string }[]>([])
const savingUsers = ref(false)

const activePrompts = computed(() => prompts.value?.[activeKind.value] || [])

async function loadPrompts() {
  loading.value = true
  error.value = ''
  try {
    const res = await getPrompts()
    if (res.success && res.prompts) {
      prompts.value = res.prompts
    } else {
      error.value = '加载提示词失败'
    }
  } catch (e: any) {
    error.value = '加载提示词失败：' + (e?.message || '未知错误')
  } finally {
    loading.value = false
  }
}

function switchKind(kind: PromptKind) {
  activeKind.value = kind
  expandedName.value = null
}

function toggleExpand(name: string) {
  expandedName.value = expandedName.value === name ? null : name
}

function startCreate() {
  editing.value = { originalName: '', name: '', content: '' }
}

function startEdit(item: PromptItem) {
  editing.value = {
    originalName: item.name,
    name: item.name,
    content: item.content,
    isBase: !!item.is_base
  }
}

async function save() {
  if (!editing.value) return
  const { originalName, name, content, isBase } = editing.value
  if (!name.trim()) {
    alert('请填写提示词名称')
    return
  }
  if (!content.trim()) {
    alert('请填写提示词内容')
    return
  }

  saving.value = true
  error.value = ''
  try {
    let res: any
    if (isBase) {
      // 系统默认提示词：管理员直接保存默认内容（名称不可修改）
      res = await saveBasePrompt(activeKind.value, content)
    } else {
      // 重命名：先删旧的再存新的
      if (originalName && originalName !== name) {
        await deletePrompt(activeKind.value, originalName)
      }
      res = await savePrompt(activeKind.value, name.trim(), content)
    }
    if (!res?.success) {
      error.value = res?.error_message || '保存失败'
      return
    }
    editing.value = null
    await loadPrompts()
  } catch (e: any) {
    error.value = '保存失败：' + (e?.message || '未知错误')
  } finally {
    saving.value = false
  }
}

async function remove(item: PromptItem) {
  const target = item.is_shared ? `"${item.name}"（来自 ${item.owner}）` : `"${item.name}"`
  if (!confirm(`确定要删除提示词${target}吗？`)) return
  error.value = ''
  try {
    if (isAdmin.value && item.is_shared) {
      // 管理员删除他人提示词
      const res = await adminDeletePrompt(item.owner_id!, activeKind.value, item.name)
      if (!res?.success) {
        error.value = res?.error_message || '删除失败'
        return
      }
    } else {
      await deletePrompt(activeKind.value, item.name)
    }
    await loadPrompts()
  } catch (e: any) {
    error.value = '删除失败：' + (e?.message || '未知错误')
  }
}

// ==================== 管理员：配置用户名单 ====================

async function openUsersModal(item: PromptItem) {
  usersModalItem.value = item
  // 拥有者（创建者）默认打勾、始终可见
  const selected = new Set<string>([...(item.allowed_users || [])])
  if (item.owner) selected.add(item.owner)
  usersModalSelected.value = [...selected]
  usersModalOpen.value = true
  if (adminUsers.value.length === 0) {
    try {
      const res = await listUsers()
      if (res.success && res.users) {
        adminUsers.value = res.users
      }
    } catch {
      // 用户列表加载失败时保持空，弹窗内不展示可选用户
    }
  }
}

async function saveUsersModal() {
  if (!usersModalItem.value) return
  savingUsers.value = true
  error.value = ''
  try {
    const res = await setPromptUsers(
      usersModalItem.value.owner_id!,
      activeKind.value,
      usersModalItem.value.name,
      usersModalSelected.value
    )
    if (res?.success) {
      usersModalOpen.value = false
      await loadPrompts()
    } else {
      error.value = res?.error_message || '保存失败'
    }
  } catch (e: any) {
    error.value = '保存失败：' + (e?.message || '未知错误')
  } finally {
    savingUsers.value = false
  }
}

onMounted(loadPrompts)
</script>

<style scoped>
.kind-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.kind-tab {
  padding: 8px 18px;
  border: 1px solid var(--border-color);
  background: #fff;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-sub);
  transition: all 0.2s;
}
.kind-tab:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.kind-tab.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  font-weight: 600;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.placeholder-hint {
  font-size: 12px;
  color: var(--text-sub);
}
.placeholder-hint code {
  margin-right: 6px;
  padding: 2px 6px;
  background: #f0f0f0;
  border-radius: 4px;
  color: var(--primary);
}
.editor-card {
  margin-bottom: 20px;
  border: 2px solid var(--primary);
}
.editor-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}
.editor-head h3 {
  margin: 0;
  font-size: 16px;
}
.icon-btn {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-sub);
}
.editor-body {
  padding: 20px;
}
.field {
  margin-bottom: 16px;
}
.field label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 600;
}
.field .input:disabled {
  background: #f5f5f5;
  color: #999;
  cursor: not-allowed;
}
.base-editor-tip {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: #b45309;
}
.input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}
.textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.6;
  font-family: inherit;
  box-sizing: border-box;
  resize: vertical;
}
.editor-actions {
  display: flex;
  gap: 10px;
}
.prompt-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.prompt-card {
  padding: 16px 20px;
}
.prompt-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.prompt-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
}
.base-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #F0F0F0;
  color: #666;
}
.mine-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #E8F5E9;
  color: #2E7D32;
}
.shared-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #E3F2FD;
  color: #1565C0;
}
.prompt-preview {
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-sub);
  white-space: pre-wrap;
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.prompt-preview.expanded {
  display: block;
}
.expand-btn {
  border: none;
  background: none;
  color: var(--primary);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 10px;
}
.prompt-actions {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}
.base-actions .base-tip {
  font-size: 12px;
  color: #999;
}
.empty-tip {
  text-align: center;
  padding: 40px;
  color: #999;
  font-size: 14px;
}
.allowed-users {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
  font-size: 12px;
}
.allowed-label {
  color: #666;
}
.allowed-chip {
  padding: 2px 10px;
  border-radius: 12px;
  background: #E8F5E9;
  color: #2E7D32;
  font-weight: 600;
}
.allowed-empty {
  color: #999;
}
/* 配置用户弹窗 */
.modal {
  width: 420px;
  max-width: 92vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal .editor-body {
  overflow: auto;
}
.modal-sub {
  font-size: 13px;
  color: #555;
  margin: 0 0 14px;
}
.user-check-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.user-check {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}
.user-check:hover {
  background: #F7F9FC;
}
.user-check input {
  margin: 0;
}
.owner-flag {
  font-size: 12px;
  color: #999;
}
</style>
