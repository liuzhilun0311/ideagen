import axios from 'axios'
import { API_BASE_URL } from './client'
import type { ContentResponse } from './types'

export async function generateContent(
  topic: string,
  outline: string,
  promptName?: string,
  signal?: AbortSignal,
  providerName?: string,
  generationPreferences?: import('../features/generationOptions').OutlinePreferences,
  copyPreferences?: import('../features/copyOptions').CopyPreferences,
): Promise<ContentResponse> {
  const response = await axios.post<ContentResponse>(`${API_BASE_URL}/content`, {
    topic,
    generation_preferences: generationPreferences,
    copy_preferences: copyPreferences,
    outline,
    prompt_name: promptName || '',
    provider_name: providerName || ''
  }, { signal })
  return response.data
}
