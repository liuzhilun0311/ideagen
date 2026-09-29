export function selectedTitleIndex(titles: string[], index: unknown): number {
  return typeof index === 'number' && Number.isInteger(index) && index >= 0 && index < titles.length
    ? index : 0
}

export function selectedTitle(titles: string[], index: unknown): string {
  return titles[selectedTitleIndex(titles, index)] || ''
}

export function publicationText(content: {
  titles: string[]; copywriting: string; tags: string[]
}, index: unknown): string {
  return [
    selectedTitle(content.titles, index).trim(),
    content.copywriting.trim(),
    content.tags.map(tag => `#${tag.replace(/^#/, '')}`).join(' '),
  ].filter(Boolean).join('\n\n')
}
