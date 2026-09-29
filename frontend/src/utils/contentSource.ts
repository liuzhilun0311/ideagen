import type { Page } from '../api/types'

export interface ContentSource {
  topic: string
  outline: string
}

export function contentSource(topic: string, pages: Page[]): ContentSource {
  return {
    topic: topic.trim(),
    outline: pages.map(page => [
      page.content,
      page.reference_notes ? `参考分析：${page.reference_notes}` : '',
    ].filter(Boolean).join('\n')).join('\n\n<page>\n\n'),
  }
}
