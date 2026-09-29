import { afterEach, expect, it, vi } from 'vitest'
import { compatibleTextSymbols, prepareImageDownload, fetchDownloadFiles, chooseDownloadDirectory, exportImageDownload } from '../../src/utils/imageDownload'

const pages = [
  { index: 0, original_url: '/original-0.png', processed_url: '/processed-0.png' },
  { index: 2, original_url: '/original-2.png', processed_url: null },
]

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

const unicodeContent = {
  titles: ['中文标题：春日出发 🥰🪻'],
  copywriting: '① 准备：☕ 🫐\n② 出发 → 👍🏽 ❤️ 👩‍💻\n1️⃣ 留下回忆，家人同行 👨‍👩‍👧‍👦',
  tags: ['中文标签', '#春日🌸'],
}
const expectedContent = [
  '【标题】', unicodeContent.titles[0], '',
  '【文案】', '① 准备：☕ 🫐\n② 出发 → 👍🏽 ❤️ 👩‍💻\n① 留下回忆，家人同行 👨‍👩‍👧‍👦', '',
  '【标签】', '#中文标签 #春日🌸',
].join('\n').replace(/\n/g, '\r\n')

function expectUnicodeBytes(bytes: Uint8Array) {
  expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf])
  expect(new TextDecoder('utf-8', { fatal: true }).decode(bytes)).toBe(expectedContent)
}

it('converts keycap sequences to single-character symbols only for TXT compatibility', () => {
  expect(compatibleTextSymbols('0️⃣1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣ #️⃣ *️⃣'))
    .toBe('⓪①②③④⑤⑥⑦⑧⑨ # *')
  expect(compatibleTextSymbols('1\u20e3 2\ufe0e\u20e3 3\ufe0f\u20e3')).toBe('① ② ③')
  expect(compatibleTextSymbols('📌 1️⃣ 出行：把保护落实到每一次。🚗\n3️⃣ 健康：分清日常预防与异常就医。'))
    .toBe('📌 ① 出行：把保护落实到每一次。🚗\n③ 健康：分清日常预防与异常就医。')
})

it('preserves ordinary numbers, Chinese and all other emoji sequences', () => {
  const text = '2026年9月29日 1234 36.5°C #标签 *正文* ①②③ 🔟 🏠 📌 ❤️ 👍🏽 👩‍💻 👨‍👩‍👧‍👦'
  expect(compatibleTextSymbols(text)).toBe(text)
  expect(compatibleTextSymbols(compatibleTextSymbols('1️⃣ 中文'))).toBe('① 中文')
})

it('preserves Chinese, compound emoji and labeled sections in the saved text bytes', async () => {
  const saved = new Map<string, Blob>()
  const target = {
    name: '中文作品',
    getDirectoryHandle: vi.fn(),
    getFileHandle: vi.fn(async (name: string) => ({
      createWritable: async () => ({
        write: async (blob: Blob) => { saved.set(name, blob) },
        close: vi.fn(), abort: vi.fn(),
      }),
    })),
  }
  target.getDirectoryHandle.mockResolvedValue(target)
  vi.stubGlobal('window', { showDirectoryPicker: vi.fn().mockResolvedValue(target), location: { href: 'http://localhost/' } })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2]), {
    headers: { 'Content-Type': 'image/png' },
  })))
  const result = await exportImageDownload({
    files: prepareImageDownload([pages[0]!], 'original').files,
    content: unicodeContent, stage: vi.fn(),
  })
  expect(result.status).toBe('saved')
  expect(result).toMatchObject({
    location: {
      directoryName: '中文作品',
      relativePath: expect.stringMatching(/^ideagen_\d+_[\da-f-]+$/),
    },
  })
  if (result.status === 'saved') {
    expect(target.getDirectoryHandle).toHaveBeenCalledWith(result.location.relativePath, { create: true })
  }
  expectUnicodeBytes(new Uint8Array(await saved.get('content.txt')!.arrayBuffer()))
  expect(unicodeContent.tags).toEqual(['中文标签', '#春日🌸'])
  expect(unicodeContent.copywriting).toContain('1️⃣ 留下回忆')
})

it.each([false, true])('preserves UTF-8 text and image bytes in ZIP (folder failure: %s)', async folderFailure => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  const target = { getDirectoryHandle: vi.fn().mockRejectedValue(new Error('Disk full')) }
  vi.stubGlobal('window', {
    location: { href: 'http://localhost/' },
    ...(folderFailure ? { showDirectoryPicker: vi.fn().mockResolvedValue(target) } : {}),
  })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2, 3]), {
    headers: { 'Content-Type': 'image/png' },
  })))
  const link = { href: '', download: '', click: vi.fn(), remove: vi.fn() }
  vi.stubGlobal('document', { createElement: vi.fn(() => link), body: { appendChild: vi.fn() } })
  let archive: Blob | undefined
  vi.spyOn(URL, 'createObjectURL').mockImplementation(blob => {
    archive = blob as Blob
    return 'blob:test-export'
  })
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  const result = await exportImageDownload({
    files: prepareImageDownload([pages[0]!], 'original').files,
    content: unicodeContent, stage: vi.fn(),
  })
  expect(result.status).toBe('submitted')
  expect(link.click).toHaveBeenCalledOnce()
  const { default: JSZip } = await import('jszip')
  const zip = await JSZip.loadAsync(await archive!.arrayBuffer())
  expectUnicodeBytes(await zip.file('content.txt')!.async('uint8array'))
  expect([...(await zip.file('original/page_1.png')!.async('uint8array'))]).toEqual([1, 2, 3])
  await vi.runAllTimersAsync()
})

it.each([true, false])('explicit ZIP skips the folder picker even for one image (include content: %s)', async includeContent => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  const picker = vi.fn().mockRejectedValue(new Error('Must not open'))
  vi.stubGlobal('window', { showDirectoryPicker: picker, location: { href: 'http://localhost/' } })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2, 3]), {
    headers: { 'Content-Type': 'image/png' },
  })))
  const link = { href: '', download: '', click: vi.fn(), remove: vi.fn() }
  vi.stubGlobal('document', { createElement: vi.fn(() => link), body: { appendChild: vi.fn() } })
  let archive: Blob | undefined
  vi.spyOn(URL, 'createObjectURL').mockImplementation(blob => {
    archive = blob as Blob
    return 'blob:explicit-zip'
  })
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  const result = await exportImageDownload({
    files: prepareImageDownload([pages[0]!], 'original').files,
    format: 'zip', content: includeContent ? unicodeContent : undefined, stage: vi.fn(),
  })
  expect(picker).not.toHaveBeenCalled()
  expect(result.status).toBe('submitted')
  expect(result.message).not.toContain('回退')
  expect(result.message).not.toContain('无法')
  expect(result).not.toHaveProperty('location')
  expect(link.download).toMatch(/\.zip$/)
  const { default: JSZip } = await import('jszip')
  const zip = await JSZip.loadAsync(await archive!.arrayBuffer())
  expect([...(await zip.file('original/page_1.png')!.async('uint8array'))]).toEqual([1, 2, 3])
  if (includeContent) expectUnicodeBytes(await zip.file('content.txt')!.async('uint8array'))
  else expect(zip.file('content.txt')).toBeNull()
  await vi.runAllTimersAsync()
})

it('falls back when directory picker is unavailable or permission is denied', async () => {
  vi.stubGlobal('window', {})
  expect(await chooseDownloadDirectory()).toBeNull()
  vi.stubGlobal('window', { showDirectoryPicker: vi.fn().mockRejectedValue(new DOMException('Denied', 'SecurityError')) })
  expect(await chooseDownloadDirectory()).toBeNull()
})

it('cancelling the folder picker stops before any image fetch', async () => {
  vi.stubGlobal('window', { showDirectoryPicker: vi.fn().mockRejectedValue(new DOMException('Cancelled', 'AbortError')) })
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  expect(await exportImageDownload({ files: prepareImageDownload(pages).files, stage: vi.fn() })).toEqual({ status: 'cancelled', message: '已取消下载' })
  expect(fetch).not.toHaveBeenCalled()
})

it('opens the picker before fetching and writes separate version folders with content', async () => {
  const write = vi.fn(), close = vi.fn()
  const target = { getDirectoryHandle: vi.fn(), getFileHandle: vi.fn(async () => ({
    createWritable: async () => ({ write, close, abort: vi.fn() }),
  })) }
  target.getDirectoryHandle.mockResolvedValue(target)
  const picker = vi.fn().mockResolvedValue(target)
  vi.stubGlobal('window', { showDirectoryPicker: picker, location: { href: 'http://localhost/' } })
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => {
    expect(picker).toHaveBeenCalledOnce()
    return new Response(new Uint8Array([1]), { headers: { 'Content-Type': 'image/png' } })
  }))
  const result = await exportImageDownload({
    files: prepareImageDownload([pages[0]!], 'both').files,
    content: { copywriting: 'Synthetic content' }, stage: vi.fn(),
  })
  expect(result.status).toBe('saved')
  expect(result.message).toContain('已保存到所选文件夹')
  expect(target.getDirectoryHandle).toHaveBeenCalledWith('original', { create: true })
  expect(target.getDirectoryHandle).toHaveBeenCalledWith('processed', { create: true })
  expect(target.getFileHandle).toHaveBeenCalledWith('content.txt', { create: true })
  expect(write).toHaveBeenCalledTimes(3)
  expect(close).toHaveBeenCalledTimes(3)
})

it('defaults to processed images and never substitutes originals', () => {
  const result = prepareImageDownload(pages)
  expect(result.files).toEqual([{ index: 0, version: 'processed', url: '/processed-0.png', name: 'processed/page_1.png' }])
  expect(result.missing).toEqual([2])
})

it('selects originals explicitly without reporting missing processed versions', () => {
  const result = prepareImageDownload(pages, 'original')
  expect(result.files.map(file => file.url)).toEqual(['/original-0.png', '/original-2.png'])
  expect(result.missing).toEqual([])
})

it('exports both into distinct folders and preserves page indices', () => {
  const result = prepareImageDownload(pages, 'both')
  expect(result.files.map(file => file.name)).toEqual(['original/page_1.png', 'processed/page_1.png', 'original/page_3.png'])
  expect(result.missing).toEqual([2])
})

it('has no output when every requested processed image is missing', () => {
  expect(prepareImageDownload([pages[1]!]).files).toEqual([])
})

it('rejects failed image fetches instead of exporting an error document', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('error', { status: 403 })))
  await expect(fetchDownloadFiles(prepareImageDownload(pages).files)).rejects.toThrow('第 1 页')
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('rejects non-image responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>', { headers: { 'Content-Type': 'text/html' } })))
  await expect(fetchDownloadFiles(prepareImageDownload(pages).files)).rejects.toThrow('不是图片')
})

it('only reads image bytes without submitting processing requests', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2]), { headers: { 'Content-Type': 'image/png' } })))
  const files = await fetchDownloadFiles(prepareImageDownload(pages).files)
  expect(files).toHaveLength(1)
  expect(fetch).toHaveBeenCalledWith('/processed-0.png', expect.not.objectContaining({ method: 'POST' }))
})
