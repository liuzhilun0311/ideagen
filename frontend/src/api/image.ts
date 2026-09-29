import axios from 'axios'
import {
  API_BASE_URL,
  readErrorResponse,
  readSseResponse,
  authHeaders
} from './client'
import { getToken } from './token'
import { withImageToken } from '../utils/imageUrl'
import type {
  FinishEvent,
  Page,
  ProgressEvent
} from './types'
import type { AppError } from '../utils/errors'
import type { ImageStyle } from '../features/styles/catalog'

/** Ask the backend to cancel; acknowledgement does not guarantee the upstream request stops billing. */
export async function cancelCurrentGeneration(): Promise<void> {
  const response = await axios.post(`${API_BASE_URL}/generate/cancel`, undefined, { timeout: 10000 })
  if (response.data?.success !== true) throw new Error('服务端未确认取消请求。')
}

export function getImageUrl(taskId: string, filename: string, thumbnail: boolean = true): string {
  const params: string[] = [thumbnail ? 'thumbnail=true' : 'thumbnail=false']
  const token = getToken()
  if (token) params.push(`token=${encodeURIComponent(token)}`)
  return `${API_BASE_URL}/images/${taskId}/${filename}?${params.join('&')}`
}

/**
 * 为后端返回的图片 URL（如 /api/images/<task_id>/<filename>）追加鉴权 token，
 * 因为 <img> 标签无法携带 Authorization 请求头，只能通过 query 参数传 token。
 */
export function withToken(url: string): string {
  return withImageToken(url, getToken())
}

export async function regenerateImage(
  taskId: string,
  page: Page,
  useReference: boolean = true,
  context?: {
    fullOutline?: string
    userTopic?: string
    recordId?: string | null
    imageStyle?: ImageStyle
    referenceRoles?: string[]
    userImages?: File[]
  },
  imagePromptName?: string,
  providerName?: string,
  imageParameters?: Record<string, string>
): Promise<{ success: boolean; index: number; image_url?: string; error?: AppError | string; error_message?: string }> {
  const response = await axios.post(`${API_BASE_URL}/regenerate`, {
    task_id: taskId,
    page,
    use_reference: useReference,
    full_outline: context?.fullOutline,
    user_topic: context?.userTopic,
    record_id: context?.recordId || undefined,
    image_style: context?.imageStyle,
    reference_roles: context?.referenceRoles,
    user_images: context?.userImages ? await Promise.all(context.userImages.map(readFileAsDataUrl)) : undefined,
    image_prompt_name: imagePromptName || '',
    provider_name: providerName || '', image_parameters: imageParameters
  })
  return response.data
}

export async function retryFailedImages(
  taskId: string,
  pages: Page[],
  onProgress: (event: ProgressEvent) => void,
  onComplete: (event: ProgressEvent) => void,
  onError: (event: ProgressEvent) => void,
  onFinish: (event: { success: boolean; total: number; completed: number; failed: number }) => void,
  onStreamError: (error: unknown) => void,
  recordId?: string | null,
  imagePromptName?: string,
  providerName?: string,
  imageStyle?: ImageStyle,
  useCoverAsReference: boolean = true,
  imageParameters?: Record<string, string>
) {
  try {
    const response = await fetch(`${API_BASE_URL}/retry-failed`, {
      method: 'POST',
      headers: authHeaders({
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify({
        task_id: taskId,
        pages,
        record_id: recordId || undefined,
        image_prompt_name: imagePromptName || '',
        provider_name: providerName || '',
        image_style: imageStyle,
        use_reference: useCoverAsReference,
        image_parameters: imageParameters,
      })
    })

    if (!response.ok) {
      throw await readErrorResponse(response, `请求失败：HTTP ${response.status}`)
    }

    await readSseResponse(response, {
      retry_start: (data) => onProgress({ index: -1, status: 'generating', message: data.message }),
      complete: onComplete,
      error: onError,
      retry_finish: onFinish
    })
  } catch (error) {
    onStreamError(error)
  }
}

export async function generateImagesPost(
  pages: Page[],
  taskId: string | null,
  fullOutline: string,
  onProgress: (event: ProgressEvent) => void,
  onComplete: (event: ProgressEvent) => void,
  onError: (event: ProgressEvent) => void,
  onFinish: (event: FinishEvent) => void,
  onStreamError: (error: unknown) => void,
  userImages?: File[],
  userTopic?: string,
  recordId?: string | null,
  force: boolean = false,
  imagePromptName?: string,
  signal?: AbortSignal,
  providerName?: string,
  imageStyle?: ImageStyle,
  useCoverAsReference: boolean = true,
  imageParameters?: Record<string, string>,
  referenceRoles?: string[],
) {
  try {
    const userImagesBase64 = userImages && userImages.length > 0
      ? await Promise.all(userImages.map(readFileAsDataUrl))
      : []

    const response = await fetch(`${API_BASE_URL}/generate`, {
      method: 'POST',
      signal,
      headers: authHeaders({
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify({
        pages,
        task_id: taskId,
        full_outline: fullOutline,
        user_images: userImagesBase64.length > 0 ? userImagesBase64 : undefined,
        user_topic: userTopic || '',
        record_id: recordId || undefined,
        force,
        image_prompt_name: imagePromptName || '',
        provider_name: providerName || '',
        image_style: imageStyle,
        use_reference: useCoverAsReference,
        image_parameters: imageParameters,
        reference_roles: referenceRoles,
      })
    })

    if (!response.ok) {
      throw await readErrorResponse(response, `请求失败：HTTP ${response.status}`)
    }

    await readSseResponse(response, {
      progress: onProgress,
      complete: onComplete,
      error: onError,
      finish: onFinish
    })
  } catch (error) {
    onStreamError(error)
  }
}

export function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}
