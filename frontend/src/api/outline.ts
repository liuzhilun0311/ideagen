import axios from 'axios'
import { API_BASE_URL } from './client'
import type { OutlineResponse } from './types'


export async function generateOutline(
  topic: string,
  images?: File[],
  signal?: AbortSignal,
  promptName?: string,
  referenceContent?: string,
  providerName?: string
): Promise<OutlineResponse & { has_images?: boolean }> {
  if (images && images.length > 0) {
    const formData = new FormData()
    formData.append('topic', topic)
    formData.append('prompt_name', promptName || '')
    formData.append('reference_content', referenceContent || '')
    formData.append('provider_name', providerName || '')
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
    { topic, prompt_name: promptName || '', reference_content: referenceContent || '', provider_name: providerName || '' },
    { signal } // ✅ 新增：json请求分支同样加上中断信号
  )
  return response.data
}
