import { expect, it } from 'vitest'
import { publicationText, selectedTitleIndex, selectedTitle } from '../../src/utils/publicationContent'

it('uses only the selected title for publication and preserves alternatives', () => {
  const content = { titles: ['First', 'Second'], copywriting: 'Body', tags: ['tag'] }
  expect(publicationText(content, 1)).toBe('Second\n\nBody\n\n#tag')
  expect(content.titles).toEqual(['First', 'Second'])
})

it.each([undefined, null, -1, 99, NaN, 0.5, '1'])('defaults an invalid selection %s to the first title', index => {
  expect(selectedTitleIndex(['First', 'Second'], index)).toBe(0)
  expect(selectedTitle(['First', 'Second'], index)).toBe('First')
})

it('handles empty titles without exporting undefined or duplicate tag prefixes', () => {
  expect(publicationText({ titles: [], copywriting: 'Body', tags: ['#tag'] }, 0)).toBe('Body\n\n#tag')
})
