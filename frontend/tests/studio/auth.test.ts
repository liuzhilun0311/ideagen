import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../src/stores/auth'
import { getToken, getUser, setToken, setUser } from '../../src/api/token'

const originalAdapter = axios.defaults.adapter
const oldUser = { id: 'old', username: 'old-user', is_admin: false }
const nextUser = { id: 'next', username: 'next-user', is_admin: false }
let logoutConfig: InternalAxiosRequestConfig | undefined
let finishLogout: (status?: number) => void
let nextToken: string

beforeEach(() => {
  setActivePinia(createPinia())
  setToken('old-token')
  setUser(oldUser)
  nextToken = 'next-token'
  logoutConfig = undefined
  vi.stubGlobal('window', { location: { pathname: '/workspace', href: '/workspace' } })
  axios.defaults.adapter = config => {
    if (config.url === '/api/auth/logout') {
      logoutConfig = config
      return new Promise<AxiosResponse>((resolve, reject) => {
        finishLogout = (status = 200) => {
          const response = { data: { success: true }, status, statusText: '', headers: {}, config }
          if (status === 200) resolve(response)
          else reject(new AxiosError('Logout failed', 'ERR_BAD_REQUEST', config, undefined, response))
        }
      })
    }
    if (config.url === '/api/auth/login') {
      return Promise.resolve({
        data: { success: true, token: nextToken, user: nextUser },
        status: 200, statusText: 'OK', headers: {}, config,
      })
    }
    throw new Error(`Unexpected request: ${config.url}`)
  }
})

afterEach(() => {
  axios.defaults.adapter = originalAdapter
  vi.unstubAllGlobals()
})

it.each([200, 500])('clears the owning session after logout status %s', async status => {
  const store = useAuthStore()
  const pending = store.logout()
  await vi.waitFor(() => expect(logoutConfig).toBeDefined())
  expect(logoutConfig?.headers.Authorization).toBe('Bearer old-token')
  finishLogout(status)
  await pending
  expect(store.isLoggedIn).toBe(false)
  expect(getToken()).toBe('')
  expect(getUser()).toBeNull()
})

it.each([200, 401, 500])('preserves a new login when old logout returns %s', async status => {
  const store = useAuthStore()
  const pending = store.logout()
  await vi.waitFor(() => expect(logoutConfig).toBeDefined())
  expect(await store.login('next-user', 'synthetic-password')).toEqual({ success: true })
  finishLogout(status)
  await pending
  expect(store.token).toBe('next-token')
  expect(store.user).toEqual(nextUser)
  expect(getToken()).toBe('next-token')
  expect(getUser()).toEqual(nextUser)
  expect(window.location.href).toBe('/workspace')
})

it('pins the old token before asynchronous request interceptors can see a replacement', async () => {
  const store = useAuthStore()
  const pending = store.logout()
  setToken('replacement-token')
  setUser(nextUser)
  await vi.waitFor(() => expect(logoutConfig).toBeDefined())
  finishLogout()
  await pending
  expect(logoutConfig?.headers.Authorization).toBe('Bearer old-token')
  expect(getToken()).toBe('replacement-token')
  expect(getUser()).toEqual(nextUser)
})

it('preserves a successful new login even if the server returns the same token', async () => {
  const store = useAuthStore()
  const pending = store.logout()
  await vi.waitFor(() => expect(logoutConfig).toBeDefined())
  nextToken = 'old-token'
  await store.login('next-user', 'synthetic-password')
  finishLogout()
  await pending
  expect(store.isLoggedIn).toBe(true)
  expect(store.user).toEqual(nextUser)
  expect(getToken()).toBe('old-token')
  expect(getUser()).toEqual(nextUser)
})
