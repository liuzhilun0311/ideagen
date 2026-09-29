import axios from 'axios'
import { API_BASE_URL } from '../api/client'

const MAX_REFERENCE_BYTES = 10 * 1024 * 1024
export const MAX_REFERENCE_TEXT = 100000

export function isReferenceDocument(file: File): boolean {
  return file.name.toLowerCase().endsWith('.md')
    || file.name.toLowerCase().endsWith('.markdown')
    || file.name.toLowerCase().endsWith('.docx')
}

export async function extractReferenceDocument(file: File, signal?: AbortSignal): Promise<string> {
  if (file.name.toLowerCase().endsWith('.doc')) throw new Error('旧版 Word（.doc）请先另存为 .docx 后导入。')
  if (!isReferenceDocument(file)) throw new Error('仅支持 Markdown（.md）或 Word（.docx）文档。')
  if (file.size > MAX_REFERENCE_BYTES) throw new Error('参考文档不能超过 10 MiB。')
  if (file.name.toLowerCase().endsWith('.md') || file.name.toLowerCase().endsWith('.markdown')) {
    const text = (await file.text()).replace(/^\uFEFF/, '').trim()
    if (!text) throw new Error('参考文档为空，请选择有内容的文件。')
    if (text.length > MAX_REFERENCE_TEXT) throw new Error('参考文本超过 100000 字符，请拆分后导入。')
    return text
  }
  const body = new FormData()
  body.append('file', file)
  const { data } = await axios.post(`${API_BASE_URL}/reference-document/import`, body, { signal })
  if (!data.success || typeof data.text !== 'string' || !data.text.trim()) throw new Error('文档没有可提取的文字。')
  return data.text
}
