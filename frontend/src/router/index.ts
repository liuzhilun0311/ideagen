// Vue Router 4 uses the application's bundler module resolution and typed route components.
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import WorkspaceView from '../views/WorkspaceView.vue'
import ResultView from '../views/ResultView.vue'
import HistoryView from '../views/HistoryView.vue'
import LoginView from '../views/LoginView.vue'
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
      redirect: '/workspace'
    },
    {
      path: '/generate',
      name: 'generate',
      redirect: '/workspace'
    },
    {
      path: '/workspace',
      name: 'workspace',
      component: WorkspaceView
    },
    {
      path: '/workspace/copy',
      name: 'workspace-copy',
      component: WorkspaceView
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
      component: () => import('../views/SettingsView.vue')
    },
    {
      path: '/prompts',
      name: 'prompts',
      component: () => import('../views/PromptManageView.vue')
    },
    {
      path: '/reference-assets',
      name: 'reference-assets',
      component: () => import('../views/ReferenceAssetsView.vue')
    },
    {
      path: '/users',
      name: 'users',
      component: () => import('../views/UsersView.vue'),
      meta: { admin: true }
    }
  ]
})

// 全局路由守卫：未登录跳转到登录页；管理员页面校验管理员身份
router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!getToken()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !getUser()?.is_admin) {
    return { name: 'home' }
  }
  if ((to.name === 'workspace' || to.name === 'workspace-copy') && !useGeneratorStore().outline.pages.length) return { name: 'home' }
  return true
})

export default router
