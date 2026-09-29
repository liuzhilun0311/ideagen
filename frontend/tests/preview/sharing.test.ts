import axios from 'axios'
import { describe, expect, it } from 'vitest'
import { createPreviewFixtures, previewReader, previewUser } from './fixtures'

const endpoint = '/api/history/preview-record'
const rejected = (status: number) => ({ response: { status } })
function setup() {
  return axios.create({ adapter: createPreviewFixtures(0).adapter })
}
async function login(client: ReturnType<typeof setup>, username: string) {
  await client.post('/api/auth/login', { username, password: 'synthetic-only' })
}

describe('isolated work sharing fixtures', () => {
  it('grants read-only access without adding the work to recipient own records', async () => {
    const client = setup()
    const original = (await client.get(endpoint)).data.record
    expect(original).toMatchObject({ can_edit: true, can_share: true, shared_count: 0 })
    await client.put(`${endpoint}/sharing`, { user_ids: [previewReader.id] })
    await login(client, previewReader.username)
    expect((await client.get('/api/history')).data.records).toEqual([])
    const shared = (await client.get('/api/history', { params: { source: 'shared', keyword: '城市', status: 'completed', page_size: 1 } })).data
    expect(shared.total).toBe(1)
    expect(shared.records[0]).toMatchObject({
      can_edit: false, can_share: false, is_shared: true, owner: { id: previewUser.id, username: previewUser.username },
    })
    expect(shared.records[0]).not.toHaveProperty('shared_count')
    expect((await client.get('/api/history/stats', { params: { source: 'shared' } })).data.total).toBe(1)
    expect((await client.get(endpoint)).data.record.content).toEqual(original.content)
    expect((await client.get('/api/postprocessing/preview-record')).data.pages).toHaveLength(3)
    await expect(client.get('/api/images/preview-task/0.png')).resolves.toMatchObject({ status: 200 })
    await expect(client.get('/api/images/preview-task/9.png')).rejects.toMatchObject(rejected(403))
    for (const action of [
      () => client.put(endpoint, { title: 'Forbidden' }),
      () => client.delete(endpoint),
      () => client.put(`${endpoint}/sharing`, { user_ids: [] }),
      () => client.post('/api/postprocessing/preview-record', { action: 'preferences', automatic: true, strength: 'light' }),
      () => client.post('/api/history/scan/preview-task'),
      () => client.post('/api/regenerate', { record_id: 'preview-record', task_id: 'preview-task', page: { index: 0 } }),
    ]) await expect(action()).rejects.toMatchObject(rejected(403))
  })
  it('revocation denies cached record IDs and state reads', async () => {
    const client = setup()
    await client.put(`${endpoint}/sharing`, { user_ids: [previewReader.id] })
    await login(client, previewReader.username)
    expect((await client.get(`${endpoint}/exists`)).data.exists).toBe(true)
    await login(client, previewUser.username)
    await client.put(`${endpoint}/sharing`, { user_ids: [] })
    await login(client, previewReader.username)
    expect((await client.get('/api/history', { params: { source: 'shared' } })).data.total).toBe(0)
    expect((await client.get(`${endpoint}/exists`)).data.exists).toBe(false)
    await expect(client.get(endpoint)).rejects.toMatchObject(rejected(403))
    await expect(client.get('/api/postprocessing/preview-record')).rejects.toMatchObject(rejected(403))
    await expect(client.get('/api/images/preview-task/0.png')).rejects.toMatchObject(rejected(403))
  })
  it('rejects invalid grant sets without dropping existing grants', async () => {
    const client = setup()
    await client.put(`${endpoint}/sharing`, { user_ids: [previewReader.id] })
    await expect(client.put(`${endpoint}/sharing`, { user_ids: ['missing'] })).rejects.toMatchObject(rejected(400))
    expect((await client.get(`${endpoint}/sharing`)).data.user_ids).toEqual([previewReader.id])
    await login(client, previewReader.username)
    await expect(client.get(`${endpoint}/sharing`)).rejects.toMatchObject(rejected(403))
  })
})
