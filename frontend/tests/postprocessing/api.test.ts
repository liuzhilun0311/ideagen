import { beforeEach, expect, it, vi } from 'vitest'
import axios from 'axios'
import { getProcessingState, updatePostprocessing } from '../../src/api/postprocessing'

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), isAxiosError: (error: any) => error?.isAxiosError === true,
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } } },
}))
beforeEach(() => vi.clearAllMocks())
it('preserves HTTP denial status from legacy error bodies', async () => {
  vi.mocked(axios.get).mockRejectedValue({
    isAxiosError: true, response: { status: 403, data: { error: 'Sharing revoked' } },
  })
  await expect(getProcessingState('record')).rejects.toMatchObject({ status: 403, detail: 'Sharing revoked' })
})
it('uses record-scoped GET and sends the exact adoption contract', async () => {
  const data = { success: true, preferences: { automatic: false, strength: 'light' }, pages: [] }
  vi.mocked(axios.get).mockResolvedValue({ data })
  vi.mocked(axios.post).mockResolvedValue({ data })
  expect(await getProcessingState('record /one')).toBe(data)
  expect(axios.get).toHaveBeenCalledWith('/api/postprocessing/record%20%2Fone', { timeout: 15000 })
  const action = { action: 'adopt' as const, index: 2, version: 'processed' as const, source_revision: 'source-2' }
  expect(await updatePostprocessing('record', action)).toBe(data)
  expect(axios.post).toHaveBeenCalledWith('/api/postprocessing/record', action, { timeout: 15000 })
})
it('rejects unsuccessful responses without presenting them as valid state', async () => {
  vi.mocked(axios.get).mockResolvedValue({ data: { success: false, error_message: 'Unavailable' } })
  await expect(getProcessingState('record')).rejects.toBe('Unavailable')
})
