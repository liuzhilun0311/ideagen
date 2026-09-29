import { describe, expect, it } from 'vitest'
import { isReferenceDocument } from '../../src/features/referenceDocument'

describe('reference document input', () => {
  it('accepts Word and Markdown extensions only', () => {
    expect(isReferenceDocument(new File(['# note'], 'note.md', { type: 'text/markdown' }))).toBe(true)
    expect(isReferenceDocument(new File([''], 'note.docx'))).toBe(true)
    expect(isReferenceDocument(new File([''], 'note.pdf'))).toBe(false)
  })
})
