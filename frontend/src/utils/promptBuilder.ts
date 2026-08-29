interface PageItem {
  type: 'cover' | 'content' | 'summary'
  content: string
}
interface ImageOpts {
  style: string
  aspect: string
  extraPositive: string
}

export function buildPrompt(page: PageItem, opts: ImageOpts): string {
  const baseStyle = opts.style || "小红书摄影，高清，氛围感，胶片质感，8k，细节丰富"
  let contentText = page.content
  const prompt = `${contentText}\n${baseStyle}\n${opts.extraPositive || ''}`
  return prompt.trim()
}