import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { imageStyleChanged, normalizeImageStyle, effectiveStyle, imageStyles, styleGroups } from '../../src/features/styles/catalog'
import { useGeneratorStore } from '../../src/stores/generator'
import { useImageRetry } from '../../src/composables/useImageRetry'
import { regenerateImage } from '../../src/api'

vi.mock('../../src/api', () => ({ regenerateImage: vi.fn() }))
beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

it('contains the concrete style catalog and resolves auto without forwarding recommendation text', () => {
  expect(imageStyles.length).toBeGreaterThanOrEqual(43)
  expect(styleGroups.length).toBeGreaterThanOrEqual(6)
  expect(new Set(imageStyles.map(style => style.id)).size).toBe(imageStyles.length)
  const recommendation = { preset: 'ink', reason: '历史', alternatives: ['woodcut', 'modern-chinese'] }
  expect(effectiveStyle({ preset: 'auto', notes: '', recommendation })).toEqual({ preset: 'ink', notes: '' })
  expect(effectiveStyle({ preset: 'clay', notes: '', recommendation })).toEqual({ preset: 'clay', notes: '' })
  expect(imageStyleChanged({ preset: 'auto', notes: '', recommendation, applied: { preset: 'ink', notes: '' } })).toBe(false)
})

it('persists style preferences but clears applied style for a new draft', () => {
  const store = useGeneratorStore()
  store.imageStyle = { preset: 'comic', notes: 'Blue', applied: { preset: 'comic', notes: 'Blue' } }
  store.reset()
  expect(store.imageStyle).toEqual({ preset: 'comic', notes: 'Blue' })
  expect(JSON.parse(localStorage.getItem('generator-state')!).imageStyle).toEqual(store.imageStyle)
})

it('normalizes old works and detects changed choices without generating anything', () => {
  expect(normalizeImageStyle()).toEqual({ preset: 'auto', notes: '' })
  expect(imageStyleChanged({ preset: 'comic', notes: '', applied: { preset: 'comic', notes: '' } })).toBe(false)
  expect(imageStyleChanged({ preset: 'watercolor', notes: '', applied: { preset: 'comic', notes: '' } })).toBe(true)
  expect(regenerateImage).not.toHaveBeenCalled()
})
it('repairs conflicting saved automatic recommendations on reload without overriding manual selections', () => {
  const growth = { platform: 'douyin' as const, goal: 'follow' as const, layout: '清单',
    image_style: 'high-contrast-promo', aspect_ratio: '9:16', content_structure: '重点', reason: '平台适配' }
  localStorage.setItem('generator-state', JSON.stringify({
    outline: { raw: 'Cover', pages: [{ index: 0, type: 'cover', content: 'Cover' }], growth_recommendation: growth },
    imageStyle: { preset: 'auto', notes: '', recommendation: { preset: 'infographic', reason: 'Old', alternatives: [] } },
  }))
  const store = useGeneratorStore()
  expect(effectiveStyle(store.imageStyle).preset).toBe('high-contrast-promo')
  expect(normalizeImageStyle({ preset: 'watercolor', notes: '' }, growth).preset).toBe('watercolor')
})

it('blocks mixed-style single page redraw and preserves existing images', async () => {
  const store = useGeneratorStore()
  store.setOutline('Page', [{ index: 0, type: 'cover', content: 'Page' }])
  store.taskId = 'task'
  store.images = [{ index: 0, status: 'done', url: '/existing.png' }]
  store.imageStyle = { preset: 'watercolor', notes: '', applied: { preset: 'comic', notes: '' } }
  const report = vi.fn()
  await useImageRetry(report).retrySingleImage(0)
  expect(regenerateImage).not.toHaveBeenCalled()
  expect(store.images[0]!.url).toBe('/existing.png')
  expect(report).toHaveBeenCalledWith(expect.objectContaining({ code: 'STYLE_CHANGED' }))
})

it('passes the selected style to a compatible single-page redraw', async () => {
  const store = useGeneratorStore()
  store.setOutline('Page', [{ index: 0, type: 'cover', content: 'Page' }])
  store.taskId = 'task'
  store.imageStyle = { preset: 'comic', notes: 'Blue', applied: { preset: 'comic', notes: 'Blue' } }
  vi.mocked(regenerateImage).mockResolvedValue({ success: true, index: 0, image_url: '/new.png' })
  await useImageRetry(vi.fn()).retrySingleImage(0)
  expect(regenerateImage).toHaveBeenCalledWith(
    'task',
    expect.objectContaining({ index: 0, type: 'cover' }),
    false,
    expect.objectContaining({
      fullOutline: 'Page',
      imageStyle: { preset: 'comic', notes: 'Blue' },
    }),
    '',
    '',
    { resolution: '1K', aspect_ratio: '3:4', quality: 'low', output_format: 'png' },
  )
})
