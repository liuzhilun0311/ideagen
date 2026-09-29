import { expect, it } from 'vitest'
import { resolveStylePreview, type StyleSample } from '../../src/features/styles/samplePreview'

const sample: StyleSample = {
  id: 'watercolor', direction: 'Watercolor only', model: 'tested-model', quality: 'low',
  width: 1536, height: 2048, generated_at: '2026-09-27T12:00:00Z', review: 'approved',
  url: '/assets/styles/samples/watercolor.webp', thumbnail: '/assets/styles/samples/watercolor-thumb.webp',
}
const entry = {
  id: 'image.style.watercolor', builtin: true, content: sample.direction,
  metadata: { preview: 'comic' },
}

it('resolves reviewed samples by stable ID despite legacy preview metadata', () => {
  expect(resolveStylePreview(entry, [sample])).toMatchObject({
    url: sample.url, thumbnail: sample.thumbnail, source: 'sample', label: '模型实测 · 2K',
  })
})

it('does not claim edited prompts were tested', () => {
  expect(resolveStylePreview({ ...entry, content: 'Different prompt' }, [sample])).toMatchObject({
    source: 'reference', label: '原始预设样图 · 提示词已修改',
  })
})

it('never transfers tested status to a custom copy of a builtin style', () => {
  expect(resolveStylePreview({ ...entry, builtin: false }, [sample]).source).not.toBe('sample')
})

it('prioritizes uploaded reference images over builtin samples', () => {
  const result = resolveStylePreview({ ...entry, metadata: { reference_asset_id: 'asset-123' } }, [sample])
  expect(result.source).toBe('custom')
  expect(result.url).toContain('/api/reference-assets/images/asset-123')
})

it('does not substitute another style for a missing independent preview', () => {
  expect(resolveStylePreview({
    id: 'image.style.gongbi', builtin: true, content: '', metadata: { preview: 'pencil' },
  }, [])).toMatchObject({ url: '', source: 'missing' })
})

it('marks an unsuccessful visual test as pending instead of borrowing a misleading preview', () => {
  expect(resolveStylePreview({
    id: 'image.style.chat-proof', builtin: true, content: '', metadata: { preview: 'minimal' },
  }, [], [{ id: 'chat-proof', reason: 'Missing chat structure' }])).toMatchObject({
    url: '', source: 'missing', label: '样图待校准',
  })
})
