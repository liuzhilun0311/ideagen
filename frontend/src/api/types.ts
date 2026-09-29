import type { AppError } from '../utils/errors'
import type { GrowthGoal, GrowthRecommendation, PublishingPlatform } from '../features/generationOptions'
import type { ImageStyle, StyleRecommendation } from '../features/styles/catalog'

export interface Page {
  layout?: string
  visual_focus?: string
  reference_notes?: string
  index: number
  type: 'cover' | 'content' | 'summary' | 'infographic'
  content: string
}

export interface GenerationRecommendation {
  platform?: PublishingPlatform
  goal?: GrowthGoal
  [key: string]: string | undefined
}

export interface OutlineResponse {
  requested_preferences?: import('../features/generationOptions').OutlinePreferences
  generation_record?: import('./outline').OutlineRun
  copy_preferences?: import('../features/copyOptions').CopyPreferences
  generation_preferences?: import('../features/generationOptions').OutlinePreferences
  organization?: string
  style_recommendation?: StyleRecommendation
  generation_recommendation?: GenerationRecommendation
  growth_recommendation?: GrowthRecommendation
  generation_audit?: GenerationAudit
  success: boolean
  outline?: string
  pages?: Page[]
  error?: AppError | string
  error_message?: string
}

export interface ProgressEvent {
  index: number
  status: 'generating' | 'done' | 'error'
  current?: number
  total?: number
  image_url?: string
  message?: string
  error?: AppError | string
  retryable?: boolean
}

export interface FinishEvent {
  success: boolean
  task_id: string
  images: string[]
  total?: number
  completed?: number
  failed?: number
  failed_indices?: number[]
  cached?: boolean
}

export type HistorySource = 'shared'

export interface HistoryPermissions {
  owner?: { id: string; username: string }
  can_edit?: boolean
  can_share?: boolean
  is_shared?: boolean
  shared_count?: number
}

export interface HistoryRecord extends HistoryPermissions {
  id: string
  title: string
  created_at: string
  updated_at: string
  status: string
  thumbnail: string | null
  page_count: number
  task_id: string | null
  adopted_thumbnail_url?: string | null
}

export interface HistoryDetail extends HistoryPermissions {
  image_style?: ImageStyle
  generation_audit?: GenerationAudit
  id: string
  title: string
  created_at: string
  updated_at: string
  outline: {
    creation_inputs?: import('../features/creationInputs').CreationInputs
    requested_preferences?: import('../features/generationOptions').OutlinePreferences
    copy_preferences?: import('../features/copyOptions').CopyPreferences
    generation_preferences?: import('../features/generationOptions').OutlinePreferences
    generation_record_id?: string
    diagnostic_record_id?: string
    growth_recommendation?: GrowthRecommendation
    organization?: string
    raw: string
    pages: Page[]
  }
  images: {
    task_id: string | null
    generated: string[]
  }
  status: string
  thumbnail: string | null
  content?: {
    diagnostic_record_id?: string
    source?: { topic: string; outline: string }
    titles: string[]
    selected_title_index?: number
    copywriting: string
    tags: string[]
  }
  analysis_snapshots?: ImageAnalysisSnapshot[]
}

export interface ImageAnalysisSnapshot {
  analysis_id?: string
  parts: Array<'content' | 'layout' | 'visual_style'>
  mode: 'merge' | 'replace'
  content: Record<string, unknown>
  layout: Record<string, unknown>
  visual_style: Record<string, unknown>
}

export interface PromptAuditEntry {
  phase: 'outline' | 'copy' | 'image' | string
  prompt_name?: string
  used_fields?: string[]
  rules?: string[]
  created_at?: string
  [key: string]: unknown
}

export interface GenerationAuditEffective {
  platform?: PublishingPlatform | string
  goal?: GrowthGoal | string
  layout?: string
  image_style?: string | ImageStyle
  auto_recommended?: boolean
  [key: string]: unknown
}

export interface GenerationAudit {
  context?: Record<string, unknown>
  effective?: GenerationAuditEffective
  prompts?: PromptAuditEntry[]
  [key: string]: unknown
}

export interface CreateHistoryParams {
  topic: string
  outline: { raw: string; pages: Page[] }
  task_id?: string
  generation_audit?: GenerationAudit
}

export interface UpdateHistoryParams {
  structure_change?: {
    expected_outline: { raw: string; pages: Page[] }
    outline: { raw: string; pages: Page[] }
  }
  image_style?: ImageStyle
  title?: string
  outline?: { raw: string; pages: Page[] }
  images?: { task_id: string | null; generated: string[] }
  status?: string
  thumbnail?: string
  content?: { titles: string[]; selected_title_index?: number; copywriting: string; tags: string[]; source?: { topic: string; outline: string } }
  analysis_snapshots?: ImageAnalysisSnapshot[]
  generation_audit?: GenerationAudit
}

export interface Config {
  text_generation: {
    active_provider: string
    providers: Record<string, any>
  }
  image_generation: {
    active_provider: string
    providers: Record<string, any>
  }
}

export interface ContentResponse {
  generation_record?: { id: string; status: string }
  validation?: { body_characters: number; warnings: string[]; semantic_verified: boolean; facts_verified: boolean }
  success: boolean
  titles?: string[]
  copywriting?: string
  tags?: string[]
  error?: AppError | string
  error_message?: string
}
