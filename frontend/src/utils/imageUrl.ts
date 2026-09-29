function browserBaseUrl(): string {
  return typeof window === 'undefined' ? '' : window.location.href
}

function sameOriginUrl(source: string, baseUrl: string): URL | null {
  if (!source || !baseUrl) return null
  try {
    const base = new URL(baseUrl)
    const url = new URL(source, base)
    if (!['http:', 'https:'].includes(url.protocol) || url.origin !== base.origin) return null
    if (url.username || url.password) return null
    return url
  } catch {
    return null
  }
}

/** Only the application's image endpoint may receive a session token. */
export function isAuthenticatedImageUrl(source: string, baseUrl = browserBaseUrl()): boolean {
  const path = sameOriginUrl(source, baseUrl)?.pathname
  return !!path && (
    path.startsWith('/api/images/') ||
    path.startsWith('/api/postprocessing/images/') ||
    path.startsWith('/api/reference-assets/images/') ||
    /^\/api\/image-candidates\/[^/]+\/[^/]+\/image$/.test(path)
  )
}

/** Validate with URL, but retain the server's relative path and query encoding. */
export function withImageToken(source: string, token: string, baseUrl = browserBaseUrl()): string {
  const url = sameOriginUrl(source, baseUrl)
  if (!token || !url || !isAuthenticatedImageUrl(source, baseUrl) || url.searchParams.has('token')) return source
  const hashIndex = source.indexOf('#')
  const path = hashIndex < 0 ? source : source.slice(0, hashIndex)
  const hash = hashIndex < 0 ? '' : source.slice(hashIndex)
  const separator = path.includes('?') ? (/[?&]$/.test(path) ? '' : '&') : '?'
  return `${path}${separator}token=${encodeURIComponent(token)}${hash}`
}

/** External signed URLs are opaque: do not normalize or rewrite them. */
export function getOriginalImageUrl(source: string, token: string, baseUrl = browserBaseUrl()): string {
  const url = sameOriginUrl(source, baseUrl)
  if (!url) return source
  url.searchParams.set('thumbnail', 'false')
  if (token && isAuthenticatedImageUrl(source, baseUrl)) url.searchParams.set('token', token)
  return url.href
}
