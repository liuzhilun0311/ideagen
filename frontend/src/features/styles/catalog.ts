import catalog from '../../../../backend/generation/style_catalog.json'
import { findItem, itemValue, promptItems, resolvePromptValue } from '../promptCatalog'
import { resolveStylePreview } from './samplePreview'
import { referenceAssetImageUrl } from '../../api/referenceAssets'
import type { GrowthRecommendation } from '../generationOptions'
import type { PaletteChoice } from './palette'

export interface StyleChoice {
  preset: string
  notes: string
  palette?: PaletteChoice
}
export interface ImageStyle extends StyleChoice {
  applied?: StyleChoice
  recommendation?: StyleRecommendation
}
export interface StyleRecommendation { preset: string; reason: string; alternatives: string[] }
export interface StyleMetadata {
  platforms?: string[]
  goals?: string[]
  aspect_ratios?: string[]
  text_density?: string
  summary?: string
  media?: string
  mood?: string
  business_use?: string[]
}
export type StylePreviewSource = 'custom' | 'builtin' | 'missing'
export interface StylePreview {
  url: string
  source: StylePreviewSource
}
export const imageStyles = [
  { id: 'auto', name: '自动推荐', detail: '根据主题与大纲推荐', color: '#5b6472', group: '推荐',
    scenes: '由内容决定画风', caution: '生成前解析为具体风格', preview: 'auto', direction: '' },
  ...catalog,
]
export const styleGroups = [...new Set(catalog.map(style => style.group))]
export function stylePreviewUrl(metadata: Record<string, unknown> = {}): StylePreview {
  const referenceAssetId = typeof metadata.reference_asset_id === 'string' ? metadata.reference_asset_id.trim() : ''
  if (referenceAssetId) return { url: referenceAssetImageUrl(referenceAssetId), source: 'custom' }
  const preview = typeof metadata.preview === 'string' ? metadata.preview.trim() : ''
  return preview ? { url: `/assets/styles/${preview}.png`, source: 'builtin' } : { url: '', source: 'missing' }
}
export function stylePreviewLabel(item: { name: string; metadata?: Record<string, unknown> }): string {
  const preview = stylePreviewUrl(item.metadata || {})
  return preview.source === 'custom' ? '用户参考图' : preview.source === 'builtin' ? `${item.name}参考图` : '暂无样图'
}
export function availableImageStyles() {
  return promptItems('image', 'style').map(item => {
    const legacy = imageStyles.find(style => style.id === item.legacyValue)
    const field = (key: string, fallback = '') => typeof item.metadata[key] === 'string' ? item.metadata[key] as string : fallback
    const preview = field('preview', legacy?.preview)
    const previewState = resolveStylePreview(item)
    return {
      id: itemValue(item), catalogId: item.id, name: item.name,
      detail: field('detail', item.description), scenes: field('scenes', item.description),
      group: field('group', '自定义'), color: field('color', '#5b6472'),
      caution: field('caution'), preview,
      previewUrl: previewState.url,
      previewThumbnail: previewState.thumbnail,
      previewLabel: previewState.label,
      previewDetail: previewState.detail,
      previewSource: previewState.source,
      platforms: Array.isArray(item.metadata.platforms) ? item.metadata.platforms.filter(value => typeof value === 'string') : [],
      goals: Array.isArray(item.metadata.goals) ? item.metadata.goals.filter(value => typeof value === 'string') : [],
      aspect_ratios: Array.isArray(item.metadata.aspect_ratios) ? item.metadata.aspect_ratios.filter(value => typeof value === 'string') : [],
      text_density: field('text_density'),
      summary: field('summary'),
      media: field('media'),
      mood: field('mood'),
      business_use: Array.isArray(item.metadata.business_use)
        ? item.metadata.business_use.filter(value => typeof value === 'string') : [],
    }
  })
}
export function normalizeRecommendation(value?: StyleRecommendation): StyleRecommendation | undefined {
  if (!value || typeof value.preset !== 'string' || !value.preset || value.preset === 'auto') return undefined
  return { preset: value.preset, reason: typeof value.reason === 'string' ? value.reason.slice(0, 180) : '',
    alternatives: [...new Set(Array.isArray(value.alternatives) ? value.alternatives : [])]
      .filter(id => typeof id === 'string' && id && id !== 'auto' && id !== value.preset).slice(0, 2) }
}
export function effectiveStyle(value: ImageStyle, recommendation = value.recommendation): StyleChoice {
  const choice = styleChoice(value)
  const items = promptItems('image', 'style')
  const selected = findItem(items, choice.preset)
  if (choice.preset === 'auto' || (selected?.builtin && selected.legacyValue === 'auto')) {
    const concrete = items.filter(item => !(item.builtin && item.legacyValue === 'auto'))
    const item = findItem(concrete, normalizeRecommendation(recommendation)?.preset)
      || findItem(concrete, 'infographic') || concrete[0]
    // An empty ID is an invalid choice, never a fallback to a hidden builtin.
    choice.preset = item ? itemValue(item) : ''
  }
  return choice
}
export function resolveImageStyle(value: ImageStyle, recommendation = value.recommendation): StyleChoice {
  resolvePromptValue('image', 'style', value.preset)
  const choice = effectiveStyle(value, recommendation)
  if (!choice.preset) throw new Error('没有可用的图片风格，请检查提示词管理。')
  resolvePromptValue('image', 'style', choice.preset)
  return choice
}

export function normalizeImageStyle(value?: Partial<ImageStyle> | null, growth?: GrowthRecommendation): ImageStyle {
  const preset = typeof value?.preset === 'string' && value.preset ? value.preset : 'auto'
  const notes = typeof value?.notes === 'string' ? value.notes.slice(0, 600) : ''
  const applied = value?.applied && typeof value.applied.preset === 'string' && value.applied.preset
    ? styleChoice(value.applied) : undefined
  const recommendation = normalizeRecommendation(growth?.image_style ? {
    preset: growth.image_style, reason: growth.reason,
    alternatives: value?.recommendation?.alternatives || [],
  } : value?.recommendation)
  return { preset, notes, ...(value?.palette ? { palette: { ...value.palette } } : {}), ...(applied ? { applied } : {}), ...(recommendation ? { recommendation } : {}) }
}
export function styleChoice(value: ImageStyle): StyleChoice {
  return { preset: value.preset, notes: value.notes.trim(), ...(value.palette ? { palette: { ...value.palette } } : {}) }
}
export function imageStyleChanged(value: ImageStyle): boolean {
  if (!value.applied) return value.preset !== 'auto' || !!value.notes.trim()
  const items = promptItems('image', 'style')
  const current = effectiveStyle(value).preset
  const applied = value.applied.preset
  return (findItem(items, current)?.id || current) !== (findItem(items, applied)?.id || applied)
    || value.notes.trim() !== value.applied.notes.trim()
    || JSON.stringify(value.palette) !== JSON.stringify(value.applied.palette)
}
