import axios from 'axios'
import { API_BASE_URL } from './client'
import type { PromptItem } from './prompts'

export type LibraryResource = 'models' | 'prompts'
export interface LibraryOrder {
  success: boolean
  revision: number
  order: string[]
}
export interface LibraryCopy extends LibraryOrder { created: { id: string; name: string } }
export function libraryItemId(item: Pick<PromptItem, 'is_base' | 'owner_id' | 'name'>): string {
  return JSON.stringify([item.is_base ? 'base' : item.owner_id || '', item.name])
}
function path(resource: LibraryResource, kind: string) {
  return `${API_BASE_URL}/library/${resource}/${encodeURIComponent(kind)}`
}
function checked<T extends LibraryOrder>(data: T): T {
  if (!data.success) throw data
  return data
}
export async function getLibraryOrder(resource: LibraryResource, kind: string) {
  return checked((await axios.get<LibraryOrder>(path(resource, kind))).data)
}
export async function saveLibraryOrder(resource: LibraryResource, kind: string, revision: number, order: string[]) {
  return checked((await axios.post<LibraryOrder>(`${path(resource, kind)}/reorder`, { revision, order })).data)
}
export async function copyLibraryItem(resource: LibraryResource, kind: string, source: string, revision: number, requestId: string) {
  return checked((await axios.post<LibraryCopy>(`${path(resource, kind)}/copy`, {
    source, revision, request_id: requestId,
  })).data)
}
