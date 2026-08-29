interface ImageOpts {
  extraNegative: string
}

export function buildNegativePrompt(_page: unknown, opts: ImageOpts): string {
  const baseNeg = "模糊，低分辨率，变形，丑，水印，文字，签名，黑白，畸形，手指错误，多余肢体"
  return `${baseNeg} ${opts.extraNegative||''}`.trim()
}