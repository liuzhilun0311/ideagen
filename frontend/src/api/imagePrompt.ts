import axios from 'axios'
import { API_BASE_URL } from './client'
import type { Page } from './types'
import type { StyleChoice } from '../features/styles/catalog'

export interface ImagePromptPreview {
  provider?: { name?: string; model?: string; gpt_images: boolean; quality_applied: boolean }
  prompt: string
  parameters: Record<string, string>
  gpt_images_parameters: { size: string; quality: string; output_format: string; n: number }
  references: { count: number; user_count: number; cover_count: number; mode: string }
}
export async function previewImagePrompt(input: {
  page: Page; topic: string; image_style: StyleChoice
  image_parameters: Record<string, string>; reference_count: number
  record_id?: string | null; use_reference?: boolean
  reference_roles?: string[]
  generation_preferences?: import('../features/generationOptions').OutlinePreferences
  provider_name?: string
}): Promise<ImagePromptPreview> {
  return (await axios.post(`${API_BASE_URL}/image-prompt/preview`, input)).data
}
