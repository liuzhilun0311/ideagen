import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../src/api/history', () => ({ getHistory: vi.fn() }))

import { getHistory } from '../../src/api/history'
import type { HistoryDetail } from '../../src/api/types'
import { useGeneratorStore } from '../../src/stores/generator'
import { useStudioSession } from '../../src/stores/studioSession'
import { useHistoryDraft } from '../../src/composables/useHistoryDraft'
import { useAuthStore } from '../../src/stores/auth'
import { clearAuth, setToken, setUser } from '../../src/api/token'
import { normalizeApiError } from '../../src/utils/errors'

function record(id = 'history'): HistoryDetail {
  return {
    id, title: 'History title', created_at: '', updated_at: '2026-09-09',
    status: 'completed', thumbnail: null,
    outline: { raw: 'Cover', pages: [{ index: 0, type: 'cover', content: 'Cover' }] },
    content: { titles: ['Title'], copywriting: 'Copy', tags: ['tag'] },
    images: { task_id: 'task', generated: ['0.png'] },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

const confirm = vi.fn(() => true)
const push = vi.fn(async (_path: string) => {})
let store: ReturnType<typeof useGeneratorStore>
let session: ReturnType<typeof useStudioSession>
let history: ReturnType<typeof useHistoryDraft>

beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  setToken('history-test-token')
  setUser({ id: 'reader', username: 'reader', is_admin: false })
  store = useGeneratorStore()
  session = useStudioSession()
  confirm.mockReturnValue(true)
  vi.mocked(getHistory).mockResolvedValue({ success: true, record: record() })
  history = useHistoryDraft({ push }, confirm)
})

describe('guarded history draft replacement', () => {
  it('restores the selected title without discarding alternatives', async () => {
    const saved = record()
    saved.content = { titles: ['First', 'Second'], selected_title_index: 1, copywriting: 'Copy', tags: [] }
    vi.mocked(getHistory).mockResolvedValue({ success: true, record: saved })
    expect(await history.loadRecord('history')).toBe(true)
    expect(store.content.selectedTitleIndex).toBe(1)
    expect(store.content.titles).toEqual(['First', 'Second'])
  })
  it('refuses to load a read-only shared work into the creation draft', async () => {
    store.topic = 'Keep my draft'
    const before = JSON.stringify(store.$state)
    vi.mocked(getHistory).mockResolvedValue({ success: true, record: { ...record(), can_edit: false } })
    expect(await history.loadRecord('history')).toBe(false)
    expect(JSON.stringify(store.$state)).toBe(before)
    expect(push).not.toHaveBeenCalled()
    expect(history.error.value?.detail).toContain('共享')
  })
  it('resumes the current record on the remembered copy page without reading history', async () => {
    store.setRecordId('current')
    store.setOutline('Local', [{ index: 0, type: 'cover', content: 'Local' }])
    session.workspacePath = '/workspace/copy'
    expect(await history.loadRecord('current')).toBe(true)
    expect(push).toHaveBeenCalledWith('/workspace/copy')
    expect(getHistory).not.toHaveBeenCalled()
  })
  it.each(['homeBusy', 'workspaceBusy', 'structureBusy'] as const)('refuses replacement before GET while %s', async key => {
    session[key] = true
    const before = JSON.stringify(store.$state)
    expect(await history.loadRecord('history')).toBe(false)
    expect(getHistory).not.toHaveBeenCalled()
    expect(confirm).not.toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
    expect(JSON.stringify(store.$state)).toBe(before)
    expect(history.error.value?.detail).toBeTruthy()
  })

  it('cancels replacement of even a saved existing draft without fetching', async () => {
    store.setOutline('Local', [{ index: 0, type: 'cover', content: 'Local' }])
    store.setRecordId('local')
    confirm.mockReturnValue(false)
    const before = JSON.stringify(store.$state)
    expect(await history.loadRecord('history')).toBe(false)
    expect(confirm).toHaveBeenCalledOnce()
    expect(getHistory).not.toHaveBeenCalled()
    expect(JSON.stringify(store.$state)).toBe(before)
    expect(session.revision).toBe(0)
    expect(push).not.toHaveBeenCalled()
  })

  it.each(['busy', 'revision', 'record', 'edit', 'dirty', 'reference'] as const)(
    'rejects a late read after %s changes', async change => {
      store.topic = 'Local'
      session.dirty = change === 'edit'
      const read = deferred<Awaited<ReturnType<typeof getHistory>>>()
      vi.mocked(getHistory).mockReturnValue(read.promise)
      const pending = history.loadRecord('history')
      if (change === 'busy') session.workspaceBusy = true
      if (change === 'revision') session.replaceDraft()
      if (change === 'record') store.setRecordId('other')
      if (change === 'edit') store.content.copywriting = 'Edit during GET'
      if (change === 'dirty') session.dirty = true
      if (change === 'reference') store.referenceContent = 'New reference'
      const before = JSON.stringify(store.$state)
      const revision = session.revision
      read.resolve({ success: true, record: record() })
      expect(await pending).toBe(false)
      expect(JSON.stringify(store.$state)).toBe(before)
      expect(session.revision).toBe(revision)
      expect(push).not.toHaveBeenCalled()
      expect(history.error.value?.detail).toBeTruthy()
    },
  )

  it('uses replaceDraft before any generator assignments and then navigates', async () => {
    store.topic = 'Previous'
    store.referenceContent = 'Previous reference'
    session.dirty = true
    session.notice = 'Previous completion'
    const replacement = vi.spyOn(session, 'replaceDraft')
    store.$onAction(({ name }) => {
      if (name.startsWith('set')) expect(replacement).toHaveBeenCalledOnce()
    })
    push.mockImplementation(async () => {
      expect(store.recordId).toBe('history')
      expect(store.outline.pages[0].content).toBe('Cover')
    })
    expect(await history.loadRecord('history')).toBe(true)
    expect(session.revision).toBe(1)
    expect(session.dirty).toBe(false)
    expect(session.notice).toBe('')
    expect(store.referenceContent).toBe('')
    expect(store.entrySource).toBe('history')
    expect(store.taskId).toBe('task')
    expect(store.images[0]).toMatchObject({ index: 0, status: 'done' })
    expect(push).toHaveBeenCalledWith('/workspace')
  })

  it('does not assign if the final replacement guard refuses', async () => {
    vi.spyOn(session, 'replaceDraft').mockReturnValue(false)
    const before = JSON.stringify(store.$state)
    expect(await history.loadRecord('history')).toBe(false)
    expect(JSON.stringify(store.$state)).toBe(before)
    expect(push).not.toHaveBeenCalled()
  })

  it('checks ownership again after confirmation', async () => {
    store.topic = 'Local'
    confirm.mockImplementation(() => {
      session.homeBusy = true
      return true
    })
    expect(await history.loadRecord('history')).toBe(false)
    expect(getHistory).not.toHaveBeenCalled()
    expect(store.topic).toBe('Local')
    expect(session.revision).toBe(0)
  })

  it('clears previous results when the selected history has no content or images', async () => {
    store.setContent(['Old title'], 'Old copy', ['old'])
    store.taskId = 'old-task'
    store.images = [{ index: 0, url: 'old.png', status: 'done' }]
    const payload = record()
    payload.image_style = { preset: 'comic', notes: 'Blue' }
    delete payload.content
    payload.images = { task_id: null, generated: [] }
    vi.mocked(getHistory).mockResolvedValue({ success: true, record: payload })
    expect(await history.loadRecord('history')).toBe(true)
    expect(confirm).toHaveBeenCalledOnce()
    expect(store.content).toMatchObject({ titles: [], copywriting: '', tags: [], status: 'idle' })
    expect(store.images).toEqual([])
    expect(store.taskId).toBeNull()
    expect(store.progress).toEqual({ current: 0, total: 0, status: 'idle' })
  })

  it('protects uploaded images changed during a read, even when their serialized values match', async () => {
    store.userImages = [new File(['first'], 'reference.png')]
    const read = deferred<Awaited<ReturnType<typeof getHistory>>>()
    vi.mocked(getHistory).mockReturnValue(read.promise)
    const pending = history.loadRecord('history')
    const newImage = new File(['second'], 'reference.png')
    store.userImages = [newImage]
    read.resolve({ success: true, record: record() })
    expect(await pending).toBe(false)
    expect(store.userImages[0]).toBe(newImage)
    expect(session.revision).toBe(0)
  })

  it('clones pages, titles and tags without retaining response aliases', async () => {
    const payload = record()
    payload.image_style = { preset: 'comic', notes: 'Blue' }
    payload.content!.source = { topic: 'Original topic', outline: 'Original outline' }
    vi.mocked(getHistory).mockResolvedValue({ success: true, record: payload })
    await history.loadRecord('history')
    expect(store.imageStyle).toEqual({ preset: 'comic', notes: 'Blue' })
    store.outline.pages[0].content = 'Local edit'
    store.content.titles.push('Local title')
    store.content.tags.push('Local tag')
    expect(payload.outline.pages[0].content).toBe('Cover')
    expect(payload.content?.titles).toEqual(['Title'])
    expect(payload.content?.tags).toEqual(['tag'])
    expect(store.content.source).toEqual(payload.content!.source)
    store.content.source!.outline = 'Local source'
    expect(payload.content!.source.outline).toBe('Original outline')
    payload.outline.pages.push({ index: 1, type: 'content', content: 'Remote' })
    expect(store.outline.pages).toHaveLength(1)
  })

  it.each([false, true])('resumes the same current record without overwriting edits (busy=%s)', async busy => {
    store.setRecordId('history')
    store.setOutline('Unsaved', [{ index: 0, type: 'cover', content: 'Unsaved' }])
    session.dirty = true
    session.workspaceBusy = busy
    const before = JSON.stringify(store.$state)
    expect(await history.loadRecord('history')).toBe(true)
    expect(getHistory).not.toHaveBeenCalled()
    expect(confirm).not.toHaveBeenCalled()
    expect(JSON.stringify(store.$state)).toBe(before)
    expect(session.dirty).toBe(true)
    expect(session.revision).toBe(0)
    expect(push).toHaveBeenCalledWith('/workspace')
  })

  it('does not reload a same-record draft whose pages were deleted', async () => {
    store.setRecordId('history')
    session.dirty = true
    expect(await history.loadRecord('history')).toBe(true)
    expect(getHistory).not.toHaveBeenCalled()
    expect(push).toHaveBeenCalledWith('/')
  })

  it('ignores an older request when another history record is selected', async () => {
    const older = deferred<Awaited<ReturnType<typeof getHistory>>>()
    vi.mocked(getHistory).mockReturnValueOnce(older.promise)
    const pending = history.loadRecord('older')
    await history.loadRecord('history')
    older.resolve({ success: true, record: record('older') })
    expect(await pending).toBe(false)
    expect(store.recordId).toBe('history')
    expect(push).toHaveBeenCalledOnce()
    expect(history.error.value).toBeNull()
  })

  it('rejects a response for the wrong record', async () => {
    vi.mocked(getHistory).mockResolvedValue({ success: true, record: record('wrong') })
    expect(await history.loadRecord('history')).toBe(false)
    expect(store.recordId).toBeNull()
    expect(push).not.toHaveBeenCalled()
  })

  it.each(['success', 'rejection'] as const)(
    'invalidates a pending %s on deactivation/unmount without overwriting feedback', async outcome => {
      const read = deferred<Awaited<ReturnType<typeof getHistory>>>()
      vi.mocked(getHistory).mockReturnValueOnce(read.promise)
      const pending = history.loadRecord('history')
      const before = JSON.stringify(store.$state)
      history.cancelPending()
      history.cancelPending()
      history.error.value = normalizeApiError('New feedback')
      const feedback = history.error.value
      if (outcome === 'success') read.resolve({ success: true, record: record() })
      else read.reject(new Error('Old failure'))
      expect(await pending).toBe(false)
      expect(JSON.stringify(store.$state)).toBe(before)
      expect(session.revision).toBe(0)
      expect(push).not.toHaveBeenCalled()
      expect(history.error.value).toBe(feedback)
    },
  )

  it('allows a fresh selection after reactivation while the invalidated read is still pending', async () => {
    const read = deferred<Awaited<ReturnType<typeof getHistory>>>()
    vi.mocked(getHistory).mockReturnValueOnce(read.promise)
    const pending = history.loadRecord('history')
    history.cancelPending()
    expect(await history.loadRecord('history')).toBe(true)
    const before = JSON.stringify(store.$state)
    read.resolve({ success: true, record: { ...record(), title: 'Stale title' } })
    expect(await pending).toBe(false)
    expect(JSON.stringify(store.$state)).toBe(before)
    expect(session.revision).toBe(1)
    expect(push).toHaveBeenCalledOnce()
    expect(history.error.value).toBeNull()
  })

  describe.each(['token', 'user', 'revision', 'persisted-token', 'logout'] as const)(
    'auth ownership change: %s', change => {
      it.each(['success', 'rejection'] as const)('ignores late %s without altering errors', async outcome => {
        const auth = useAuthStore()
        const read = deferred<Awaited<ReturnType<typeof getHistory>>>()
        vi.mocked(getHistory).mockReturnValueOnce(read.promise)
        const pending = history.loadRecord('history')
        const before = JSON.stringify(store.$state)
        if (change === 'token') auth.token = 'new-token'
        if (change === 'user') auth.user = { id: 'other', username: 'other', is_admin: false }
        if (change === 'revision') auth.sessionRevision += 1
        if (change === 'persisted-token') setToken('new-token')
        if (change === 'logout') clearAuth()
        history.error.value = normalizeApiError('Current feedback')
        const feedback = history.error.value
        if (outcome === 'success') read.resolve({ success: true, record: record() })
        else read.reject(new Error('Old failure'))
        expect(await pending).toBe(false)
        expect(JSON.stringify(store.$state)).toBe(before)
        expect(session.revision).toBe(0)
        expect(push).not.toHaveBeenCalled()
        expect(history.error.value).toBe(feedback)
      })
    },
  )

  it('allows a fresh read under a new auth session', async () => {
    const read = deferred<Awaited<ReturnType<typeof getHistory>>>()
    vi.mocked(getHistory).mockReturnValueOnce(read.promise)
    const pending = history.loadRecord('history')
    const auth = useAuthStore()
    auth.sessionRevision += 1
    auth.token = 'new-token'
    setToken('new-token')
    expect(await history.loadRecord('history')).toBe(true)
    read.reject(new Error('Old session failure'))
    expect(await pending).toBe(false)
    expect(store.recordId).toBe('history')
    expect(session.revision).toBe(1)
    expect(push).toHaveBeenCalledOnce()
    expect(history.error.value).toBeNull()
  })

  it.each(['rejection', 'failure', 'missing'] as const)('normalizes %s errors', async kind => {
    if (kind === 'rejection') vi.mocked(getHistory).mockRejectedValue(new Error('Read failed'))
    if (kind === 'failure') vi.mocked(getHistory).mockResolvedValue({ success: false, error: 'Read failed' })
    if (kind === 'missing') vi.mocked(getHistory).mockResolvedValue({ success: true })
    expect(await history.loadRecord('history')).toBe(false)
    expect(history.error.value).toMatchObject({ title: expect.any(String), detail: expect.any(String) })
    expect(store.recordId).toBeNull()
    expect(push).not.toHaveBeenCalled()
  })
})
