/**
 * 用户认证状态 Store
 *
 * 管理登录态：token、当前用户信息
 * token 持久化在 localStorage（通过 api/token.ts），刷新页面后恢复
 */
import { defineStore } from 'pinia'
import {
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
  getMe,
  type AuthUser,
} from '../api/auth'
import {
  getToken,
  setToken,
  getUser,
  setUser,
  clearAuth,
  type StoredUser,
} from '../api/token'

interface AuthState {
  token: string
  user: StoredUser | null
  sessionRevision: number
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: getToken(),
    user: getUser(),
    sessionRevision: 0,
  }),

  getters: {
    isLoggedIn: (state): boolean => !!state.token && !!state.user,
    isAdmin: (state): boolean => !!state.user?.is_admin,
    username: (state): string => state.user?.username || '',
  },

  actions: {
    async login(username: string, password: string) {
      const res = await apiLogin(username, password)
      if (res.success && res.token && res.user) {
        this.sessionRevision += 1
        this.token = res.token
        this.user = res.user as StoredUser
        setToken(res.token)
        setUser(res.user as StoredUser)
        return { success: true }
      }
      return { success: false, message: res.error_message || '登录失败' }
    },

    async register(username: string, password: string) {
      const res = await apiRegister(username, password)
      if (res.success && res.user) {
        // 注册成功后自动登录
        return this.login(username, password)
      }
      return { success: false, message: res.error_message || '注册失败' }
    },

    async logout() {
      const token = this.token
      const revision = this.sessionRevision
      try {
        if (token) {
          await apiLogout(token)
        }
      } catch {
        // 忽略注销接口错误
      }
      if (this.sessionRevision !== revision || this.token !== token) return
      this.sessionRevision += 1
      this.token = ''
      this.user = null
      if (getToken() === token) clearAuth()
    },

    /** 启动时校验 token 有效性（过期则清除登录态） */
    async validateSession(): Promise<boolean> {
      if (!this.token) return false
      try {
        const res = await getMe()
        if (res.success && res.user) {
          this.user = res.user as StoredUser
          setUser(res.user as StoredUser)
          return true
        }
      } catch {
        // 网络错误不强制登出
      }
      this.token = ''
      this.user = null
      clearAuth()
      return false
    },
  },
})

export type { AuthUser }
