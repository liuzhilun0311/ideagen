import axios from 'axios'
import { API_BASE_URL } from './client'
import type { ContentResponse } from './types'

export async function generateContent(
  topic: string,
  outline: string,
  promptName?: string,
  signal?: AbortSignal,
  providerName?: string
): Promise<ContentResponse> {
  const response = await axios.post<ContentResponse>(`${API_BASE_URL}/content`, {
    topic,
    outline,
    prompt_name: promptName || '',
    provider_name: providerName || ''
  }, { signal })
  return response.data
}
