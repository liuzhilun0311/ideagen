import axios from 'axios'
import { expect, it, vi } from 'vitest'
import { generateCandidate } from '../../src/api/candidates'

vi.mock('axios', async importOriginal => {
  const actual = await importOriginal<typeof import('axios')>()
  return {
    ...actual,
    default: {
      ...actual.default,
      post: vi.fn(async () => ({ data: { candidate: {} } }))
    }
  }
})

it.each([true, false])('serializes use_reference=%s on the actual candidate request', async enabled => {
  await generateCandidate('work', 1, { preset: 'comic', notes: '' }, 'model', '', [], undefined, enabled)
  expect(axios.post).toHaveBeenLastCalledWith('/api/image-candidates/work',
    expect.objectContaining({ index: 1, use_reference: enabled, user_images: [] }),
    { timeout: 0 })
})
