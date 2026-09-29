import samples from './samples.json'
import issues from './sampleIssues.json'
import { referenceAssetImageUrl } from '../../api/referenceAssets'

export interface StyleSample {
  id: string
  direction: string
  model: string
  quality: string
  width: number
  height: number
  generated_at: string
  url: string
  thumbnail: string
  review: 'approved'
}

interface PreviewEntry {
  id: string
  builtin: boolean
  legacyValue?: string
  content?: string
  metadata: Record<string, unknown>
}

// Existing independent illustrations remain identifiable as references, not test results.
const referenceFiles = import.meta.glob('/public/assets/styles/*.png')
const references = new Set(Object.keys(referenceFiles).map(path => path.split('/').pop()!.replace('.png', '')))

export function resolveStylePreview(
  entry: PreviewEntry, catalog: StyleSample[] = samples as StyleSample[],
  pending: { id: string; reason: string }[] = issues,
) {
  const asset = entry.metadata.reference_asset_id
  if (typeof asset === 'string' && asset.trim()) {
    const url = referenceAssetImageUrl(asset.trim())
    return { url, thumbnail: url, source: 'custom', label: '用户参考图', detail: '' }
  }
  const external = entry.metadata.preview_url
  if (typeof external === 'string' && /^(\/(?!\/)|https?:\/\/)/.test(external)) {
    return { url: external, thumbnail: external, source: 'custom', label: '参考图片', detail: '' }
  }
  const id = entry.builtin
    ? (entry.id.startsWith('image.style.') ? entry.id.slice('image.style.'.length) : entry.legacyValue || entry.id)
    : ''
  const sample = catalog.find(item => item.id === id && item.review === 'approved')
  if (sample) {
    const matches = typeof entry.content === 'string' && entry.content.trim() === sample.direction.trim()
    return {
      url: sample.url, thumbnail: sample.thumbnail, source: matches ? 'sample' : 'reference',
      label: matches ? '模型实测 · 2K' : '原始预设样图 · 提示词已修改',
      detail: `${sample.model} · ${sample.width} × ${sample.height} · ${sample.generated_at.slice(0, 10)}`,
    }
  }
  const issue = pending.find(item => item.id === id)
  if (issue) return { url: '', thumbnail: '', source: 'missing', label: '样图待校准', detail: issue.reason }
  const preview = typeof entry.metadata.preview === 'string' ? entry.metadata.preview : ''
  const reference = id ? (references.has(id) ? id : '') : (references.has(preview) ? preview : '')
  const url = reference ? `/assets/styles/${reference}.png` : ''
  return { url, thumbnail: url, source: url ? 'reference' : 'missing',
    label: url ? '风格示意 · 非模型实测' : '暂无独立样图', detail: '' }
}
