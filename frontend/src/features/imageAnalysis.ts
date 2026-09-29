import type { Page } from '../api'
import type { ImageStyle } from './styles/catalog'
import type { AnalysisPart, ImageAnalysis } from '../api/imageAnalysis'

function appendText(existing: string, next: string): string {
  const left = existing.trim()
  const right = next.trim()
  if (!right) return left
  if (!left) return right
  if (left.includes(right)) return left
  return `${left}\n\n${right}`
}

export function mergeAnalysisIntoReference(existing: string, analysis: ImageAnalysis): string {
  const summary = String(analysis.content.summary || '').trim()
  const subjects = Array.isArray(analysis.content.subjects) ? analysis.content.subjects.join('、') : ''
  const rewrite = String(analysis.rewritten_content || analysis.content.rewrite || '').trim()
  return appendText(existing, [summary, subjects && `视觉主体：${subjects}`, rewrite].filter(Boolean).join('\n'))
}

export function mergeAnalysisIntoPage(page: Page, analysis: ImageAnalysis, mode: 'merge' | 'replace' = 'merge'): Page {
  const layout = String(analysis.layout.prompt_text || analysis.layout.description || '').trim()
  const content = String(analysis.content.rewrite || analysis.content.summary || '').trim()
  const notes = [layout && `参考布局：${layout}`, content && `参考内容：${content}`].filter(Boolean).join('\n')
  return {
    ...page,
    reference_notes: mode === 'replace' ? notes : appendText(page.reference_notes || '', notes),
  }
}

export function mergeAnalysisIntoStyle(style: ImageStyle, analysis: ImageAnalysis, mode: 'merge' | 'replace' = 'merge'): ImageStyle {
  const notes = String(analysis.visual_style.prompt_text || analysis.visual_style.description || '').trim()
  return {
    ...style,
    notes: mode === 'replace' ? notes : appendText(style.notes, notes),
  }
}

export function snapshotForAnalysis(analysis: ImageAnalysis, parts: AnalysisPart[], mode: 'merge' | 'replace') {
  return {
    analysis_id: analysis.id,
    parts: [...parts],
    mode,
    content: parts.includes('content') ? { ...analysis.content } : {},
    layout: parts.includes('layout') ? { ...analysis.layout } : {},
    visual_style: parts.includes('visual_style') ? { ...analysis.visual_style } : {},
  }
}
