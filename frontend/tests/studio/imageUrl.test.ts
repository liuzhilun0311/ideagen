import { afterEach, describe, expect, it, vi } from 'vitest'
import { getOriginalImageUrl, isAuthenticatedImageUrl, withImageToken } from '../../src/utils/imageUrl'
import { withToken } from '../../src/api/image'
import { setToken } from '../../src/api/token'

const base = 'https://studio.example/result'
const token = 'session /+?&'

afterEach(() => vi.unstubAllGlobals())

describe('original image URLs', () => {
  it('preserves same-origin query values and fragment while requesting the original', () => {
    const result = new URL(getOriginalImageUrl('/api/images/task/0.png?thumbnail=true&v=2&label=a%20b#page', token, base))
    expect(result.origin).toBe('https://studio.example')
    expect(result.searchParams.get('thumbnail')).toBe('false')
    expect(result.searchParams.get('v')).toBe('2')
    expect(result.searchParams.get('label')).toBe('a b')
    expect(result.searchParams.get('token')).toBe(token)
    expect(result.hash).toBe('#page')
  })

  it('replaces duplicate thumbnail and stale token values without duplicating them', () => {
    const result = new URL(getOriginalImageUrl('/api/images/task/0.png?thumbnail=true&thumbnail=true&token=old', token, base))
    expect(result.searchParams.getAll('thumbnail')).toEqual(['false'])
    expect(result.searchParams.getAll('token')).toEqual([token])
  })

  it('does not add a token to other same-origin paths', () => {
    const result = new URL(getOriginalImageUrl('/assets/photo.png?size=large', token, base))
    expect(result.searchParams.get('thumbnail')).toBe('false')
    expect(result.searchParams.get('size')).toBe('large')
    expect(result.searchParams.has('token')).toBe(false)
  })

  it('works without a token and is idempotent', () => {
    const result = getOriginalImageUrl('/api/images/task/0.png', '', base)
    expect(new URL(result).searchParams.has('token')).toBe(false)
    expect(getOriginalImageUrl(result, '', base)).toBe(result)
  })

  it.each([
    'https://cdn.example/photo.png?signature=A%2fb+%20&thumbnail=true#part',
    '//cdn.example/api/images/task/0.png?signature=unchanged',
    'https://studio.example:8443/api/images/task/0.png',
    'http://studio.example/api/images/task/0.png',
    'https://studio.example.evil.test/api/images/task/0.png',
    'https://studio.example@evil.test/api/images/task/0.png',
    'data:image/png;base64,AAAA',
    'blob:https://studio.example/image-id',
    'https://[invalid',
    '',
  ])('leaves external, opaque or invalid URL untouched: %s', url => {
    expect(getOriginalImageUrl(url, token, base)).toBe(url)
    expect(withImageToken(url, token, base)).toBe(url)
    expect(isAuthenticatedImageUrl(url, base)).toBe(false)
  })
})

describe('image authentication boundary', () => {
  it.each([
    '/api/images/task/0.png',
    'https://studio.example/api/images/task/0.png',
    '//studio.example/api/images/task/0.png',
    './api/images/task/0.png',
    '/api/postprocessing/images/result-id.png',
    '/api/image-candidates/work-id/candidate-id/image',
  ])('accepts same-origin image endpoint: %s', url => {
    expect(isAuthenticatedImageUrl(url, base)).toBe(true)
  })

  it.each([
    '/api/images-other/task/0.png',
    '/api/images',
    '/api/images/../../other.png',
    '/assets/photo.png',
    '/api/deai/images/task/0.png',
    '/api/postprocessing/images-other/result.png',
    '/api/postprocessing/images/../../other.png',
    '/api/image-candidates/work-id',
    '/api/image-candidates/work-id/candidate-id/adopt',
    '/api/image-candidates/work-id/candidate-id/image/other',
    'https://cdn.example/api/image-candidates/work-id/candidate-id/image',
    'https://user:password@studio.example/api/images/task/0.png',
  ])('does not authenticate other paths or credentialed URLs: %s', url => {
    expect(isAuthenticatedImageUrl(url, base)).toBe(false)
    expect(withImageToken(url, token, base)).toBe(url)
  })
})

describe('withToken compatibility', () => {
  it('authenticates candidate previews through the actual image wrapper', () => {
    vi.stubGlobal('window', { location: { href: base } })
    setToken(token)
    const url = '/api/image-candidates/work-id/candidate-id/image'
    expect(withToken(url)).toBe(`${url}?token=${encodeURIComponent(token)}`)
  })
  it('authenticates processed images without losing their revision', () => {
    const url = '/api/postprocessing/images/result.png?v=3'
    expect(withImageToken(url, token, base)).toContain('&token=')
    expect(new URL(getOriginalImageUrl(url, token, base)).searchParams.get('v')).toBe('3')
    expect(new URL(getOriginalImageUrl(url, token, base)).searchParams.get('token')).toBe(token)
  })
  it('preserves relative paths, query encoding and fragment position', () => {
    vi.stubGlobal('window', { location: { href: base } })
    setToken(token)
    expect(withToken('/api/images/task/0.png?label=a%20b#part'))
      .toBe(`/api/images/task/0.png?label=a%20b&token=${encodeURIComponent(token)}#part`)
    expect(withToken('./api/images/task/0.png'))
      .toBe(`./api/images/task/0.png?token=${encodeURIComponent(token)}`)
  })

  it('does not duplicate an existing token or confuse a token-like key with one', () => {
    expect(withImageToken('/api/images/task/0.png?token=existing', token, base))
      .toBe('/api/images/task/0.png?token=existing')
    expect(withImageToken('/api/images/task/0.png?other_token=value', token, base))
      .toBe(`/api/images/task/0.png?other_token=value&token=${encodeURIComponent(token)}`)
  })

  it('does not authenticate external URLs through the API wrapper', () => {
    vi.stubGlobal('window', { location: { href: base } })
    setToken(token)
    const url = 'https://cdn.example/api/images/task/0.png?signature=A%2fb+%20'
    expect(withToken(url)).toBe(url)
  })

  it('does not add anything without a token or a known base URL', () => {
    expect(withImageToken('/api/images/task/0.png', '', base)).toBe('/api/images/task/0.png')
    expect(withImageToken('/api/images/task/0.png', token, '')).toBe('/api/images/task/0.png')
    expect(getOriginalImageUrl('/api/images/task/0.png', token, '')).toBe('/api/images/task/0.png')
  })
})
