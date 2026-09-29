import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { getPromptCatalog, type PromptEntry } from '../../src/api/promptCenter'
import { fallbackItems, findLayoutItem, makeCatalog, promptItems, resolvePromptValue, selectionItems, usePromptCatalogStore } from '../../src/features/promptCatalog'
import { normalizeImageStyle, resolveImageStyle } from '../../src/features/styles/catalog'
import { copyPreferences, resolveCopyPreferences } from '../../src/features/copyOptions'
import { setToken } from '../../src/api/token'

vi.mock('../../src/api/promptCenter', () => ({ getPromptCatalog: vi.fn() }))
const entry = (patch: Partial<PromptEntry> = {}): PromptEntry => ({
  id: 'custom-id', module: 'image', category: 'style', name: 'Custom', description: '',
  content: 'Instructions', metadata: {}, builtin: false, enabled: true, can_use: true,
  owner_id: 'owner', owner_name: 'Owner', visibility: 'private', allowed_users: [],
  revision: 1, can_edit: true, ...patch,
})
beforeEach(() => { setActivePinia(createPinia()); vi.mocked(getPromptCatalog).mockReset() })

it('accepts generated Chinese layout names against the live catalog IDs and English aliases', () => {
  const layouts = fallbackItems('image.layout').filter(item => item.id.startsWith('image.layout.'))
  usePromptCatalogStore().catalog = makeCatalog(layouts.map(item => entry({
    id: item.id, category: 'layout', name: item.name, builtin: true,
    legacy_value: String(item.metadata.preview),
  })))
  for (const layout of layouts) {
    expect(resolvePromptValue('image', 'layout', layout.name)).toBe(layout.metadata.preview)
    expect(resolvePromptValue('image', 'layout', layout.id)).toBe(layout.id)
    expect(selectionItems('image', 'layout', layout.name).some(item => item.unavailable)).toBe(false)
  }
})

it('resolves only unique authorized layout names, without falling back to missing builtins', () => {
  const data = entry({ id: 'image.layout.data-conclusion', category: 'layout', name: '数据结论',
    builtin: true, legacy_value: 'data-conclusion' })
  const custom = entry({ id: 'custom-layout', category: 'layout', name: '数据结论' })
  usePromptCatalogStore().catalog = makeCatalog([data, custom])
  expect(() => resolvePromptValue('image', 'layout', '数据结论')).toThrow(/名称不唯一/)
  expect(resolvePromptValue('image', 'layout', data.id)).toBe(data.id)
  expect(resolvePromptValue('image', 'layout', 'data-conclusion')).toBe('data-conclusion')
  usePromptCatalogStore().catalog = makeCatalog([{ ...data, enabled: false }, { ...custom, can_use: false }])
  expect(() => resolvePromptValue('image', 'layout', '数据结论')).toThrow(/不可用/)
  usePromptCatalogStore().catalog = makeCatalog([{ ...custom, name: '我的布局' }])
  expect(resolvePromptValue('image', 'layout', '我的布局')).toBe('custom-layout')
})

it('prefers a layout ID over a conflicting name or legacy alias', () => {
  const items = makeCatalog([
    entry({ id: 'alias', category: 'layout', builtin: true, legacy_value: 'target', name: 'Alias' }),
    entry({ id: 'target', category: 'layout', name: 'Actual' }),
  ])['image.layout']
  expect(findLayoutItem(items, 'target')?.id).toBe('target')
})

it('filters permissions and honors order without restoring empty categories', () => {
  usePromptCatalogStore().catalog = makeCatalog([
    entry(), entry({ id: 'second' }), entry({ id: 'disabled', enabled: false }),
    entry({ id: 'private', can_use: false }),
  ], { 'image.style': { revision: 1, ids: ['second', 'custom-id'] } })
  expect(promptItems('image', 'style').map(item => item.id)).toEqual(['second', 'custom-id'])
  expect(promptItems('outline', 'tone')).toEqual([])
})

it('keeps builtin aliases and custom IDs while displaying edited names', () => {
  usePromptCatalogStore().catalog = makeCatalog([
    entry({ id: 'image.style.comic', builtin: true, legacy_value: 'comic', name: 'Edited comic' }),
    entry({ legacy_value: 'not-an-alias' }),
  ])
  expect(selectionItems('image', 'style', 'comic')[0]).toMatchObject({ name: 'Edited comic', value: 'comic' })
  expect(selectionItems('image', 'style', 'image.style.comic')[0].value).toBe('image.style.comic')
  expect(resolvePromptValue('image', 'style', 'custom-id')).toBe('custom-id')
  expect(() => resolvePromptValue('image', 'style', 'not-an-alias')).toThrow()
})

it('preserves unavailable selections and fails generation instead of replacing them', () => {
  expect(normalizeImageStyle({ preset: 'custom-id', applied: { preset: 'old-custom', notes: '' } }))
    .toMatchObject({ preset: 'custom-id', applied: { preset: 'old-custom' } })
  expect(copyPreferences({ style: 'custom-copy' }).style).toBe('custom-copy')
  expect(() => resolveCopyPreferences({ style: 'custom-copy' })).toThrow(/不可用/)
  expect(() => resolveImageStyle({ preset: 'custom-id', notes: '' })).toThrow(/不可用/)
  expect(selectionItems('image', 'style', 'custom-id').at(-1)?.unavailable).toBe(true)
})

it('resolves auto from current available styles, including custom recommendations', () => {
  usePromptCatalogStore().catalog = makeCatalog([
    entry({ id: 'image.style.auto', builtin: true, legacy_value: 'auto' }), entry(),
  ])
  expect(resolveImageStyle({ preset: 'auto', notes: '' }).preset).toBe('custom-id')
  expect(resolveImageStyle({ preset: 'custom-id', notes: '' }).preset).toBe('custom-id')
  usePromptCatalogStore().catalog = {}
  expect(() => resolveImageStyle({ preset: 'auto', notes: '' })).toThrow()
})

it('refreshes the usable catalog and fails closed after losing access', async () => {
  const store = usePromptCatalogStore()
  vi.mocked(getPromptCatalog).mockResolvedValue({ success: true, entries: [entry()], categories: [], orders: {} })
  await Promise.all([store.refresh(), store.refresh()])
  expect(getPromptCatalog).toHaveBeenCalledTimes(1)
  expect(getPromptCatalog).toHaveBeenCalledWith(false)
  expect(resolvePromptValue('image', 'style', 'custom-id')).toBe('custom-id')
  vi.mocked(getPromptCatalog).mockRejectedValue(new Error('Offline'))
  await store.refresh()
  expect(promptItems('image', 'style')).toEqual([])
  expect(store.error).toBeTruthy()
})

it('bootstraps offline but rejects a response from a previous login', async () => {
  const store = usePromptCatalogStore()
  vi.mocked(getPromptCatalog).mockRejectedValueOnce(new Error('Offline'))
  await store.refresh()
  expect(promptItems('image', 'style')).toHaveLength(43)
  let finish!: (value: Awaited<ReturnType<typeof getPromptCatalog>>) => void
  vi.mocked(getPromptCatalog).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const request = store.refresh()
  setToken('another-user')
  finish({ success: true, entries: [entry()], categories: [], orders: {} })
  await request
  expect(() => resolvePromptValue('image', 'style', 'custom-id')).toThrow()
})
