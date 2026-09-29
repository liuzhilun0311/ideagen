import axios from 'axios'
import { API_BASE_URL } from './client'
import type { StyleChoice } from '../features/styles/catalog'
import { readFileAsDataUrl } from './image'

export interface ImageCandidate {
  id: string
  index: number
  style: StyleChoice
  prompt: string
  provider: string
  status: 'generating' | 'ready' | 'failed'
  image_url: string
  adopted: boolean
  stale: boolean
  created_at: string
}

export async function listCandidates(recordId: string): Promise<ImageCandidate[]> {
  return (await axios.get(`${API_BASE_URL}/image-candidates/${recordId}`)).data.candidates
}

export async function generateCandidate(recordId: string, index: number, style: StyleChoice,
  provider: string, prompt: string, references: File[] = [],
  imageParameters?: Record<string, string>, useReference = false, referenceRoles: string[] = []): Promise<ImageCandidate> {
  return (await axios.post(`${API_BASE_URL}/image-candidates/${recordId}`, {
    request_id: crypto.randomUUID(), index, image_style: style,
    provider_name: provider, image_prompt_name: prompt,
    image_parameters: imageParameters,
    use_reference: useReference,
    reference_roles: [...referenceRoles],
    user_images: await Promise.all(references.map(readFileAsDataUrl)),
  }, { timeout: 0 })).data.candidate
}

export async function adoptCandidate(recordId: string, candidateId: string, expectedFilename: string):
Promise<{ task_id: string; image_url: string; candidate: ImageCandidate }> {
  return (await axios.post(`${API_BASE_URL}/image-candidates/${recordId}/${candidateId}/adopt`, {
    expected_filename: expectedFilename,
  })).data
}
