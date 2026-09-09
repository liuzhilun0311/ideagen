import axios from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  createPreviewFixtures, previewDelay, previewImageUrl, previewPages, previewRecord, previewUser,
} from '../preview/fixtures'

function setup(delay = 0) {
  const fixtures = createPreviewFixtures(delay)
  return { ...fixtures, client: axios.create({ adapter: fixtures.adapter }) }
}

afterEach(() => vi.useRealTimers())

describe('isolated management preview', () => {
  it('provides a demonstrative admin and rejects unimplemented requests', async () => {
    const { client, fetch } = setup()
    expect((await client.get('/api/auth/me')).data.user).toEqual(previewUser)
    expect(previewUser).toMatchObject({ username: '开发预览', is_admin: true })
    await expect(client.post('/api/not-implemented')).rejects.toMatchObject({ response: { status: 404 } })
    await expect(client.delete('/api/config')).rejects.toMatchObject({ response: { status: 404 } })
    expect((await fetch('/api/not-implemented')).status).toBe(404)
    expect(localStorage.length).toBe(0)
  })

  it('supports prompt create, edit, sharing, base save and both delete contracts', async () => {
    const { client } = setup()
    for (const kind of ['outline', 'content', 'image']) {
      await client.post('/api/prompts/save', { kind, name: 'Example', content: 'First' })
      await client.post('/api/prompts/save', { kind, name: 'Example', content: 'Updated' })
      await client.post('/api/prompts/base/save', { kind, content: 'New base' })
      await client.post('/api/prompts/admin/users', { kind, name: 'Example', owner_id: previewUser.id, allowed_users: ['演示成员'] })
      const items = (await client.get('/api/prompts')).data.prompts[kind]
      expect(items).toHaveLength(2)
      expect(items[0]).toMatchObject({ is_base: true, content: 'New base', can_edit: true })
      expect(items[1]).toMatchObject({ content: 'Updated', owner_id: previewUser.id, allowed_users: ['演示成员'] })
      items[1].content = 'Client mutation'
      expect((await client.get('/api/prompts')).data.prompts[kind][1].content).toBe('Updated')
      await client.post('/api/prompts/admin/delete', { kind, name: 'Example', owner_id: previewUser.id })
      await client.post('/api/prompts/save', { kind, name: 'Own', content: 'Own content' })
      await client.post('/api/prompts/delete', { kind, name: 'Own' })
      expect((await client.get('/api/prompts')).data.prompts[kind]).toHaveLength(1)
    }
    await expect(client.post('/api/prompts/delete', { kind: 'outline', name: 'Missing' })).rejects.toMatchObject({ response: { status: 404 } })
    expect((await setup().client.get('/api/prompts')).data.prompts.outline[0].content).not.toBe('New base')
  })

  it('saves single providers, masks keys and supports full replacement and sharing', async () => {
    const { client } = setup()
    for (const kind of ['text', 'image']) {
      const section = `${kind}_generation`
      await client.post('/api/config/providers/save', { kind, name: 'added', config: { type: 'image_api', model: 'demo', api_key: 'dummy-preview-key', remark: 'One' } })
      await client.post('/api/config/providers/save', { kind, name: 'added', config: { model: 'edited', api_key: '', remark: 'Two' } })
      await client.post('/api/config/providers/users', { kind, provider_name: 'added', usernames: ['演示成员'] })
      const config = (await client.get('/api/config')).data.config
      expect(config[section].providers.added).toMatchObject({ model: 'edited', remark: 'Two', api_key_masked: 'preview-****', allowed_users: ['演示成员'] })
      expect(config[section].providers.added).not.toHaveProperty('api_key')
      config[section].active_provider = 'added'
      delete config[section].providers[`preview-${kind}`]
      await client.post('/api/config', config)
      expect((await client.get('/api/config')).data.config[section]).toEqual(config[section])
    }
    expect((await setup().client.get('/api/config')).data.config.text_generation.providers).not.toHaveProperty('added')
    expect((await client.post('/api/config/test', { base_url: 'https://must-not-be-called.invalid' })).data.message).toContain('模拟')
  })

  it('creates, resets and deletes mock users without exposing passwords or changing the admin', async () => {
    const { client } = setup()
    const body = { username: 'Temporary', password: 'abcdef' }
    const user = (await client.post('/api/auth/register', body)).data.user
    await expect(client.post('/api/auth/register', body)).rejects.toMatchObject({ response: { status: 400 } })
    await client.post(`/api/auth/users/${user.id}/password`, { new_password: 'updated' })
    const listed = (await client.get('/api/auth/users')).data.users
    expect(listed).toContainEqual(user)
    expect(JSON.stringify(listed)).not.toContain('updated')
    expect((await client.get('/api/auth/me')).data.user).toEqual(previewUser)
    await expect(client.delete(`/api/auth/users/${previewUser.id}`)).rejects.toMatchObject({ response: { status: 400 } })
    await client.delete(`/api/auth/users/${user.id}`)
    expect((await client.get('/api/auth/users')).data.users).not.toContainEqual(user)
    await expect(client.post('/api/auth/login', body)).rejects.toMatchObject({ response: { status: 400 } })
    expect((await setup().client.get('/api/auth/users')).data.users).toHaveLength(2)
  })

  it('keeps distinct works with correct list, detail, filter, pagination and delete shapes', async () => {
    const { client } = setup()
    const first = (await client.post('/api/history', { topic: 'New draft', outline: previewRecord.outline })).data.record_id
    const second = (await client.post('/api/history', { topic: 'Another draft', outline: previewRecord.outline })).data.record_id
    expect(first).not.toBe(second)
    await client.put(`/api/history/${first}`, { title: 'Edited', content: { titles: [], copywriting: 'Searchable copy', tags: [] }, status: 'partial', id: 'must-not-change' })
    const detail = (await client.get(`/api/history/${first}`)).data.record
    expect(detail).toMatchObject({ id: first, title: 'Edited', status: 'partial', images: { task_id: null, generated: [] } })
    expect((await client.get('/api/history/preview-record')).data.record).toEqual(previewRecord)
    const list = (await client.get('/api/history', { params: { page: 1, page_size: 1, status: 'draft' } })).data
    expect(list).toMatchObject({ total: 1, page: 1, page_size: 1, total_pages: 1 })
    expect(list.records[0]).toMatchObject({ id: second, page_count: 3, task_id: null })
    expect(list.records[0]).not.toHaveProperty('outline')
    expect((await client.get('/api/history?page=2&page_size=1')).data.records).toHaveLength(1)
    expect((await client.get('/api/history/search', { params: { keyword: 'searchable' } })).data.records[0].id).toBe(first)
    expect((await client.get('/api/history/stats')).data.by_status).toEqual({ completed: 1, partial: 1, draft: 1 })
    await client.delete(`/api/history/${first}`)
    expect((await client.get(`/api/history/${first}/exists`)).data).toEqual({ exists: false })
    await expect(client.get(`/api/history/${first}`)).rejects.toMatchObject({ response: { status: 404 } })
    expect((await setup().client.get('/api/history/stats')).data.total).toBe(1)
  })
})

describe('delayed generation preview', () => {
  it('bounds query delay and maps only local image API URLs to existing assets', () => {
    expect(previewDelay('')).toBe(1200)
    expect(previewDelay('?delay=nope')).toBe(1200)
    expect(previewDelay('?delay=')).toBe(1200)
    expect(previewDelay('?delay=90000')).toBe(15000)
    expect(previewDelay('?delay=-2')).toBe(0)
    for (const filename of previewRecord.images.generated) {
      const image = previewImageUrl(`/api/images/preview-task/${filename}?thumbnail=true&token=dummy`, 'http://localhost')
      expect(image).toMatch(/^\/assets\/inspiration\//)
      expect(existsSync(resolve('public', image.slice(1)))).toBe(true)
      expect(image).not.toContain('token')
    }
    const external = 'https://other.invalid/api/images/preview-task/0.png'
    expect(previewImageUrl(external, 'http://localhost')).toBe(external)
  })

  it.each(['/api/outline', '/api/content'])('delays %s while management remains usable and supports abort', async path => {
    vi.useFakeTimers()
    const { client } = setup(1200)
    const controller = new AbortController()
    const request = client.post(path, { topic: 'Example' }, { signal: controller.signal })
    const rejected = expect(request).rejects.toSatisfy(axios.isCancel)
    await vi.advanceTimersByTimeAsync(600)
    expect((await client.get('/api/prompts')).data.success).toBe(true)
    controller.abort()
    await rejected
    await vi.runAllTimersAsync()
    expect(vi.getTimerCount()).toBe(0)
    const completed = client.post(path, { topic: 'Example' })
    await vi.advanceTimersByTimeAsync(1200)
    expect((await completed).data).toHaveProperty(path.endsWith('outline') ? 'pages' : 'copywriting')
  })

  it('supports multipart outlines without parsing FormData as JSON', async () => {
    const { client } = setup()
    const form = new FormData()
    form.append('topic', 'Example')
    form.append('images', new Blob(['image']), 'example.png')
    expect((await client.post('/api/outline', form)).data).toMatchObject({ has_images: true, pages: previewPages })
  })

  it('streams requested page indices over time and scan synchronizes completed tasks', async () => {
    vi.useFakeTimers()
    const { client, fetch } = setup(1200)
    const recordId = (await client.post('/api/history', { topic: 'Generated', outline: { raw: 'One', pages: [previewPages[2]] }, task_id: 'custom-task' })).data.record_id
    const response = await fetch(new Request('http://preview.local/api/generate', {
      method: 'POST', body: JSON.stringify({ pages: [previewPages[2]], task_id: 'custom-task' }),
    }))
    const reader = response.body!.getReader()
    const decode = new TextDecoder()
    expect(decode.decode((await reader.read()).value)).toContain('event: progress')
    const next = reader.read()
    let ready = false
    void next.then(() => { ready = true })
    await vi.advanceTimersByTimeAsync(1199)
    expect(ready).toBe(false)
    expect((await client.get('/api/history/stats')).data.total).toBe(2)
    await vi.advanceTimersByTimeAsync(1)
    expect(decode.decode((await next).value)).toContain('"index":2,"status":"done"')
    expect(decode.decode((await reader.read()).value)).toContain('"images":["2.png"]')
    expect((await reader.read()).done).toBe(true)
    expect((await client.post('/api/history/scan-all')).data).toMatchObject({ total_tasks: 2, synced: 2, failed: 0, orphan_tasks: [] })
    expect((await client.get(`/api/history/${recordId}`)).data.record).toMatchObject({ status: 'completed', images: { task_id: 'custom-task', generated: ['2.png'] } })
  })

  it.each(['signal', 'endpoint', 'reader'])('cancels SSE by %s without late completion or pending timers', async mode => {
    vi.useFakeTimers()
    const { client, fetch } = setup(1200)
    const controller = new AbortController()
    const response = await fetch('/api/generate', { method: 'POST', body: JSON.stringify({ pages: previewPages }), signal: controller.signal })
    const reader = response.body!.getReader()
    await reader.read()
    const pending = reader.read()
    const result = mode === 'reader' ? expect(pending).resolves.toMatchObject({ done: true })
      : expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    if (mode === 'signal') controller.abort()
    if (mode === 'endpoint') await client.post('/api/generate/cancel')
    if (mode === 'reader') await reader.cancel()
    await result
    await vi.runAllTimersAsync()
    expect(vi.getTimerCount()).toBe(0)
    expect((await client.post('/api/history/scan-all')).data.total_tasks).toBe(1)
  })

  it('rejects pre-aborted requests and emits the retry finish contract', async () => {
    const { fetch } = setup()
    const controller = new AbortController()
    controller.abort()
    await expect(fetch('/api/generate', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    const response = await fetch('/api/retry-failed', { method: 'POST', body: JSON.stringify({ pages: [previewPages[1]], task_id: 'retry' }) })
    const events = await response.text()
    expect(events).toContain('event: retry_finish')
    expect(events).toContain('"completed":1,"failed":0')
  })
})
