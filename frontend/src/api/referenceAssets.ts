import axios from 'axios'
import { API_BASE_URL, getApiErrorPayload } from './client'
import { withImageToken } from '../utils/imageUrl'
import { getToken } from './token'

export interface ReferenceAsset {
  id: string
  analysis_id?: string | null
  title: string
  content: Record<string, any>
  rewritten_content: string
  user_note: string
  image_url: string
  created_at: string
  updated_at: string
}

export async function listReferenceAssets(): Promise<{
  success: boolean
  assets: ReferenceAsset[]
  error?: string | import('../utils/errors').AppError
  error_message?: string
}> {
  try {
    const response = await axios.get(`${API_BASE_URL}/reference-assets`)
    return { success: true, assets: (response.data.assets || []) as ReferenceAsset[] }
  } catch (error) {
    return { success: false, assets: [] as ReferenceAsset[], ...getApiErrorPayload(error, '获取参考素材失败') }
  }
}

export async function updateReferenceAsset(id: string, data: Partial<ReferenceAsset>) {
  try {
    const response = await axios.put(`${API_BASE_URL}/reference-assets/${id}`, data)
    return response.data
  } catch (error) {
    return { success: false, ...getApiErrorPayload(error, '保存参考素材失败') }
  }
}

export async function deleteReferenceAsset(id: string) {
  try {
    const response = await axios.delete(`${API_BASE_URL}/reference-assets/${id}`)
    return response.data
  } catch (error) {
    return { success: false, ...getApiErrorPayload(error, '删除参考素材失败') }
  }
}

export function referenceAssetImageUrl(asset: Pick<ReferenceAsset, 'image_url'> | string): string {
  const source = typeof asset === 'string' ? `/api/reference-assets/images/${asset}` : asset.image_url
  return withImageToken(source, getToken())
}
