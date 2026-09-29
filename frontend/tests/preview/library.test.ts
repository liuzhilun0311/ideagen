import axios, { type AxiosInstance } from 'axios'
import { describe, expect, it } from 'vitest'
import { libraryItemId, type LibraryCopy, type LibraryOrder } from '../../src/api/library'
import type { PromptItem, PromptKind } from '../../src/api/prompts'
import { createPreviewFixtures, previewUser } from './fixtures'

function setup() {
  const fixtures = createPreviewFixtures(0)
  return { ...fixtures, client: axios.create({ adapter: fixtures.adapter }) }
}
const endpoint = (resource: string, kind: string) => `/api/library/${resource}/${kind}`
async function order(client: AxiosInstance, path: string) {
  return (await client.get<LibraryOrder>(path)).data
}
async function copy(client: AxiosInstance, path: string, source: string, requestId = 'copy') {
  const current = await order(client, path)
  const body = { source, revision: current.revision, request_id: requestId }
  return { body, result: (await client.post<LibraryCopy>(`${path}/copy`, body)).data }
}
async function prompts(client: AxiosInstance, kind: PromptKind) {
  return (await client.get<{ prompts: Record<PromptKind, PromptItem[]> }>('/api/prompts')).data.prompts[kind]
}
async function login(client: AxiosInstance, username: string) {
  await client.post('/api/auth/login', { username, password: 'synthetic-only' })
}
const rejected = (status: number) => ({ response: { status } })

describe('preview library API', () => {
  it.each(['text', 'image'] as const)('copies %s model privately, disabled and directly below source', async kind => {
    const { client } = setup()
    const path = endpoint('models', kind)
    const section = `${kind}_generation`
    const source = `preview-${kind}`
    await client.post('/api/config/providers/save', { kind, name: source, config: {
      api_key: 'synthetic-secret-never-returned', api_protocol: 'responses', endpoint_type: '/custom/responses',
      temperature: 0.3, allowed_users: ['演示成员'], remark: 'Keep parameters',
    } })
    const original = (await client.get('/api/config')).data.config[section]
    const { result, body } = await copy(client, path, source)
    expect(result).toMatchObject({ success: true, revision: 1, order: [source, result.created.id] })
    expect(result.created.name).toBe(result.created.id)
    expect(JSON.stringify(result)).not.toContain('synthetic-secret')
    const current = (await client.get('/api/config')).data.config[section]
    expect(current.active_provider).toBe(original.active_provider)
    expect(current.providers[source]).toEqual(original.providers[source])
    expect(current.providers[result.created.id]).toEqual({
      ...original.providers[source], enabled: false, allowed_users: [],
      provider_label: `${source}（副本）`,
      display_name: `${source}（副本）:${original.providers[source].model}`,
    })
    expect(current.providers[result.created.id]).not.toHaveProperty('api_key')
    expect(Object.keys(current.providers)).toEqual(result.order)
    expect((await client.post(`${path}/copy`, body)).data).toEqual(result)
    expect(Object.keys((await client.get('/api/config')).data.config[section].providers)).toHaveLength(2)
    await expect(client.post(`${path}/copy`, { ...body, source: result.created.id })).rejects.toMatchObject(rejected(409))
    await expect(client.post(`${path}/copy`, { ...body, request_id: 'stale' })).rejects.toMatchObject(rejected(409))
    const second = (await copy(client, path, source, 'next-copy')).result
    expect(second.created.id).not.toBe(result.created.id)
    expect(second.order).toEqual([source, second.created.id, result.created.id])
    expect((await order(setup().client, path)).order).toEqual([source])
  })

  it.each(['outline', 'content', 'image'] as const)('copies default %s prompts using stable owner-qualified IDs and preserves base identity', async kind => {
    const { client } = setup()
    const path = endpoint('prompts', kind)
    const base = (await prompts(client, kind))[0]!
    const { result } = await copy(client, path, libraryItemId(base))
    const items = await prompts(client, kind)
    expect(items.map(libraryItemId)).toEqual(result.order)
    expect(items[1]).toMatchObject({
      name: result.created.name, content: base.content, is_base: false, can_edit: true,
      owner_id: previewUser.id, is_shared: false, allowed_users: [],
    })
    expect(result.created.id).toBe(libraryItemId(items[1]!))
    const reversed = [...result.order].reverse()
    await client.post(`${path}/reorder`, { revision: result.revision, order: reversed })
    await client.post('/api/prompts/base/save', { kind, content: 'Changed base only' })
    const reordered = await prompts(client, kind)
    expect(reordered.map(libraryItemId)).toEqual(reversed)
    expect(reordered[0]!.content).toBe(base.content)
    expect(reordered.find(item => item.is_base)!.content).toBe('Changed base only')
    expect(reordered.filter(item => item.is_base)).toHaveLength(1)
  })

  it('isolates prompt order revisions by user/category and copies shared content into the current account', async () => {
    const { client } = setup()
    const path = endpoint('prompts', 'outline')
    await client.post('/api/prompts/save', { kind: 'outline', name: 'Shared', content: 'Full shared content {topic}' })
    await client.post('/api/prompts/admin/users', {
      kind: 'outline', name: 'Shared', owner_id: previewUser.id, allowed_users: ['演示成员'],
    })
    const admin = await order(client, path)
    await client.post(`${path}/reorder`, { revision: admin.revision, order: [...admin.order].reverse() })
    await login(client, '演示成员')
    const reader = await order(client, path)
    expect(reader.revision).toBe(0)
    expect(reader.order).toEqual(admin.order)
    const shared = (await prompts(client, 'outline')).find(item => item.name === 'Shared')!
    expect(shared).toMatchObject({ can_edit: false, is_shared: true, allowed_users: [] })
    const { result } = await copy(client, path, libraryItemId(shared))
    const own = (await prompts(client, 'outline')).find(item => libraryItemId(item) === result.created.id)!
    expect(own).toMatchObject({
      owner_id: 'preview-reader', content: shared.content, can_edit: true, is_shared: false, allowed_users: [],
    })
    expect((await order(client, endpoint('prompts', 'image'))).revision).toBe(0)
    await login(client, previewUser.username)
    expect((await order(client, path)).revision).toBe(1)
    expect((await order(client, path)).order.slice(0, 2)).toEqual([...admin.order].reverse())
    await client.post('/api/prompts/admin/users', {
      kind: 'outline', name: 'Shared', owner_id: previewUser.id, allowed_users: [],
    })
    await login(client, '演示成员')
    expect((await order(client, path)).order).not.toContain(libraryItemId(shared))
    expect((await order(client, path)).order).toContain(result.created.id)
    await expect(client.post(`${path}/copy`, {
      source: libraryItemId(shared), revision: 1, request_id: 'revoked',
    })).rejects.toMatchObject(rejected(404))
  })

  it('keeps model order personal for shared viewers and rejects shared-key copying', async () => {
    const { client } = setup()
    const path = endpoint('models', 'text')
    for (const name of ['preview-text', 'second']) {
      await client.post('/api/config/providers/save', {
        kind: 'text', name, config: { type: 'openai_compatible', model: name, allowed_users: ['演示成员'] },
      })
    }
    await login(client, '演示成员')
    await client.post(`${path}/reorder`, { revision: 0, order: ['second', 'preview-text'] })
    expect(Object.keys((await client.get('/api/config')).data.config.text_generation.providers)).toEqual(['second', 'preview-text'])
    await expect(copy(client, path, 'second')).rejects.toMatchObject(rejected(403))
    await login(client, previewUser.username)
    expect(await order(client, path)).toMatchObject({ revision: 0, order: ['preview-text', 'second'] })
    const { result } = await copy(client, path, 'second')
    await login(client, '演示成员')
    expect((await order(client, path)).order).not.toContain(result.created.id)
    expect((await order(client, endpoint('models', 'image'))).order).toEqual([])
  })

  it('validates revisions, exact visible sets, duplicate IDs and methods without modifying state', async () => {
    const { client } = setup()
    const path = endpoint('models', 'text')
    for (const body of [
      { revision: -1, order: ['preview-text'] },
      { revision: true, order: ['preview-text'] },
      { revision: 0, order: ['preview-text', 'preview-text'] },
      { revision: 0, order: [] },
      { revision: 0, order: ['foreign'] },
      { revision: 0, order: [123] },
    ]) await expect(client.post(`${path}/reorder`, body)).rejects.toMatchObject(rejected(400))
    await client.post(`${path}/reorder`, { revision: 0, order: ['preview-text'] })
    await expect(client.post(`${path}/reorder`, { revision: 0, order: ['preview-text'] })).rejects.toMatchObject(rejected(409))
    expect(await order(client, path)).toMatchObject({ revision: 1, order: ['preview-text'] })
    await expect(client.get(endpoint('models', 'outline'))).rejects.toMatchObject(rejected(404))
    await expect(client.get(`${path}/copy`)).rejects.toMatchObject(rejected(405))
    await expect(client.post(`${path}/copy`, {
      source: 'preview-text', revision: 1, request_id: '',
    })).rejects.toMatchObject(rejected(400))
  })

  it('binds idempotency to the user and entire request, and refuses replay of deleted copies', async () => {
    const { client } = setup()
    const path = endpoint('prompts', 'outline')
    const source = libraryItemId((await prompts(client, 'outline'))[0]!)
    const first = await copy(client, path, source, 'same-key')
    const newer = await copy(client, path, source, 'different-key')
    expect((await client.post(`${path}/copy`, first.body)).data).toEqual(first.result)
    expect((await order(client, path)).revision).toBe(newer.result.revision)
    await expect(client.post(`${endpoint('prompts', 'image')}/copy`, first.body)).rejects.toMatchObject(rejected(409))
    await login(client, '演示成员')
    const other = await copy(client, path, source, 'same-key')
    expect(other.result.created.id).not.toBe(first.result.created.id)
    await login(client, previewUser.username)
    await client.post('/api/prompts/delete', { kind: 'outline', name: first.result.created.name })
    await expect(client.post(`${path}/copy`, first.body)).rejects.toMatchObject(rejected(404))
    expect((await order(client, path)).order).not.toContain(first.result.created.id)
  })

  it('appends newly visible IDs and prunes removed ones without mutating returned snapshots', async () => {
    const { client } = setup()
    const path = endpoint('models', 'text')
    const { result } = await copy(client, path, 'preview-text')
    await client.post(`${path}/reorder`, { revision: 1, order: [...result.order].reverse() })
    await client.post('/api/config/providers/save', { kind: 'text', name: 'new', config: { type: 'image_api', model: 'new' } })
    const state = await order(client, path)
    expect(state.order).toEqual([result.created.id, 'preview-text', 'new'])
    state.order.reverse()
    const config = (await client.get('/api/config')).data.config
    delete config.text_generation.providers['preview-text']
    await client.post('/api/config', config)
    expect((await order(client, path)).order).toEqual([result.created.id, 'new'])
  })

  it('limits copy names to 50 Unicode characters and resolves collisions', async () => {
    const { client } = setup()
    const name = '字'.repeat(50)
    await client.post('/api/prompts/save', { kind: 'image', name, content: 'Long named content' })
    const path = endpoint('prompts', 'image')
    const source = libraryItemId({ is_base: false, owner_id: previewUser.id, name })
    const first = (await copy(client, path, source, 'first')).result
    const second = (await copy(client, path, source, 'second')).result
    expect(Array.from(first.created.name)).toHaveLength(50)
    expect(Array.from(second.created.name)).toHaveLength(50)
    expect(first.created.name).not.toBe(second.created.name)
  })

  it('generates distinct model labels even when a different provider already occupies the display name', async () => {
    const { client } = setup()
    await client.post('/api/config/providers/save', {
      kind: 'text', name: 'preview-text', config: { provider_label: 'Label', display_name: 'Label:preview-text' },
    })
    await client.post('/api/config/providers/save', {
      kind: 'text', name: 'occupied', config: { type: 'image_api', model: 'other', display_name: 'Label（副本）:preview-text' },
    })
    const path = endpoint('models', 'text')
    const first = (await copy(client, path, 'preview-text', 'first')).result
    const second = (await copy(client, path, 'preview-text', 'second')).result
    const models = (await client.get('/api/config')).data.config.text_generation.providers
    expect(models[first.created.id].provider_label).toBe('Label（副本2）')
    expect(models[first.created.id].display_name).toBe('Label（副本2）:preview-text')
    expect(models[second.created.id].provider_label).toBe('Label（副本3）')
    expect(models[second.created.id].display_name).toBe('Label（副本3）:preview-text')
    expect(models['preview-text'].display_name).toBe('Label:preview-text')
  })

  it('uses the same library contract through fetch and keeps unauthenticated calls local', async () => {
    const { fetch, client } = setup()
    const path = endpoint('models', 'image')
    const first = await (await fetch(path)).json()
    expect(first).toMatchObject({ revision: 0, order: ['preview-image'] })
    const result = await (await fetch(`${path}/copy`, {
      method: 'POST', body: JSON.stringify({ source: 'preview-image', revision: 0, request_id: 'fetch' }),
    })).json()
    expect((await order(client, path)).order).toEqual(result.order)
    await client.post('/api/auth/logout')
    expect((await fetch(path)).status).toBe(401)
    await expect(client.get('/api/prompts')).rejects.toMatchObject(rejected(401))
    expect(localStorage.length).toBe(0)
  })
})

describe('preview safe prompt rename', () => {
  it('replaces the stable ID in owner and shared viewer order while retaining sharing and position', async () => {
    const { client } = setup()
    const path = endpoint('prompts', 'content')
    await client.post('/api/prompts/save', { kind: 'content', name: 'Old', content: 'Original' })
    await client.post('/api/prompts/admin/users', {
      kind: 'content', name: 'Old', owner_id: previewUser.id, allowed_users: ['演示成员'],
    })
    const before = await order(client, path)
    const oldId = before.order[1]!
    await client.post(`${path}/reorder`, { revision: 0, order: [oldId, before.order[0]] })
    await login(client, '演示成员')
    await client.post(`${path}/reorder`, { revision: 0, order: before.order })
    await login(client, previewUser.username)
    await client.post('/api/prompts/save', { kind: 'content', original_name: 'Old', name: 'Renamed', content: 'Edited' })
    const renamed = (await prompts(client, 'content'))[0]!
    expect(renamed).toMatchObject({ name: 'Renamed', content: 'Edited', allowed_users: ['演示成员'] })
    expect(await order(client, path)).toMatchObject({ revision: 2, order: [libraryItemId(renamed), before.order[0]] })
    await expect(client.post(`${path}/reorder`, { revision: 1, order: before.order })).rejects.toMatchObject(rejected(409))
    await login(client, '演示成员')
    expect(await order(client, path)).toMatchObject({ revision: 2, order: [before.order[0], libraryItemId(renamed)] })
    expect((await prompts(client, 'content')).some(item => item.name === 'Old')).toBe(false)
  })

  it('rejects unsafe renames atomically and keeps original upsert behavior when original_name is absent', async () => {
    const { client } = setup()
    for (const name of ['One', 'Two']) await client.post('/api/prompts/save', { kind: 'outline', name, content: name })
    const snapshot = await prompts(client, 'outline')
    for (const [original_name, name] of [
      ['One', 'Two'], ['missing', 'New'], ['默认提示词', 'New'], ['', 'New'], ['One', '默认提示词'], ['One', 'x'.repeat(51)],
    ]) {
      await expect(client.post('/api/prompts/save', { kind: 'outline', original_name, name, content: 'Changed' }))
        .rejects.toMatchObject(rejected(400))
      expect(await prompts(client, 'outline')).toEqual(snapshot)
    }
    await login(client, '演示成员')
    await expect(client.post('/api/prompts/save', { kind: 'outline', original_name: 'One', name: 'Stolen', content: 'Changed' }))
      .rejects.toMatchObject(rejected(400))
    await login(client, previewUser.username)
    await client.post('/api/prompts/save', { kind: 'outline', name: 'One', content: 'Updated' })
    expect((await prompts(client, 'outline')).find(item => item.name === 'One')!.content).toBe('Updated')
    expect(await prompts(client, 'outline')).toHaveLength(3)
  })
})
