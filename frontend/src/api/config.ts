import axios from 'axios'
import { API_BASE_URL } from './client'
import type { Config } from './types'
import type { AppError } from '../utils/errors'

export async function getConfig(): Promise<{
  success: boolean
  config?: Config
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.get(`${API_BASE_URL}/config`)
  return response.data
}

export async function updateConfig(config: Partial<Config>): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/config`, config)
  return response.data
}

export async function testConnection(config: {
  type: string
  provider_name?: string
  api_key?: string
  base_url?: string
  endpoint_type?: string
  model: string
}): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/config/test`, config)
  return response.data
}

/** 管理员：配置某服务商可使用的用户名单（空列表 = 仅管理员可见，不共享） */
export async function setProviderUsers(
  kind: 'text' | 'image',
  providerName: string,
  usernames: string[]
): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/config/providers/users`, {
    kind,
    provider_name: providerName,
    usernames,
  })
  return response.data
}

/** 保存单个服务商配置（只更新这一个，api_key 为空时保留原有，备注 remark 一并保存） */
export async function saveProvider(
  kind: 'text' | 'image',
  name: string,
  config: Record<string, any>
): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/config/providers/save`, {
    kind,
    name,
    config,
  })
  return response.data
}

export interface DeAIInfo {
  deai_script: string
  python_script: string
}

export async function getDeAIInfo(): Promise<{
  success: boolean
  config?: DeAIInfo
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.get(`${API_BASE_URL}/config/deai`)
  return response.data
}

export interface RunDeAIResult {
  success: boolean
  reason?: string
  error_message?: string
  exit_code?: number
  stdout?: string
  stderr?: string
  output_dir?: string
}

export async function runDeAI(taskId: string, strength: 'light' | 'medium' | 'heavy' = 'medium'): Promise<{
  success: boolean
  reason?: string
  error_message?: string
  exit_code?: number
  stdout?: string
  stderr?: string
  output_dir?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/config/deai/run`, { task_id: taskId, strength })
  return response.data
}
