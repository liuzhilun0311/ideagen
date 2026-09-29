import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import LayoutSelect from '../../src/components/workspace/LayoutSelect.vue'
import { getPromptCatalog, type PromptEntry } from '../../src/api/promptCenter'
import { makeCatalog, usePromptCatalogStore } from '../../src/features/promptCatalog'
import { renderer, root, nodes, text, settle } from './renderer'

vi.mock('../../src/api/promptCenter', () => ({ getPromptCatalog: vi.fn() }))

const entry: PromptEntry = {
  id: 'image.layout.data-conclusion', module: 'image', category: 'layout',
  name: '数据结论', legacy_value: 'data-conclusion', description: '突出已有数据和结论',
  content: 'Only existing facts', metadata: {}, builtin: true, enabled: true, can_use: true,
  owner_id: null, owner_name: 'System', visibility: 'public', allowed_users: [],
  revision: 1, can_edit: false,
}
let unmount: (() => void) | undefined
beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(getPromptCatalog).mockResolvedValue({ success: true, entries: [entry], categories: [], orders: {} })
  usePromptCatalogStore().catalog = makeCatalog([entry])
})
afterEach(() => { unmount?.(); root.children = [] })

it.each(['数据结论', 'data-conclusion', 'image.layout.data-conclusion'])('selects the existing layout for %s', async value => {
  const app = renderer.createApp(LayoutSelect, { modelValue: value })
  app.use(getActivePinia()!)
  app.mount(root)
  unmount = () => app.unmount()
  await settle()
  expect(nodes().find(node => node.tag === 'select')?.props.value).toBe('data-conclusion')
  expect(text()).not.toContain('不可用：')
  expect(text()).toContain('突出已有数据和结论')
})
