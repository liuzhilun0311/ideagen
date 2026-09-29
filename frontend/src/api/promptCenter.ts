import axios from 'axios'
import { API_BASE_URL } from './client'

export type PromptModule = 'outline' | 'image' | 'content'
export type PromptCategory = 'base' | 'organization' | 'audience' | 'tone' | 'layout' | 'style' | 'structure' | 'length'
export type PromptVisibility = 'private' | 'selected' | 'public'
export interface PromptEntry {
  id: string
  module: PromptModule
  category: PromptCategory
  name: string
  description: string
  content: string
  metadata: Record<string, unknown>
  legacy_value?: string | null
  owner_id: string | null
  owner_name: string
  builtin: boolean
  enabled: boolean
  visibility: PromptVisibility
  allowed_users: string[]
  revision: number
  can_edit: boolean
  can_use: boolean
  updated_at?: string
}
export interface PromptDraft {
  id?: string
  revision?: number
  module: PromptModule
  category: PromptCategory
  name: string
  description: string
  content: string
  metadata: Record<string, unknown>
  enabled: boolean
  visibility: PromptVisibility
  allowed_users: string[]
}
export interface PromptOrder { revision: number; ids: string[] }
export interface PromptUser { id: string; username: string }
export interface PromptVersion {
  revision: number
  name?: string
  description?: string
  content?: string
  actor_name?: string
  created_at?: string
  snapshot?: Partial<PromptEntry>
}
interface Result { success: boolean; error_message?: string }
export interface PromptCatalog extends Result {
  entries: PromptEntry[]
  categories: unknown
  orders: Record<string, PromptOrder>
}
const path = `${API_BASE_URL}/prompt-center`
function checked<T extends Result>(data: T): T {
  if (!data.success) throw data
  return data
}
export async function getPromptCatalog(manage = true): Promise<PromptCatalog> {
  return checked((await axios.get<PromptCatalog>(path, { params: manage ? { manage: 1 } : {} })).data)
}
export async function savePromptEntry(draft: PromptDraft): Promise<PromptEntry> {
  return checked((await axios.post<Result & { entry: PromptEntry }>(`${path}/save`, draft)).data).entry
}
export async function copyPromptEntry(id: string): Promise<PromptEntry> {
  return checked((await axios.post<Result & { entry: PromptEntry }>(`${path}/copy`, { id })).data).entry
}
export async function getPromptVersions(id: string): Promise<PromptVersion[]> {
  return checked((await axios.get<Result & { versions: PromptVersion[] }>(`${path}/${encodeURIComponent(id)}/versions`)).data).versions
}
export async function restorePromptEntry(id: string, revision: number, version?: number): Promise<PromptEntry> {
  return checked((await axios.post<Result & { entry: PromptEntry }>(`${path}/restore`, {
    id, revision, ...(version === undefined ? {} : { version }),
  })).data).entry
}
export async function reorderPromptEntries(module: PromptModule, category: PromptCategory, ids: string[], revision: number): Promise<number> {
  return checked((await axios.post<Result & { revision: number }>(`${path}/reorder`, { module, category, ids, revision })).data).revision
}
export async function getPromptUsers(): Promise<PromptUser[]> {
  return checked((await axios.get<Result & { users: PromptUser[] }>(`${path}/users`)).data).users
}

export function promptDraft(entry: PromptEntry): PromptDraft {
  return {
    id: entry.id, revision: entry.revision, module: entry.module, category: entry.category,
    name: entry.name, description: entry.description, content: entry.content,
    metadata: JSON.parse(JSON.stringify(entry.metadata || {})), enabled: entry.enabled,
    visibility: entry.visibility, allowed_users: [...entry.allowed_users],
  }
}
export function promptError(error: unknown): { message: string; conflict: boolean } {
  const value = error as { response?: { status?: number; data?: Result }; error_message?: string; message?: string }
  const conflict = value?.response?.status === 409
  return {
    conflict,
    message: conflict ? '配置已被其他人修改。请重新加载最新版本；未保存的输入仍保留。'
      : value?.response?.data?.error_message || value?.error_message || value?.message || '请求失败，请重试。',
  }
}
