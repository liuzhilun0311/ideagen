import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { copyLibraryItem, getLibraryOrder, saveLibraryOrder, type LibraryCopy } from '../../src/api/library'
import { useLibraryOrder } from '../../src/composables/useLibraryOrder'

vi.mock('../../src/api/library', () => ({
  copyLibraryItem: vi.fn(), getLibraryOrder: vi.fn(), saveLibraryOrder: vi.fn(),
}))
let scope: ReturnType<typeof effectScope>
function setup() {
  scope = effectScope()
  const kind = ref('text'), ids = ref(['a', 'b', 'c'])
  return { kind, ids, ...scope.run(() => useLibraryOrder('models', kind, ids))! }
}
beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  vi.mocked(getLibraryOrder).mockResolvedValue({ success: true, revision: 1, order: ['b', 'a', 'c'] })
  vi.mocked(saveLibraryOrder).mockResolvedValue({ success: true, revision: 2, order: ['a', 'b', 'c'] })
})
afterEach(() => { scope?.stop(); vi.unstubAllGlobals() })

it('copies on LAN HTTP without crypto.randomUUID', async () => {
  vi.stubGlobal('crypto', { getRandomValues: (bytes: Uint8Array) => bytes.fill(7) })
  vi.mocked(copyLibraryItem).mockResolvedValue({
    success: true, revision: 2, order: ['b', 'a', 'copy', 'c'], created: { id: 'copy', name: 'Copy' },
  })
  const list = setup()
  await list.refresh()
  expect(await list.copy('a')).toEqual({ id: 'copy', name: 'Copy' })
  expect(vi.mocked(copyLibraryItem).mock.calls[0]?.[4]).toBe('07'.repeat(16))
})

it('merges server order with new visible items, removing hidden IDs', async () => {
  const list = setup()
  await list.refresh()
  expect(list.order.value).toEqual(['b', 'a', 'c'])
  list.ids.value = ['a', 'c', 'new']
  expect(list.order.value).toEqual(['a', 'c', 'new'])
})

it('saves move with revision and restores the old ordering on failure', async () => {
  const list = setup()
  await list.refresh()
  vi.mocked(saveLibraryOrder).mockRejectedValue(new Error('offline'))
  expect(await list.move('a', 'b')).toBe(false)
  expect(saveLibraryOrder).toHaveBeenCalledWith('models', 'text', 1, ['a', 'b', 'c'])
  expect(list.order.value).toEqual(['b', 'a', 'c'])
  expect(list.error.value).toContain('offline')
})

it('ignores a late copy after switching category', async () => {
  let finish!: (value: LibraryCopy) => void
  vi.mocked(copyLibraryItem).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const list = setup()
  await list.refresh()
  const pending = list.copy('a')
  list.kind.value = 'image'
  finish({ success: true, revision: 2, order: ['a', 'copy'], created: { id: 'copy', name: 'Copy' } })
  expect(await pending).toBeNull()
  expect(list.order.value).not.toContain('copy')
  expect(list.busy.value).toBe(false)
})

it('reuses an idempotency key after an uncertain network failure', async () => {
  vi.mocked(copyLibraryItem).mockRejectedValue(new Error('offline'))
  const list = setup()
  await list.refresh()
  await list.copy('a')
  await list.copy('a')
  expect(vi.mocked(copyLibraryItem).mock.calls[0]?.[4]).toBe(vi.mocked(copyLibraryItem).mock.calls[1]?.[4])
})

it('blocks duplicate mutations while a request is pending', async () => {
  let finish!: (value: LibraryCopy) => void
  vi.mocked(copyLibraryItem).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const list = setup()
  await list.refresh()
  const pending = list.copy('a')
  expect(await list.copy('a')).toBeNull()
  expect(await list.move('a', 'b')).toBe(false)
  finish({ success: true, revision: 2, order: ['b', 'a', 'copy', 'c'], created: { id: 'copy', name: 'Copy' } })
  expect(await pending).toEqual({ id: 'copy', name: 'Copy' })
  list.ids.value.push('copy')
  expect(list.order.value).toEqual(['b', 'a', 'copy', 'c'])
})
