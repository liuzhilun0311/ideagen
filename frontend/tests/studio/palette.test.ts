import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { paletteColors } from '../../src/features/styles/palette'
import { normalizeImageStyle, resolveImageStyle, styleChoice } from '../../src/features/styles/catalog'

beforeEach(() => setActivePinia(createPinia()))
it('preserves palette through storage normalization and generation resolution', () => {
  const style = { preset: 'infographic', notes: '', palette: { mode: 'auto', recommendation: 'lavender', reason: '知识层级' } }
  expect(normalizeImageStyle(style)).toEqual(style)
  expect(resolveImageStyle(style)).toEqual(style)
  expect(styleChoice(style)).toEqual(style)
  expect(paletteColors(style.palette)?.background).toBe('#F0EAFE')
})
it('manual palette wins over a new recommendation', () => {
  expect(paletteColors({ mode: 'red', recommendation: 'lavender' })?.accent).toBe('#D93737')
})
it('custom colors have valid defaults', () => {
  expect(paletteColors({ mode: 'custom' })).toEqual({
    primary: '#194B8C', background: '#F4F8FF', accent: '#19A7A0',
  })
})
