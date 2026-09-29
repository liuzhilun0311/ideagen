import axios from 'axios'
import { API_BASE_URL } from './client'
import type { OutlineResponse } from './types'
import type { OutlinePreferences } from '../features/generationOptions'

export type OutlinePromptInput = Partial<OutlinePreferences> & {
  topic: string
  reference_content: string
  image_count: number
  reference_roles?: string[]
}

export interface OutlineRun {
  id: string; prompt: string; status: string; sent: boolean; created_at: string
  provider: string; model: string; preferences: OutlinePreferences
  references: { bytes: number; thumbnail: string }[]
}
export async function previewOutlinePrompt(input: OutlinePromptInput) {
  return (await axios.post(`${API_BASE_URL}/outline/preview`, input)).data as { prompt: string }
}
export async function listOutlineRuns(id?: string): Promise<OutlineRun[]> {
  return (await axios.get(`${API_BASE_URL}/outline/records`, { params: { id } })).data.records
}


export async function generateOutline(
  topic: string,
  images?: File[],
  signal?: AbortSignal,
  promptName?: string,
  referenceContent?: string,
  providerName?: string,
  organization: string = '自动',
  preferences?: Partial<OutlinePreferences>,
  referenceRoles: string[] = [],
): Promise<OutlineResponse & { has_images?: boolean }> {
  if (images && images.length > 0) {
    const formData = new FormData()
    formData.append('topic', topic)
    formData.append('prompt_name', promptName || '')
    formData.append('reference_content', referenceContent || '')
    formData.append('provider_name', providerName || '')
    formData.append('organization', organization)
    formData.append('reference_roles', JSON.stringify(referenceRoles))
    if (preferences) Object.entries(preferences).forEach(([key, value]) => formData.set(key, String(value)))
    images.forEach((file) => {
      formData.append('images', file)
    })


    const response = await axios.post<OutlineResponse & { has_images?: boolean }>(
      `${API_BASE_URL}/outline`,
      formData,
      {
        signal, // ✅ 新增：中断信号
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    )
    return response.data
  }


  const response = await axios.post<OutlineResponse>(
    `${API_BASE_URL}/outline`,
    { topic, organization, ...preferences, reference_content: referenceContent || '', reference_roles: referenceRoles, provider_name: providerName || '' },
    { signal } // ✅ 新增：json请求分支同样加上中断信号
  )
  return response.data
}
