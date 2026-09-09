import axios from 'axios'
import { API_BASE_URL } from './client'
import { getToken } from './token'
import type { AppError } from '../utils/errors'

export interface AuthUser {
  id: string
  username: string
  is_admin: boolean
  created_at?: string
}

export async function register(username: string, password: string): Promise<{
  success: boolean
  user?: AuthUser
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/auth/register`, { username, password })
  return response.data
}

export async function login(username: string, password: string): Promise<{
  success: boolean
  token?: string
  user?: AuthUser
  expires_at?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/auth/login`, { username, password })
  return response.data
}

export async function logout(token: string = getToken()): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  // Global interceptors use the latest token and redirect on 401, which could
  // affect a new session while this old session's logout is still in flight.
  const response = await axios.create().post(`${API_BASE_URL}/auth/logout`, undefined, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    timeout: 10000,
  })
  return response.data
}

export async function getMe(): Promise<{
  success: boolean
  user?: AuthUser | null
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.get(`${API_BASE_URL}/auth/me`)
  return response.data
}

export async function listUsers(): Promise<{
  success: boolean
  users?: AuthUser[]
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.get(`${API_BASE_URL}/auth/users`)
  return response.data
}

export async function changePassword(
  userId: string,
  newPassword: string,
  oldPassword?: string
): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/auth/users/${userId}/password`, {
    new_password: newPassword,
    old_password: oldPassword || '',
  })
  return response.data
}

export async function deleteUser(userId: string): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.delete(`${API_BASE_URL}/auth/users/${userId}`)
  return response.data
}
