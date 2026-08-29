// 注意：如果出现 vue-router 类型声明文件找不到的错误，请在 tsconfig.json 中将 moduleResolution 设置为 "bundler"
// 并确保已安装 vue-router@3（npm install vue-router@4）
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import OutlineView from '../views/OutlineView.vue'
import GenerateView from '../views/GenerateView.vue'
import ResultView from '../views/ResultView.vue'
import HistoryView from '../views/HistoryView.vue'
import SettingsView from '../views/SettingsView.vue'
import PromptManageView from '../views/PromptManageView.vue'
import LoginView from '../views/LoginView.vue'
import UsersView from '../views/UsersView.vue'
import { getToken, getUser } from '../api/token'
import { useGeneratorStore } from '../stores/generator'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { public: true }
    },
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/outline',
      name: 'outline',
      component: OutlineView
    },
    {
      path: '/generate',
      name: 'generate',
      component: GenerateView
    },
    {
      path: '/result',
      name: 'result',
      component: ResultView
    },
    {
      path: '/history',
      name: 'history',
      component: HistoryView
    },
    {
      path: '/history/:id',
      name: 'history-detail',
      component: HistoryView
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
    },
    {
      path: '/prompts',
      name: 'prompts',
      component: PromptManageView
    },
    {
      path: '/users',
      name: 'users',
      component: UsersView,
      meta: { admin: true }
    }
  ]
})

// 全局路由守卫：未登录跳转到登录页；管理员页面校验管理员身份
router.beforeEach((to, from) => {
  // 进入编辑大纲页时的草稿清理（在路由层统一处理）：
  // 组件被 KeepAlive 缓存后，onMounted 不会重新触发，旧大纲可能在组件内残留。
  // 规则：
  // - 从首页新建任务进入（entrySource=home，无 from=generate）→ 清空旧草稿
  // - 从历史记录进入（entrySource=history）→ 保留该记录内容
  // - 从图文页"返回编辑大纲"（query.from=generate 或 from=/generate，含浏览器返回）→ 保留当前大纲继续编辑
  if (to.path === '/outline' && to.query.from !== 'generate' && from.path !== '/generate') {
    const genStore = useGeneratorStore()
    if (genStore.entrySource !== 'history') {
      genStore.prepareNewOutline()
    }
  }
  if (to.meta.public) return true
  if (!getToken()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !getUser()?.is_admin) {
    return { name: 'home' }
  }
  return true
})

export default router
