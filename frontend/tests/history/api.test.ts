import { beforeEach, expect, it, vi } from 'vitest'
import axios from 'axios'
import { getHistoryList, getHistoryStats, getHistorySharing, setHistorySharing } from '../../src/api/history'

vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn(), isAxiosError: () => false } }))
vi.mock('../../src/api/client', () => ({ API_BASE_URL: '/api', getApiErrorPayload: () => ({ error_message: 'Failed' }) }))
beforeEach(() => {
  vi.mocked(axios.get).mockResolvedValue({ data: { success: true, user_ids: ['reader'] } })
  vi.mocked(axios.put).mockResolvedValue({ data: { success: true, user_ids: ['reader'] } })
})
it('combines source, status, keyword and pagination in the list endpoint', async () => {
  await getHistoryList(3, 12, 'completed', 'shared', '  test  ')
  expect(axios.get).toHaveBeenCalledWith('/api/history', {
    params: { page: 3, page_size: 12, status: 'completed', source: 'shared', keyword: 'test' }, timeout: 10000,
  })
  await getHistoryList()
  expect(axios.get).toHaveBeenLastCalledWith('/api/history', { params: { page: 1, page_size: 20 }, timeout: 10000 })
})
it('scopes statistics independently of status', async () => {
  await getHistoryStats('shared')
  expect(axios.get).toHaveBeenCalledWith('/api/history/stats', { params: { source: 'shared' }, timeout: 10000 })
})
it('reads and writes the exact sharing contract including clearing all grants', async () => {
  expect(await getHistorySharing('work')).toEqual({ success: true, user_ids: ['reader'] })
  expect(axios.get).toHaveBeenCalledWith('/api/history/work/sharing', { timeout: 10000 })
  await setHistorySharing('work', [])
  expect(axios.put).toHaveBeenCalledWith('/api/history/work/sharing', { user_ids: [] }, { timeout: 10000 })
})
it('normalizes sharing errors without throwing', async () => {
  vi.mocked(axios.put).mockRejectedValue(new Error('offline'))
  expect(await setHistorySharing('work', ['reader'])).toMatchObject({ success: false, user_ids: [], error_message: 'Failed' })
})
