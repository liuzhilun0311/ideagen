<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <span class="login-brand">AI 图文创作</span>
      </div>
      <h1 class="login-title">{{ isRegister ? '注册账号' : '欢迎回来' }}</h1>
      <p class="login-subtitle">{{ isRegister ? '创建你的专属账号' : '登录后继续你的创作' }}</p>

      <div v-if="errorMsg" class="login-error">{{ errorMsg }}</div>

      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="form-field">
          <label class="form-label" for="login-username">用户名</label>
          <input
            id="login-username"
            v-model="username"
            type="text"
            class="form-input"
            placeholder="请输入用户名"
            autocomplete="username"
            autofocus
          />
        </div>
        <div class="form-field">
          <label class="form-label" for="login-password">密码</label>
          <input
            id="login-password"
            v-model="password"
            type="password"
            class="form-input"
            placeholder="请输入密码"
            autocomplete="current-password"
          />
          <p v-if="isRegister" class="form-hint">密码至少 6 个字符</p>
        </div>

        <button
          type="submit"
          class="login-btn"
          :disabled="loading || !username.trim() || !password"
        >
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '请稍候...' : (isRegister ? '注册并登录' : '登 录') }}
        </button>
      </form>

      <div class="login-switch">
        <span>{{ isRegister ? '已有账号？' : '还没有账号？' }}</span>
        <button type="button" class="switch-btn" @click="toggleMode" :disabled="loading">
          {{ isRegister ? '去登录' : '立即注册' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isRegister = ref(false)
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

function toggleMode() {
  isRegister.value = !isRegister.value
  errorMsg.value = ''
}

async function handleSubmit() {
  errorMsg.value = ''
  loading.value = true
  try {
    let result
    if (isRegister.value) {
      result = await authStore.register(username.value.trim(), password.value)
    } else {
      result = await authStore.login(username.value.trim(), password.value)
    }
    if (result.success) {
      const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
      router.replace(redirect)
    } else {
      errorMsg.value = result.message || '操作失败，请重试'
    }
  } catch (e: any) {
    errorMsg.value = e?.message || '网络错误，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff5f5 0%, #fdf2f8 50%, #f5f3ff 100%);
  padding: 20px;
}
.login-card {
  width: 400px;
  max-width: 100%;
  background: #fff;
  border-radius: 16px;
  padding: 36px 32px 28px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1);
  text-align: center;
}
.login-logo {
  margin-bottom: 8px;
}
.login-brand {
  display: block;
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 2px;
  background: linear-gradient(135deg, #ff2442 0%, #ff5c72 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.login-title {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: #1a1a1a;
}
.login-subtitle {
  margin: 0 0 20px;
  font-size: 14px;
  color: #999;
}
.login-error {
  margin-bottom: 14px;
  padding: 8px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  border-radius: 8px;
  font-size: 13px;
  text-align: left;
}
.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: left;
}
.form-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.form-input {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  color: #1a1a1a;
  background: #fff;
  box-sizing: border-box;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.form-input:focus {
  outline: none;
  border-color: #ff2442;
  box-shadow: 0 0 0 3px rgba(255, 36, 66, 0.12);
}
.form-input::placeholder {
  color: #9ca3af;
}
.form-hint {
  margin: 0;
  font-size: 12px;
  color: #9ca3af;
}
.login-btn {
  margin-top: 6px;
  padding: 12px 20px;
  border: none;
  border-radius: 50px;
  background: linear-gradient(135deg, #ff2442 0%, #ff5c72 100%);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 4px 14px rgba(255, 36, 66, 0.3);
  transition: all 0.2s;
}
.login-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(255, 36, 66, 0.4);
}
.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.login-switch {
  margin-top: 18px;
  font-size: 13px;
  color: #666;
}
.switch-btn {
  background: none;
  border: none;
  color: #ff2442;
  font-weight: 600;
  cursor: pointer;
  padding: 0 4px;
}
.switch-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
