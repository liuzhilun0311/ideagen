import { authHeaders } from '../api/client'
import { getToken } from '../api/token'
import { getOriginalImageUrl, isAuthenticatedImageUrl } from './imageUrl'

export type DownloadVersion = 'processed' | 'original' | 'both'
export type DownloadFormat = 'directory' | 'zip'
export interface DownloadLocation {
  directoryName: string
  relativePath: string
}
export interface DownloadPage {
  index: number
  original_url: string
  processed_url?: string | null
}
export interface DownloadFile {
  index: number
  version: 'original' | 'processed'
  url: string
  name: string
}
export interface DownloadDirectory {
  readonly name?: string
  getDirectoryHandle(name: string, options: { create: boolean }): Promise<DownloadDirectory>
  getFileHandle(name: string, options: { create: boolean }): Promise<{
    createWritable(): Promise<{ write(data: Blob): Promise<void>; close(): Promise<void>; abort(): Promise<void> }>
  }>
}

export function compatibleTextSymbols(text: string): string {
  // Avoid combining keycap sequences in TXT; keep Chinese and other emoji unchanged.
  return text.replace(/([0-9#*])[\uFE0E\uFE0F]?\u20E3/g, (_, symbol: string) =>
    /^[0-9]$/.test(symbol) ? '⓪①②③④⑤⑥⑦⑧⑨'[Number(symbol)]! : symbol)
}

export async function chooseDownloadDirectory(): Promise<DownloadDirectory | null | 'cancelled'> {
  const picker = (window as Window & { showDirectoryPicker?: (options: { mode: string }) => Promise<DownloadDirectory> }).showDirectoryPicker
  if (!picker) return null
  try { return await picker.call(window, { mode: 'readwrite' }) }
  catch (error) {
    return error instanceof Error && error.name === 'AbortError' ? 'cancelled' : null
  }
}

export function prepareImageDownload(pages: DownloadPage[], version: DownloadVersion = 'processed') {
  const files: DownloadFile[] = []
  const missing: number[] = []
  for (const page of pages) {
    if (version !== 'processed' && page.original_url) {
      files.push({ index: page.index, version: 'original', url: page.original_url, name: `original/page_${page.index + 1}.png` })
    }
    if (version !== 'original') {
      if (page.processed_url) files.push({ index: page.index, version: 'processed', url: page.processed_url, name: `processed/page_${page.index + 1}.png` })
      else missing.push(page.index)
    }
  }
  return { files, missing }
}

export async function fetchDownloadFiles(files: DownloadFile[], stage: (value: string) => void = () => {}) {
  const results: { name: string; blob: Blob }[] = []
  for (const file of files) {
    stage(`正在读取图片 ${results.length + 1}/${files.length}`)
    const url = getOriginalImageUrl(file.url, getToken())
    const authenticated = isAuthenticatedImageUrl(url)
    const response = await fetch(url, {
      headers: authenticated ? authHeaders() : undefined,
      credentials: authenticated ? 'same-origin' : 'omit',
    })
    if (!response.ok) throw new Error(`第 ${file.index + 1} 页读取失败（${response.status}），未完成下载`)
    const blob = await response.blob()
    if (!blob.type.startsWith('image/') || !blob.size) throw new Error(`第 ${file.index + 1} 页返回内容不是图片`)
    const extension = blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png'
    results.push({ name: file.name.replace(/\.png$/, `.${extension}`), blob })
  }
  return results
}

export async function exportImageDownload(options: {
  files: DownloadFile[]
  format?: DownloadFormat
  content?: { titles?: string[]; copywriting?: string; tags?: string[] }
  stage: (value: string) => void
}) {
  if (!options.files.length) throw new Error('没有可下载的图片')
  // Invoke before the first fetch to preserve the click's user activation.
  const format = options.format ?? 'directory'
  const directory = format === 'directory' ? await chooseDownloadDirectory() : null
  if (directory === 'cancelled') return { status: 'cancelled' as const, message: '已取消下载' }
  // Fetch every requested file before producing any archive, so failures cannot look complete.
  const files = await fetchDownloadFiles(options.files, options.stage)
  if (options.content) {
    const { titles = [], copywriting = '', tags = [] } = options.content
    const text = [
      '【标题】', titles.join('\n'), '',
      '【文案】', copywriting, '',
      '【标签】', tags.map(tag => `#${tag.replace(/^#+/, '')}`).join(' '),
    ].join('\n').replace(/\r\n?/g, '\n').replace(/\n/g, '\r\n')
    // Keep the UTF-8 BOM in both directory and ZIP exports for text-editor detection.
    files.push({ name: 'content.txt', blob: new Blob(['\uFEFF', compatibleTextSymbols(text)], { type: 'text/plain;charset=utf-8' }) })
  }
  let fallback = format === 'directory' && !directory ? '当前浏览器无法保存到文件夹，已改为浏览器下载。' : ''
  if (directory) {
    const folderName = `ideagen_${Date.now()}_${crypto.randomUUID().slice(0, 8)}`
    try {
      options.stage('正在保存到文件夹')
      const target = await directory.getDirectoryHandle(folderName, { create: true })
      for (const file of files) {
        const parts = file.name.split('/')
        let parent = target
        for (const part of parts.slice(0, -1)) parent = await parent.getDirectoryHandle(part, { create: true })
        const handle = await parent.getFileHandle(parts.at(-1)!, { create: true })
        const writable = await handle.createWritable()
        try { await writable.write(file.blob); await writable.close() }
        catch (error) { await writable.abort().catch(() => {}); throw error }
      }
      return {
        status: 'saved' as const,
        location: { directoryName: directory.name || '所选文件夹', relativePath: folderName },
        message: `已保存到所选文件夹，共 ${options.files.length} 张图片`,
      }
    } catch {
      fallback = `文件夹写入未完成，已回退浏览器下载。${folderName} 中可能保留部分文件。`
    }
  }
  if (format !== 'zip' && files.length === 1 && !options.content) {
    triggerDownload(files[0]!.blob, files[0]!.name.replace('/', '_'))
    return { status: 'submitted' as const, message: `${fallback}已提交浏览器下载，共 ${options.files.length} 张图片` }
  }
  options.stage('正在打包')
  const { default: JSZip } = await import('jszip')
  const zip = new JSZip()
  for (const file of files) zip.file(file.name, new Uint8Array(await file.blob.arrayBuffer()))
  const blob = await zip.generateAsync({ type: 'blob' })
  triggerDownload(blob, `ideagen_${Date.now()}.zip`)
  return { status: 'submitted' as const, message: `${fallback}已提交浏览器下载，共 ${options.files.length} 张图片` }
}

function triggerDownload(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}
