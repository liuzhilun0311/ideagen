import axios from 'axios'
import { API_BASE_URL } from './client'

export type PromptKind = 'outline' | 'content' | 'image'

export interface PromptItem {
  name: string
  content: string
  type: PromptKind
  is_base: boolean
  /** 是否可编辑/删除（仅拥有者自己的提示词为 true；默认/共享的为 false） */
  can_edit?: boolean
  /** 拥有者用户名 */
  owner?: string | null
  /** 拥有者用户 id */
  owner_id?: string | null
  /** 是否别人共享给我的提示词 */
  is_shared?: boolean
  /** 共享名单（用户名列表，管理员配置） */
  allowed_users?: string[]
}

export interface PromptsResponse {
  success: boolean
  prompts: Record<PromptKind, PromptItem[]>
}

export async function getPrompts(): Promise<PromptsResponse> {
  const response = await axios.get<PromptsResponse>(`${API_BASE_URL}/prompts`)
  return response.data
}

export async function savePrompt(kind: PromptKind, name: string, content: string) {
  const response = await axios.post(`${API_BASE_URL}/prompts/save`, { kind, name, content })
  return response.data
}

export async function deletePrompt(kind: PromptKind, name: string) {
  const response = await axios.post(`${API_BASE_URL}/prompts/delete`, { kind, name })
  return response.data
}

/** 管理员：保存系统默认提示词内容 */
export async function saveBasePrompt(kind: PromptKind, content: string) {
  const response = await axios.post(`${API_BASE_URL}/prompts/base/save`, { kind, content })
  return response.data
}

export async function setPromptUsers(
  ownerId: string,
  kind: PromptKind,
  name: string,
  allowedUsers: string[]
) {
  const response = await axios.post(`${API_BASE_URL}/prompts/admin/users`, {
    owner_id: ownerId,
    kind,
    name,
    allowed_users: allowedUsers
  })
  return response.data
}

export async function adminDeletePrompt(ownerId: string, kind: PromptKind, name: string) {
  const response = await axios.post(`${API_BASE_URL}/prompts/admin/delete`, {
    owner_id: ownerId,
    kind,
    name
  })
  return response.data
}
