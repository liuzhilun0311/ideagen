import axios from 'axios'
import { API_BASE_URL, getApiErrorPayload } from './client'
import type { AppError } from '../utils/errors'

export type AnalysisPart = 'content' | 'layout' | 'visual_style'

export interface ImageAnalysis {
  id: string
  content: Record<string, any>
  layout: Record<string, any>
  visual_style: Record<string, any>
  rewritten_content: string
  user_note?: string
  source_image_available: boolean
  created_at?: string
  updated_at?: string
}

export interface ImageAnalysisResponse {
  success: boolean
  analysis?: ImageAnalysis
  error?: AppError | string
  error_message?: string
}

export interface ApplyImageAnalysisInput {
  parts: AnalysisPart[]
  mode: 'merge' | 'replace'
}

export async function analyzeImage(
  file: File,
  context: { topic?: string; pageContent?: string; saveSource?: boolean; providerName?: string } = {},
  signal?: AbortSignal,
): Promise<ImageAnalysisResponse> {
  const form = new FormData()
  form.append('image', file)
  if (context.topic) form.append('topic', context.topic)
  if (context.pageContent) form.append('page_content', context.pageContent)
  if (context.saveSource) form.append('save_source', '1')
  if (context.providerName) form.append('provider_name', context.providerName)
  try {
    const response = await axios.post<ImageAnalysisResponse>(`${API_BASE_URL}/image-analysis`, form, { signal })
    return response.data
  } catch (error) {
    return { success: false, ...getApiErrorPayload(error, '图片分析失败') }
  }
}

export async function updateImageAnalysis(
  id: string,
  data: Partial<ImageAnalysis> & { user_note?: string },
): Promise<ImageAnalysisResponse> {
  try {
    const response = await axios.put<ImageAnalysisResponse>(`${API_BASE_URL}/image-analysis/${id}`, data)
    return response.data
  } catch (error) {
    return { success: false, ...getApiErrorPayload(error, '保存图片分析失败') }
  }
}

export async function applyImageAnalysis(id: string, input: ApplyImageAnalysisInput) {
  try {
    const response = await axios.post(`${API_BASE_URL}/image-analysis/${id}/apply`, input)
    return response.data as {
      success: boolean
      applied?: { mode: 'merge' | 'replace'; parts: AnalysisPart[]; [key: string]: any }
      error?: AppError | string
      error_message?: string
    }
  } catch (error) {
    return { success: false, ...getApiErrorPayload(error, '应用图片分析失败') }
  }
}

export async function createReferenceAsset(input: {
  analysis_id?: string
  title: string
  content: Record<string, any>
  rewritten_content: string
  user_note?: string
}) {
  try {
    const response = await axios.post(`${API_BASE_URL}/reference-assets`, input)
    return response.data
  } catch (error) {
    return { success: false, ...getApiErrorPayload(error, '保存参考素材失败') }
  }
}

export async function createPromptsFromAnalysis(input: {
  analysis_id: string
  parts: AnalysisPart[]
  names: Record<string, string>
  drafts: Record<string, { content?: string; description?: string }>
}) {
  try {
    const response = await axios.post(`${API_BASE_URL}/prompt-center/from-analysis`, input)
    return response.data
  } catch (error) {
    return { success: false, ...getApiErrorPayload(error, '保存提示词失败') }
  }
}
