import { describe, expect, it } from 'vitest'
import { mergeAnalysisIntoPage, mergeAnalysisIntoReference, mergeAnalysisIntoStyle, snapshotForAnalysis } from '../../src/features/imageAnalysis'
import type { ImageAnalysis } from '../../src/api/imageAnalysis'

const analysis: ImageAnalysis = {
  id: 'analysis-1',
  content: { summary: '咖啡主题', subjects: ['咖啡杯'], rewrite: '一页关于咖啡的分享' },
  layout: { description: '标题在上，主体居中', prompt_text: '顶部标题，中心主体，四周留白' },
  visual_style: { description: '柔和手绘', prompt_text: '柔和手绘线稿，低饱和色彩' },
  rewritten_content: '一页关于咖啡的分享',
  source_image_available: true,
}

describe('image analysis application', () => {
  it('merges content without removing existing reference text', () => {
    const result = mergeAnalysisIntoReference('已有产品卖点', analysis)
    expect(result).toContain('已有产品卖点')
    expect(result).toContain('咖啡主题')
  })

  it('merges page layout and style independently', () => {
    const page = mergeAnalysisIntoPage({ index: 0, type: 'content', content: '页面' }, analysis)
    const style = mergeAnalysisIntoStyle({ preset: 'auto', notes: '品牌色' }, analysis)
    expect(page.reference_notes).toContain('顶部标题')
    expect(style.notes).toContain('品牌色')
    expect(style.notes).toContain('柔和手绘')
  })

  it('snapshots only selected parts', () => {
    const snapshot = snapshotForAnalysis(analysis, ['layout', 'visual_style'], 'merge')
    expect(snapshot.content).toEqual({})
    expect(snapshot.layout.prompt_text).toContain('顶部标题')
    expect(snapshot.mode).toBe('merge')
  })
})
