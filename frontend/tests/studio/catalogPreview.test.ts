import { expect, it } from 'vitest'
import { fallbackItems, layoutPreviewUrl, layoutPreviewLabel } from '../../src/features/promptCatalog'
import { stylePreviewUrl, stylePreviewLabel } from '../../src/features/styles/catalog'

it('exposes stable growth layout IDs and metadata-rich fallback entries', () => {
  const layouts = fallbackItems('image.layout')
  const ids = new Set(layouts.map(item => item.id))
  expect(ids.has('image.layout.hook-cover')).toBe(true)
  expect(ids.has('image.layout.pain-solution')).toBe(true)
  expect(ids.has('image.layout.comment-proof')).toBe(true)
  expect(ids.has('image.layout.cta')).toBe(true)
  expect(layouts.find(item => item.id === 'image.layout.hook-cover')?.metadata).toMatchObject({
    platforms: expect.any(Array),
    goals: expect.any(Array),
    aspect_ratios: expect.any(Array),
    text_density: expect.any(String),
    summary: expect.any(String),
    preview: expect.any(String),
  })
})

it('uses a stable layout preview path and a clear missing-image placeholder label', () => {
  expect(layoutPreviewUrl({ preview: 'hook-cover' })).toBe('/assets/layouts/hook-cover.png')
  expect(layoutPreviewUrl({ preview: '' })).toBe('')
  expect(layoutPreviewLabel({ name: '案例拆解', metadata: { preview: '' } })).toBe('暂无样图')
})

it('keeps complete preview metadata for every offline layout option', () => {
  const layouts = fallbackItems('image.layout')
  expect(layouts.length).toBeGreaterThanOrEqual(24)
  for (const item of layouts) {
    expect(item.metadata).toMatchObject({
      preview: expect.any(String),
      preview_alt: expect.any(String),
      summary: expect.any(String),
    })
  }
})

it('resolves built-in style previews and keeps custom reference assets first', () => {
  expect(stylePreviewUrl({ preview: 'photography' })).toEqual({
    url: '/assets/styles/photography.png',
    source: 'builtin',
  })
  expect(stylePreviewUrl({ preview: 'photography', reference_asset_id: 'asset-42' })).toEqual({
    url: expect.stringContaining('/api/reference-assets/images/asset-42'),
    source: 'custom',
  })
  expect(stylePreviewLabel({ name: '自定义风格', metadata: { preview: '', reference_asset_id: 'asset-42' } })).toBe('用户参考图')
})

it('returns an explicit missing-image state instead of a broken URL', () => {
  expect(stylePreviewUrl({ preview: '' })).toEqual({ url: '', source: 'missing' })
  expect(stylePreviewLabel({ name: '无样图风格', metadata: { preview: '' } })).toBe('暂无样图')
})
