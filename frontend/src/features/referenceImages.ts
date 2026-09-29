export const MAX_REFERENCE_IMAGE_BYTES = 5 * 1024 * 1024
export const REFERENCE_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export function referenceImageError(file: File): string {
  if (!REFERENCE_IMAGE_TYPES.includes(file.type)) return `${file.name}：仅支持 JPEG、PNG 或 WebP。`
  if (!file.size) return `${file.name}：图片文件为空。`
  if (file.size > MAX_REFERENCE_IMAGE_BYTES) return `${file.name}：文件超过 5 MiB。`
  return ''
}

export function validateReferenceImages(files: File[]) {
  for (const file of files) {
    const error = referenceImageError(file)
    if (error) throw new Error(error)
  }
}
