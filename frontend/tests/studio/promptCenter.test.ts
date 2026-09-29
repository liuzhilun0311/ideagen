import { describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import {
  copyPromptEntry, getPromptCatalog, promptDraft, reorderPromptEntries,
  restorePromptEntry, savePromptEntry,
} from '../../src/api/promptCenter'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

const entry = {
  id: 'entry-1', module: 'content' as const, category: 'style' as const,
  name: '清晰表达', description: '适合产品说明', content: '用清晰的语言。',
  metadata: { color: '#176b55' }, owner_id: 'u1', owner_name: '作者',
  builtin: false, enabled: true, visibility: 'selected' as const,
  allowed_users: ['u2'], revision: 3, can_edit: true, can_use: true,
}

describe('prompt center API contract', () => {
  it('loads the management catalog with manage flag', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { success: true, entries: [entry], categories: {}, orders: {} } })
    await getPromptCatalog()
    expect(axios.get).toHaveBeenCalledWith('/api/prompt-center', { params: { manage: 1 } })
  })

  it('saves editable fields with id and revision', async () => {
    vi.mocked(axios.post).mockResolvedValueOnce({ data: { success: true, entry } })
    await savePromptEntry(promptDraft(entry))
    expect(axios.post).toHaveBeenCalledWith('/api/prompt-center/save', expect.objectContaining({
      id: 'entry-1', revision: 3, module: 'content', category: 'style',
      allowed_users: ['u2'], metadata: { color: '#176b55' },
    }))
  })

  it('copies, restores, and reorders using stable IDs and revisions', async () => {
    vi.mocked(axios.post)
      .mockResolvedValueOnce({ data: { success: true, entry: { ...entry, id: 'entry-2' } } })
      .mockResolvedValueOnce({ data: { success: true, entry } })
      .mockResolvedValueOnce({ data: { success: true, revision: 4 } })
    await copyPromptEntry('entry-1')
    await restorePromptEntry('entry-1', 3, 2)
    await reorderPromptEntries('content', 'style', ['entry-2', 'entry-1'], 3)
    expect(axios.post).toHaveBeenNthCalledWith(1, '/api/prompt-center/copy', { id: 'entry-1' })
    expect(axios.post).toHaveBeenNthCalledWith(2, '/api/prompt-center/restore', { id: 'entry-1', revision: 3, version: 2 })
    expect(axios.post).toHaveBeenNthCalledWith(3, '/api/prompt-center/reorder', {
      module: 'content', category: 'style', ids: ['entry-2', 'entry-1'], revision: 3,
    })
  })

  it('clones draft data without mutating the catalog entry', () => {
    const draft = promptDraft(entry)
    draft.metadata.color = '#ffffff'
    draft.allowed_users.push('u3')
    expect(entry.metadata.color).toBe('#176b55')
    expect(entry.allowed_users).toEqual(['u2'])
  })
})
