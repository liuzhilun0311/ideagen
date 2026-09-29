import axios from 'axios'
import { API_BASE_URL } from './client'

export interface GenerationDiagnostic {
  at: string
  event: 'request' | 'response'
  page_index?: number
  provider?: string
  model?: string
  endpoint?: string
  prompt?: string
  prompt_length?: number
  references?: Record<string, unknown>
  parameters?: Record<string, unknown>
  status?: string
  image_bytes?: number
  error?: string
  source?: string
  attempt_id?: string
  generation_id?: string
  http_status?: number
  elapsed_ms?: number
  headers?: Record<string, unknown>
  body?: unknown
}

export async function getGenerationDiagnostics(taskId: string, pageIndex?: number, generationId?: string) {
  const response = await axios.get(`${API_BASE_URL}/diagnostics/${encodeURIComponent(taskId)}`, {
    params: { page_index: pageIndex, generation_id: generationId || undefined, _ts: Date.now() },
    headers: { 'Cache-Control': 'no-cache' },
  })
  return response.data as { success: boolean; task_id: string; events: GenerationDiagnostic[] }
}

export async function getOutlineDiagnostics(recordId: string) {
  const response = await axios.get(
    `${API_BASE_URL}/outline/records/${encodeURIComponent(recordId)}/diagnostics`,
    { headers: { 'Cache-Control': 'no-cache' } },
  )
  return response.data as {
    success: boolean; record_id: string; status: string
    events: GenerationDiagnostic[]; response_available: boolean
  }
}

export async function getContentDiagnostics(recordId: string) {
  const response = await axios.get(
    `${API_BASE_URL}/content/records/${encodeURIComponent(recordId)}/diagnostics`,
    { headers: { 'Cache-Control': 'no-cache' } },
  )
  return response.data as { success: boolean; record_id: string; status: string; events: GenerationDiagnostic[] }
}
