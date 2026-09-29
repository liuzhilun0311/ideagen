import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../../src/stores/generator'
import { outlineRequest } from '../../src/features/outlineRequest'
import { validateReferenceImages, MAX_REFERENCE_IMAGE_BYTES } from '../../src/features/referenceImages'

beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })

it('normalizes home preview and generation without mutating hidden workspace settings', () => {
  const store = useGeneratorStore()
  store.topic = '  Topic  '
  store.referenceContent = ' Source '
  store.outlineOrganization = '步骤教程'
  store.outlineTone = '专业简洁'
  store.outlineAudienceDetail = 'Stale custom reader'
  const input = outlineRequest(store, true)
  expect(input.topic).toBe('Topic')
  expect(input.reference_content).toBe('Source')
  expect(input.preferences).toMatchObject({ organization: '步骤教程', tone: '自动匹配', audience_detail: '' })
  expect(store.outlineOrganization).toBe('步骤教程')
  expect(outlineRequest(store).preferences.organization).toBe('步骤教程')
})

it('validates a custom reader before any request', () => {
  const store = useGeneratorStore()
  store.outlineAudience = '自定义'
  store.outlineAudienceDetail = ' '
  expect(() => outlineRequest(store, true)).toThrow('目标读者')
  store.outlineAudienceDetail = ' Reader '
  expect(outlineRequest(store, true).preferences.audience_detail).toBe('Reader')
})

it('blocks requests with unrestored image references', () => {
  const store = useGeneratorStore()
  store.referenceImageKey = 'missing'
  expect(() => outlineRequest(store, true)).toThrow('尚未恢复')
})

it('accepts unlimited file counts and rejects oversized, empty or wrong-type files', () => {
  const good = new File([new Uint8Array(MAX_REFERENCE_IMAGE_BYTES)], 'photo.png', { type: 'image/png' })
  expect(() => validateReferenceImages([good])).not.toThrow()
  expect(() => validateReferenceImages([new File([good, 'x'], 'large.png', { type: 'image/png' })])).toThrow('5 MiB')
  expect(() => validateReferenceImages([new File([], 'empty.png', { type: 'image/png' })])).toThrow('为空')
  expect(() => validateReferenceImages([new File(['x'], 'doc.txt', { type: 'text/plain' })])).toThrow('仅支持')
  expect(() => validateReferenceImages(Array(101).fill(good))).not.toThrow()
})
