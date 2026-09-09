<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <main v-if="isLoginPage" id="main-content" tabindex="-1"><RouterView /></main>
    <template v-else>
      <header class="studio-header">
        <button type="button" class="brand" aria-label="IdeaGen 创作首页" @click="navTo('home')">
          <Layers2 :size="25" aria-hidden="true" /><span>IdeaGen</span>
        </button>
        <button ref="menuToggle" type="button" class="icon-button menu-toggle"
          :aria-expanded="menuOpen" aria-controls="primary-navigation"
          :aria-label="menuOpen ? '关闭导航菜单' : '打开导航菜单'"
          :title="menuOpen ? '关闭导航菜单' : '打开导航菜单'" @click="menuOpen = !menuOpen">
          <X v-if="menuOpen" :size="20" aria-hidden="true" />
          <Menu v-else :size="20" aria-hidden="true" />
        </button>
        <div id="primary-navigation" class="header-menu" :class="{ 'is-open': menuOpen }">
          <nav class="nav-menu" aria-label="主要导航">
            <button v-for="item in navigation" :key="item.section" type="button" class="nav-item"
              :class="{ active: sectionOf(route.path) === item.section }"
              :aria-current="sectionOf(route.path) === item.section ? 'page' : undefined"
              @click="navTo(item.section)">
              <component :is="item.icon" :size="18" aria-hidden="true" />{{ item.label }}
            </button>
          </nav>
          <div class="header-user">
            <span class="user-avatar" aria-hidden="true">{{ avatarChar }}</span>
            <span class="user-name" :title="authStore.username">{{ authStore.username }}</span>
            <button class="icon-button logout-btn" type="button" title="退出登录" aria-label="退出登录" @click="handleLogout">
              <LogOut :size="19" aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>
      <main id="main-content" class="layout-main" tabindex="-1">
        <div v-if="session.busy || session.notice" class="creation-status" role="status">
          <span>{{ session.notice || '创作任务进行中' }}</span>
          <button v-if="!isWorkflow(route.path) && route.path !== '/'" type="button" class="status-link" @click="navTo('home')">返回创作</button>
          <button v-if="!session.busy" type="button" class="icon-button" title="关闭提示" aria-label="关闭创作提示" @click="session.notice = ''"><X :size="16" /></button>
        </div>
        <RouterView v-slot="{ Component }">
          <KeepAlive><component :is="Component" /></KeepAlive>
        </RouterView>
      </main>
    </template>
  </div>
</template>

<script setup lang="ts">
import { RouterView, useRoute, useRouter } from 'vue-router'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { Layers2, Menu, X, LogOut, PenLine, Images, MessageSquare, SlidersHorizontal, Users } from 'lucide-vue-next'
import { setupAutoSave, useGeneratorStore } from './stores/generator'
import { useAuthStore } from './stores/auth'
import { useStudioSession } from './stores/studioSession'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const genStore = useGeneratorStore()
const session = useStudioSession()
const creationPath = computed(() => genStore.outline.pages.length ? '/workspace' : '/')
const isLoginPage = computed(() => route.path === '/login')
const menuOpen = ref(false)
const menuToggle = ref<HTMLButtonElement | null>(null)
const navigation = computed(() => [
  { section: 'home', label: '创作', icon: PenLine },
  { section: 'history', label: '作品', icon: Images },
  { section: 'prompts', label: '提示词', icon: MessageSquare },
  { section: 'settings', label: '模型', icon: SlidersHorizontal },
  ...(authStore.isAdmin ? [{ section: 'users', label: '用户管理', icon: Users }] : []),
])
const DEFAULT_ROUTES: Record<string, string> = {
  home: '/', history: '/history', prompts: '/prompts', settings: '/settings', users: '/users',
}
const lastRouteBySection = reactive<Record<string, string>>({ ...DEFAULT_ROUTES })
const isWorkflow = (path: string) => /^\/(workspace|outline|generate|result)(\/|$|\?)/.test(path)

function sectionOf(path: string): string {
  if (path.startsWith('/prompts')) return 'prompts'
  if (path.startsWith('/settings')) return 'settings'
  if (path.startsWith('/users')) return 'users'
  if (path.startsWith('/history')) return 'history'
  if (isWorkflow(path)) return 'home'
  return 'home'
}
function closeMenu(restoreFocus = false) {
  if (!menuOpen.value) return
  menuOpen.value = false
  if (restoreFocus) menuToggle.value?.focus()
}
watch(() => route.fullPath, (path) => {
  closeMenu()
  if (route.path === '/login') return
  const section = sectionOf(route.path)
  // Workflow routes depend on the current draft, so remember the section landing page.
  lastRouteBySection[section] = isWorkflow(route.path) ? DEFAULT_ROUTES[section] : path
}, { immediate: true })
function navTo(section: string) {
  closeMenu(true)
  if (section === 'home') {
    void router.push(creationPath.value)
    return
  }
  if (sectionOf(route.path) === section) {
    if (route.path !== DEFAULT_ROUTES[section]) router.push(DEFAULT_ROUTES[section])
    return
  }
  const target = lastRouteBySection[section] || DEFAULT_ROUTES[section]
  router.push(target === route.fullPath ? DEFAULT_ROUTES[section] : target)
}
const avatarChar = computed(() => (authStore.username || 'U').charAt(0).toUpperCase())
async function handleLogout() {
  const failure = await router.push('/login')
  if (!failure) await authStore.logout()
}
const removeGuard = router.beforeEach(to => {
  if (to.path !== '/login' || route.path === '/login') return true
  if (session.busy) {
    session.notice = '请先取消创作任务再退出登录'
    return false
  }
  return !(session.dirty || (genStore.topic.trim() && !genStore.recordId))
    || window.confirm('当前创作尚未保存到服务器，确定退出登录？')
})
const scrollPositions = new Map<string, number>()
const removeScrollGuard = router.beforeEach((_to, from) => {
  scrollPositions.set(from.fullPath, window.scrollY)
})
const removeScrollRestore = router.afterEach(async (to, _from, failure) => {
  if (failure) return
  await nextTick()
  if (route.fullPath === to.fullPath) window.scrollTo({ top: scrollPositions.get(to.fullPath) || 0, behavior: 'instant' })
})
function guardUnload(event: BeforeUnloadEvent) {
  if (!session.busy && !session.dirty && !(genStore.topic.trim() && !genStore.recordId)) return
  event.preventDefault()
  event.returnValue = ''
}
function handleEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') closeMenu(true)
}
onMounted(() => {
  setupAutoSave()
  window.addEventListener('keydown', handleEscape)
  window.addEventListener('beforeunload', guardUnload)
})
onUnmounted(() => {
  removeGuard()
  removeScrollGuard()
  removeScrollRestore()
  window.removeEventListener('keydown', handleEscape)
  window.removeEventListener('beforeunload', guardUnload)
})
</script>

<style scoped>
.creation-status { display:flex; flex-wrap:wrap; align-items:center; gap:8px 16px; min-height:44px; margin-bottom:16px; padding:0 12px; border-left:3px solid var(--primary); background:#eef3ff; font-size:14px; }
.creation-status>.icon-button { margin-left:auto; }
.status-link { background:none; border:0; color:var(--primary); font:inherit; min-height:44px; text-decoration:underline; }
.studio-header {
  position: fixed; inset: 0 0 auto; height: var(--header-height); z-index: 100;
  display: flex; align-items: center; gap: 40px; padding: 0 32px;
  background: var(--bg-card); border-bottom: 1px solid var(--border-color);
}
.brand {
  display: inline-flex; align-items: center; gap: 10px; min-height: 44px;
  border: 0; background: transparent; font-size: 22px; font-weight: 700; cursor: pointer; flex-shrink: 0;
}
.brand svg { color: var(--primary); }
.header-menu { display: flex; align-items: center; flex: 1; min-width: 0; gap: 20px; }
.nav-menu { display: flex; align-items: center; gap: 4px; }
.nav-item {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  min-height: 44px; padding: 8px 12px; border: 0; border-radius: 6px;
  background: transparent; color: var(--text-sub); font-size: 15px; white-space: nowrap; cursor: pointer;
}
.nav-item:hover { background: var(--bg-body); color: var(--text-main); }
.nav-item.active { background: var(--primary-light); color: var(--primary); font-weight: 600; }
.header-user { margin-left: auto; display: flex; align-items: center; gap: 10px; min-width: 0; }
.user-avatar {
  width: 32px; height: 32px; flex: 0 0 32px; border-radius: 50%;
  display: grid; place-items: center; background: var(--success-light);
  color: var(--success); font-size: 14px; font-weight: 600;
}
.user-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
.menu-toggle { display: none; margin-left: auto; }
@media (max-width: 1000px) {
  .studio-header { gap: 20px; }
  .user-name { display: none; }
}
@media (max-width: 800px) {
  .studio-header { padding: 0 16px; }
  .menu-toggle { display: inline-flex; }
  .header-menu {
    display: none; position: absolute; top: 64px; left: 0; right: 0;
    padding: 16px; background: var(--bg-card); border-bottom: 1px solid var(--border-color);
    max-height: calc(100dvh - 64px); overflow-y: auto;
  }
  .header-menu.is-open { display: flex; flex-direction: column; align-items: stretch; }
  .nav-menu { flex-direction: column; align-items: stretch; }
  .nav-item { justify-content: flex-start; font-size: 16px; }
  .header-user { margin-left: 0; padding-top: 12px; border-top: 1px solid var(--border-color); }
  .user-name { display: block; max-width: none; flex: 1; }
  .logout-btn { margin-left: auto; }
}
</style>
