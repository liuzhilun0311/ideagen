import axios from 'axios'
import { API_BASE_URL } from './client'
import { normalizeApiError } from '../utils/errors'

export type ProcessingStrength = 'light' | 'medium' | 'heavy'
export type ProcessingVersion = 'original' | 'processed'

export interface ProcessingPage {
  index: number
  source_revision: string
  original_url: string
  processed_url: string | null
  strength: ProcessingStrength | null
  status: 'idle' | 'queued' | 'processing' | 'done' | 'error'
  error: string
  adopted: ProcessingVersion
}

export interface ProcessingState {
  success: boolean
  preferences: { automatic: boolean; strength: ProcessingStrength }
  pages: ProcessingPage[]
}

export type ProcessingAction =
  | { action: 'process'; indices: number[]; strength: ProcessingStrength; force: boolean }
  | { action: 'adopt'; index: number; version: ProcessingVersion; source_revision: string }
  | { action: 'preferences'; automatic: boolean; strength: ProcessingStrength }

async function request(recordId: string, action?: ProcessingAction): Promise<ProcessingState> {
  const url = `${API_BASE_URL}/postprocessing/${encodeURIComponent(recordId)}`
  try {
    const response = action
      ? await axios.post(url, action, { timeout: 15000 })
      : await axios.get(url, { timeout: 15000 })
    if (!response.data.success) throw response.data.error || response.data.error_message || '图片后处理请求失败'
    return response.data
  } catch (cause) {
    if (axios.isAxiosError(cause)) throw normalizeApiError(cause, '图片后处理请求失败')
    throw cause
  }
}

export const getProcessingState = (recordId: string) => request(recordId)
export const updatePostprocessing = (recordId: string, action: ProcessingAction) => request(recordId, action)
