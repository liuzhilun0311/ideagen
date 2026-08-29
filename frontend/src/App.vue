<template>
  <div id="app">
    <!-- 登录页：全屏展示，不显示侧边栏 -->
    <template v-if="isLoginPage">
      <RouterView />
    </template>

    <template v-else>
      <!-- 侧边栏 Sidebar -->
      <aside class="layout-sidebar">
        <div class="logo-area">
          <span class="brand-title">AI 图文创作</span>
        </div>

        <nav class="nav-menu">
          <button type="button" class="nav-item" :class="{ active: sectionOf(route.path) === 'home' }" @click="navTo('home')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            创作中心
          </button>
          <button type="button" class="nav-item" :class="{ active: sectionOf(route.path) === 'history' }" @click="navTo('history')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            历史记录
          </button>
          <button type="button" class="nav-item" :class="{ active: sectionOf(route.path) === 'prompts' }" @click="navTo('prompts')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path><line x1="9" y1="10" x2="15" y2="10"></line><line x1="9" y1="14" x2="13" y2="14"></line></svg>
            提示词设计
          </button>
          <button type="button" class="nav-item" :class="{ active: sectionOf(route.path) === 'settings' }" @click="navTo('settings')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M12 1v6m0 6v6m-6-6h6m6 0h-6"></path><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            模型设置
          </button>
          <button v-if="authStore.isAdmin" type="button" class="nav-item" :class="{ active: sectionOf(route.path) === 'users' }" @click="navTo('users')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            用户管理
          </button>
        </nav>

        <div class="sidebar-user" style="margin-top: auto; padding-top: 20px; border-top: 1px solid var(--border-color);">
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="user-avatar">{{ avatarChar }}</div>
            <div style="flex: 1; min-width: 0;">
              <div style="font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ authStore.username }}</div>
              <div style="font-size: 12px; color: var(--text-sub);">{{ authStore.isAdmin ? '管理员' : '普通用户' }}</div>
            </div>
            <button class="logout-btn" type="button" title="退出登录" @click="handleLogout">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
            </button>
          </div>
        </div>
      </aside>

      <!-- 主内容区 -->
      <main class="layout-main">
        <RouterView v-slot="{ Component }">
          <KeepAlive>
            <component :is="Component" />
          </KeepAlive>
        </RouterView>
      </main>
    </template>
  </div>
</template>

<script setup lang="ts">
import { RouterView, useRoute, useRouter } from 'vue-router'
import { computed, onMounted, reactive, watch } from 'vue'
import { setupAutoSave, useGeneratorStore } from './stores/generator'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const genStore = useGeneratorStore()

// 登录页不显示侧边栏
const isLoginPage = computed(() => route.path === '/login')

// 各导航模块的默认首页
const DEFAULT_ROUTES: Record<string, string> = {
  home: '/',
  history: '/history',
  prompts: '/prompts',
  settings: '/settings',
  users: '/users',
}

// 各模块最后访问的路径（模块切换记忆功能）
const lastRouteBySection = reactive<Record<string, string>>({ ...DEFAULT_ROUTES })

// 判断当前路径属于哪个导航模块
function sectionOf(path: string): string {
  if (path === '/') return 'home'
  if (path.startsWith('/prompts')) return 'prompts'
  if (path.startsWith('/settings')) return 'settings'
  if (path.startsWith('/users')) return 'users'
  if (path.startsWith('/history')) return 'history'
  // 编辑/生成/结果页：按进入来源归属模块（从历史进入属于"历史记录"）
  if (path.startsWith('/outline') || path.startsWith('/generate') || path.startsWith('/result')) {
    return genStore.entrySource === 'history' ? 'history' : 'home'
  }
  return 'home'
}

// 记录每个模块最后访问的路径。
// 注意：/outline /generate /result 是编辑流程页，依赖当前任务上下文，
// 作为导航入口记忆没有意义（跨模块切回来会跳到脱离上下文的页面），
// 因此遇到这些页面时将该模块记忆重置为模块首页。
watch(() => route.fullPath, (path) => {
  const section = sectionOf(path)
  if (path.startsWith('/outline') || path.startsWith('/generate') || path.startsWith('/result')) {
    lastRouteBySection[section] = DEFAULT_ROUTES[section]
  } else {
    lastRouteBySection[section] = path
  }
}, { immediate: true })

// 点击导航：跨模块 -> 恢复该模块上次位置；同模块 -> 回该模块首页
function navTo(section: string) {
  const current = sectionOf(route.path)
  if (current === section) {
    if (route.path !== DEFAULT_ROUTES[section]) {
      router.push(DEFAULT_ROUTES[section])
    }
    return
  }
  const target = lastRouteBySection[section] || DEFAULT_ROUTES[section]
  // 记忆的目标路径与当前路径相同（如都在 /outline，但分属不同模块）时，
  // 直接回该模块首页，避免"点了没反应"
  router.push(target === route.fullPath ? DEFAULT_ROUTES[section] : target)
}

// 头像首字符
const avatarChar = computed(() => {
  const name = authStore.username || 'U'
  return name.charAt(0).toUpperCase()
})

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

// 启用自动保存到 localStorage
onMounted(() => {
  setupAutoSave()
})
</script>

<style scoped>
.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary) 0%, #ff6b6b 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}
.brand-title {
  display: inline-block;
  font-size: 20px;
  font-weight: 800;
  background: linear-gradient(135deg, #ff2442 0%, #ff5c72 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 1px;
}
.logout-btn {
  background: none;
  border: none;
  color: var(--text-sub);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  transition: all 0.2s;
  flex-shrink: 0;
}
.logout-btn:hover {
  color: var(--primary);
  background: rgba(255, 36, 66, 0.08);
}
</style>
