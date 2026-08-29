// 认证 Token 存取（localStorage），独立模块避免循环依赖

const TOKEN_KEY = 'ideagen_token'
const USER_KEY = 'ideagen_user'

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // ignore
  }
}

export interface StoredUser {
  id: string
  username: string
  is_admin: boolean
  created_at?: string
}

export function getUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setUser(user: StoredUser | null) {
  try {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
  } catch {
    // ignore
  }
}

export function clearAuth() {
  setToken(null)
  setUser(null)
}
