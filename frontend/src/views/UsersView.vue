<template>
  <div class="container">
    <div class="page-header">
      <div>
        <h1 class="page-title">用户管理</h1>
      </div>
      <button class="btn btn-success btn-small" @click="loadUsers" :disabled="loading">
        {{ loading ? '加载中…' : '刷新列表' }}
      </button>
    </div>

    <div class="card" v-if="!loading">
      <div v-if="users.length === 0" style="text-align: center; color: var(--text-sub); padding: 40px 0;">
        暂无用户
      </div>
      <table v-else class="user-table">
        <thead>
          <tr>
            <th>用户名</th>
            <th>角色</th>
            <th>创建时间</th>
            <th style="width: 200px;">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>
              <span style="font-weight: 600;">{{ u.username }}</span>
              <span v-if="u.id === authStore.user?.id" style="margin-left: 8px; font-size: 12px; color: var(--text-sub);">(当前账号)</span>
            </td>
            <td>
              <span :class="u.is_admin ? 'badge badge-admin' : 'badge badge-user'">
                {{ u.is_admin ? '管理员' : '普通用户' }}
              </span>
            </td>
            <td style="color: var(--text-sub); font-size: 13px;">{{ formatTime(u.created_at) }}</td>
            <td>
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-info btn-xs" @click="openResetPassword(u)">重置密码</button>
                <button
                  class="btn btn-danger btn-xs"
                  :disabled="u.id === authStore.user?.id"
                  :title="u.id === authStore.user?.id ? '不能删除当前登录的账号' : ''"
                  @click="confirmDelete(u)"
                >
                  删除
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 重置密码弹窗 -->
    <Teleport to="body">
      <div v-if="resetTarget" class="um-mask" @click.self="closeReset">
        <div class="um-dialog">
          <h3 class="um-title">重置密码</h3>
          <p class="um-desc">为账号 <b>{{ resetTarget.username }}</b> 设置新密码（至少 6 个字符），保存后该用户将强制重新登录。</p>
          <input
            v-model="newPassword"
            type="password"
            class="um-input"
            placeholder="输入新密码"
            @keyup.enter="submitResetPassword"
          />
          <p v-if="resetError" class="um-error">{{ resetError }}</p>
          <div class="um-actions">
            <button class="btn btn-ghost" @click="closeReset">取消</button>
            <button class="btn btn-info" @click="submitResetPassword" :disabled="resetting">
              {{ resetting ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 删除确认弹窗 -->
    <Teleport to="body">
      <div v-if="deleteTarget" class="um-mask" @click.self="closeDelete">
        <div class="um-dialog">
          <h3 class="um-title">删除用户</h3>
          <p class="um-desc">
            确定要删除账号 <b>{{ deleteTarget.username }}</b> 吗？<br />
            该用户的历史记录与图片将一并删除，此操作不可恢复。
          </p>
          <div class="um-actions">
            <button class="btn btn-ghost" @click="closeDelete">取消</button>
            <button class="btn btn-danger" @click="submitDelete" :disabled="deleting">
              {{ deleting ? '删除中…' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.user-table {
  width: 100%;
  border-collapse: collapse;
}
.user-table th,
.user-table td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}
.user-table th {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-sub);
  background: #fafafa;
}
.user-table tbody tr:hover {
  background: #fafafa;
}
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}
.badge-admin {
  background: rgba(255, 36, 66, 0.1);
  color: #e6395a;
}
.badge-user {
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
}
:deep(.btn-xs) {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 5px;
}
.um-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 10001;
  display: flex;
  align-items: center;
  justify-content: center;
}
.um-dialog {
  background: #fff;
  width: 400px;
  max-width: 90vw;
  border-radius: 14px;
  padding: 26px 26px 22px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.25);
}
.um-title {
  margin: 0 0 10px;
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}
.um-desc {
  margin: 0 0 16px;
  font-size: 14px;
  color: #555;
  line-height: 1.6;
}
.um-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}
.um-input:focus {
  border-color: var(--primary);
}
.um-error {
  margin: 10px 0 0;
  font-size: 13px;
  color: #e6395a;
}
.um-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
</style>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listUsers, changePassword, deleteUser, type AuthUser } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const users = ref<AuthUser[]>([])
const loading = ref(false)

const resetTarget = ref<AuthUser | null>(null)
const newPassword = ref('')
const resetError = ref('')
const resetting = ref(false)

const deleteTarget = ref<AuthUser | null>(null)
const deleting = ref(false)

function formatTime(iso?: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await listUsers()
    if (res.success && res.users) {
      users.value = res.users
    } else {
      alert(res.error_message || '加载用户列表失败')
    }
  } catch (e: any) {
    alert('加载用户列表失败：' + (e?.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function openResetPassword(user: AuthUser) {
  resetTarget.value = user
  newPassword.value = ''
  resetError.value = ''
}

function closeReset() {
  if (resetting.value) return
  resetTarget.value = null
  newPassword.value = ''
}

async function submitResetPassword() {
  if (!resetTarget.value) return
  if (!newPassword.value || newPassword.value.length < 6) {
    resetError.value = '新密码至少 6 个字符'
    return
  }
  resetting.value = true
  resetError.value = ''
  try {
    const res = await changePassword(resetTarget.value.id, newPassword.value)
    if (res.success) {
      // 保存完成：直接关闭弹窗（绕过 resetting 守卫），不再弹出对话框
      resetTarget.value = null
      newPassword.value = ''
    } else {
      resetError.value = res.error_message || '重置失败'
    }
  } catch (e: any) {
    resetError.value = '重置失败：' + (e?.message || '未知错误')
  } finally {
    resetting.value = false
  }
}

function confirmDelete(user: AuthUser) {
  deleteTarget.value = user
}

function closeDelete() {
  if (deleting.value) return
  deleteTarget.value = null
}

async function submitDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    const res = await deleteUser(deleteTarget.value.id)
    // 操作完成：直接关闭确认弹窗（绕过 deleting 守卫），成功后不再弹出任何对话框
    deleteTarget.value = null
    if (res.success) {
      await loadUsers()
    } else {
      alert(res.error_message || '删除失败')
    }
  } catch (e: any) {
    deleteTarget.value = null
    alert('删除失败：' + (e?.message || '未知错误'))
  } finally {
    deleting.value = false
  }
}

onMounted(loadUsers)
</script>
