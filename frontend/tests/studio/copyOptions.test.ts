import { expect, it } from 'vitest'
import { copyPreferences, recommendCopyPreferences, resolveCopyPreferences, selectCopyPreference } from '../../src/features/copyOptions'

it('defaults legacy works and preserves explicit copy settings', () => {
  expect(copyPreferences()).toEqual({ style: '自动', structure: '自动', length: '适中', emoji_level: '克制' })
  expect(copyPreferences({ style: '简洁干货', structure: '要点清单', length: '简短' }))
    .toEqual({ style: '简洁干货', structure: '要点清单', length: '简短', emoji_level: '克制' })
})

it('refreshes automatic recommendations and follows the outline structure', () => {
  const first = recommendCopyPreferences(undefined, { copy_style: '自然分享', copy_length: '简短', emoji_level: '无', copy_structure: '要点清单' })
  const restored = copyPreferences(JSON.parse(JSON.stringify(first)))
  const next = recommendCopyPreferences(restored, { copy_style: '专业科普', copy_length: '详细', emoji_level: '丰富' })
  expect(next).toMatchObject({ style: '专业科普', structure: '自动', length: '详细', emoji_level: '丰富' })
  expect(resolveCopyPreferences(next)).toEqual({ style: '专业科普', structure: '自动', length: '详细', emoji_level: '丰富' })
})

it('preserves manual fields individually and allows returning to the latest recommendation', () => {
  let value = recommendCopyPreferences(undefined, { copy_style: '自然分享', copy_length: '简短', emoji_level: '无' })
  value = selectCopyPreference(value, 'length', '适中')
  value = selectCopyPreference(value, 'structure', '步骤说明')
  value = recommendCopyPreferences(value, { copy_style: '专业科普', copy_length: '详细', emoji_level: '丰富' })
  expect(value).toMatchObject({ style: '专业科普', structure: '步骤说明', length: '适中', emoji_level: '丰富' })
  expect(selectCopyPreference(value, 'length', '__auto__')).toMatchObject({ length: '详细', modes: { length: 'auto' } })
  expect(selectCopyPreference(value, 'structure', '自动')).toMatchObject({ structure: '自动', modes: { structure: 'auto' } })
})

it('does not make untouched defaults manual when editing a single field', () => {
  const selected = selectCopyPreference(undefined, 'style', '自然分享')
  const next = recommendCopyPreferences(selected, { copy_style: '专业科普', copy_length: '详细', emoji_level: '丰富' })
  expect(next).toMatchObject({ style: '自然分享', length: '详细', emoji_level: '丰富' })
})

it('clears obsolete automatic recommendations when new ones are missing or invalid', () => {
  const previous = recommendCopyPreferences(undefined, { copy_style: '专业科普', copy_length: '详细', emoji_level: '丰富' })
  expect(recommendCopyPreferences(previous, { copy_style: 'invalid', emoji_level: 'invalid' }))
    .toMatchObject({ style: '自动', structure: '自动', length: '适中', emoji_level: '克制' })
})
