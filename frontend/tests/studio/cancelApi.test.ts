import { afterEach, expect, it, vi } from 'vitest'
import axios from 'axios'
import { cancelCurrentGeneration } from '../../src/api/image'

afterEach(() => vi.restoreAllMocks())
it('requires acknowledgement and bounds the cancellation wait', async () => {
  const post = vi.spyOn(axios, 'post').mockResolvedValue({ data: { success: true } })
  await expect(cancelCurrentGeneration()).resolves.toBeUndefined()
  expect(post).toHaveBeenCalledWith('/api/generate/cancel', undefined, { timeout: 10000 })
})
it('does not swallow network failures', async () => {
  vi.spyOn(axios, 'post').mockRejectedValue(new Error('timeout'))
  await expect(cancelCurrentGeneration()).rejects.toThrow('timeout')
})
it('does not claim success for a missing acknowledgement', async () => {
  vi.spyOn(axios, 'post').mockResolvedValue({ data: { success: false } })
  await expect(cancelCurrentGeneration()).rejects.toThrow('未确认')
})
