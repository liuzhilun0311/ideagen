<template>
  <div class="login-page">
    <section class="login-panel" aria-labelledby="login-title">
      <div class="login-brand"><Layers2 :size="28" aria-hidden="true" /><span>IdeaGen</span></div>
      <h1 id="login-title">{{ isRegister ? '注册账号' : '欢迎回来' }}</h1>
      <p class="login-subtitle muted">{{ isRegister ? '创建你的账号' : '登录后继续你的创作' }}</p>
      <div v-if="errorMsg" id="login-error" class="error-banner" role="alert">{{ errorMsg }}</div>
      <form class="login-form" :aria-busy="loading" @submit.prevent="handleSubmit">
        <div class="form-field">
          <label for="login-username">用户名</label>
          <input id="login-username" v-model="username" type="text" class="field"
            placeholder="请输入用户名" autocomplete="username" required autofocus
            :disabled="loading" :aria-describedby="errorMsg ? 'login-error' : undefined" />
        </div>
        <div class="form-field">
          <label for="login-password">密码</label>
          <input id="login-password" v-model="password" type="password" class="field"
            placeholder="请输入密码" :autocomplete="isRegister ? 'new-password' : 'current-password'"
            required :minlength="isRegister ? 6 : undefined" :disabled="loading"
            :aria-describedby="[isRegister ? 'password-hint' : '', errorMsg ? 'login-error' : ''].filter(Boolean).join(' ') || undefined" />
          <p v-if="isRegister" id="password-hint" class="form-hint muted">密码至少 6 个字符</p>
        </div>
        <button type="submit" class="btn btn-primary login-btn" :disabled="loading || !username.trim() || !password">
          <LoaderCircle v-if="loading" class="loading-icon" :size="18" aria-hidden="true" />
          {{ loading ? '请稍候...' : (isRegister ? '注册并登录' : '登录') }}
        </button>
        <span class="login-status muted" role="status">{{ loading ? '正在提交，请稍候' : '' }}</span>
      </form>
      <div class="login-switch">
        <span class="muted">{{ isRegister ? '已有账号？' : '还没有账号？' }}</span>
        <button type="button" class="switch-btn" :disabled="loading" @click="toggleMode">{{ isRegister ? '去登录' : '立即注册' }}</button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Layers2, LoaderCircle } from 'lucide-vue-next'
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
  if (loading.value || !username.value.trim() || !password.value) return
  errorMsg.value = ''
  loading.value = true
  try {
    const result = isRegister.value
      ? await authStore.register(username.value.trim(), password.value)
      : await authStore.login(username.value.trim(), password.value)
    if (result.success) {
      const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
      router.replace(redirect)
    } else {
      errorMsg.value = result.message || '操作失败，请重试'
    }
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '网络错误，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh; min-height: 100dvh; display: grid; place-items: center;
  padding: 48px 24px; background: var(--bg-body);
}
.login-panel { width: 100%; max-width: 360px; min-width: 0; }
.login-brand {
  display: flex; align-items: center; gap: 10px; margin-bottom: 36px;
  font-size: 28px; font-weight: 700; line-height: 1.3;
}
.login-brand svg { color: var(--primary); }
h1 { font-size: 24px; line-height: 1.4; font-weight: 650; margin-bottom: 6px; }
.login-subtitle { margin-bottom: 28px; font-size: 16px; }
.login-form { display: flex; flex-direction: column; gap: 18px; }
.form-field { display: flex; flex-direction: column; gap: 8px; }
.form-field label { font-size: 16px; font-weight: 500; }
.form-hint { font-size: 14px; }
.login-btn { width: 100%; margin-top: 6px; }
.loading-icon { animation: spin 1s linear infinite; }
.login-status { min-height: 22px; font-size: 14px; text-align: center; }
.login-switch { display: flex; align-items: center; flex-wrap: wrap; justify-content: center; gap: 4px; font-size: 16px; }
.switch-btn {
  min-width: 44px; min-height: 44px; padding: 8px; border: 0; border-radius: 4px;
  background: transparent; color: var(--primary); font-weight: 600; cursor: pointer;
}
.switch-btn:hover:not(:disabled) { background: var(--primary-light); }
.switch-btn:disabled { opacity: 0.55; cursor: not-allowed; }
@media (max-width: 700px) { .login-page { padding: 32px 16px; } }
</style>
