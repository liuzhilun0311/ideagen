import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import {
  growthGoals,
  normalizeGrowthGoal,
  normalizePublishingPlatform,
  outlinePreferences,
  publishingPlatforms,
} from '../../src/features/generationOptions'
import { useGeneratorStore } from '../../src/stores/generator'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

it('exposes the platform and growth goal contract', () => {
  expect(publishingPlatforms).toEqual(['auto', 'xiaohongshu', 'douyin', 'wechat', 'multi'])
  expect(growthGoals).toEqual(['auto', 'follow', 'product', 'inquiry', 'conversion', 'brand', 'engagement', 'share'])
})

it('defaults empty platform and goal values to auto', () => {
  expect(normalizePublishingPlatform(undefined)).toBe('auto')
  expect(normalizePublishingPlatform('')).toBe('auto')
  expect(normalizeGrowthGoal(undefined)).toBe('auto')
  expect(normalizeGrowthGoal('')).toBe('auto')
  expect(outlinePreferences({
    outlineOrganization: '自动',
    outlineAudience: '自动判断',
    outlineAudienceDetail: '',
    outlineTone: '自动匹配',
    outlinePageCount: 'auto',
  })).toMatchObject({ platform: 'auto', goal: 'auto' })
})

it('rejects invalid platform and goal values', () => {
  expect(() => normalizePublishingPlatform('weibo')).toThrow()
  expect(() => normalizeGrowthGoal('sales')).toThrow()
})

it('transmits explicitly selected platform and goal values', () => {
  expect(outlinePreferences({
    outlineOrganization: '自动',
    outlineAudience: '自动判断',
    outlineAudienceDetail: '',
    outlineTone: '自动匹配',
    outlinePageCount: 'auto',
    outlinePlatform: 'douyin',
    outlineGoal: 'conversion',
  })).toMatchObject({ platform: 'douyin', goal: 'conversion' })
})

it('persists platform and growth goal selections', () => {
  const store = useGeneratorStore()
  store.outlinePlatform = 'xiaohongshu'
  store.outlineGoal = 'inquiry'
  store.saveToStorage()

  const restored = useGeneratorStore()
  expect(restored.outlinePlatform).toBe('xiaohongshu')
  expect(restored.outlineGoal).toBe('inquiry')
})

it('falls back to auto for legacy storage without platform fields', () => {
  localStorage.setItem('generator-state', JSON.stringify({
    topic: 'Legacy draft',
    outline: { raw: '', pages: [] },
  }))
  const store = useGeneratorStore()
  expect(store.outlinePlatform).toBe('auto')
  expect(store.outlineGoal).toBe('auto')
})
