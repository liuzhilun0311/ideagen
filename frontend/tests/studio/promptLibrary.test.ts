import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, createRenderer, nextTick, ref } from 'vue'
import { createPinia } from 'pinia'
import PromptManageView from '../../src/components/prompts/LegacyPromptLibrary.vue'
import { getPrompts, savePrompt, deletePrompt, type PromptItem } from '../../src/api/prompts'
import { useLibraryOrder } from '../../src/composables/useLibraryOrder'
import { libraryItemId } from '../../src/api/library'

vi.mock('../../src/api/prompts', () => ({
  getPrompts: vi.fn(), savePrompt: vi.fn(), deletePrompt: vi.fn(),
  saveBasePrompt: vi.fn(), setPromptUsers: vi.fn(), adminDeletePrompt: vi.fn(),
}))
vi.mock('../../src/api/auth', () => ({ listUsers: vi.fn() }))
vi.mock('../../src/composables/useLibraryOrder', () => ({ useLibraryOrder: vi.fn() }))
class Node {
  children: Node[] = []
  parent: Node | null = null
  props: Record<string, any> = {}
  text = ''
  value = ''
  addEventListener() {}
  getRootNode() { return { activeElement: null } }
  constructor(public tag: string) {}
}
const renderer = createRenderer<Node, Node>({
  createElement: tag => new Node(tag), createText: text => Object.assign(new Node('#text'), { text }),
  createComment: () => new Node('#comment'), setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.text = text }, parentNode: node => node.parent,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  patchProp: (node, key, _old, value) => { node.props[key] = value },
  insert: (node, parent, anchor) => {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
    node.parent = parent
  },
  remove: node => { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) },
  setScopeId: () => {},
  insertStaticContent: (text, parent) => {
    const node = Object.assign(new Node('#static'), { text, parent })
    parent.children.push(node)
    return [node, node]
  },
})
const base: PromptItem = { name: 'Default', content: 'Synthetic prompt', is_base: true, type: 'content' }
const duplicate: PromptItem = { ...base, name: 'Default copy', is_base: false, can_edit: true, owner_id: 'owner' }
let root: Node
let dispose: () => void
function nodes(node = root): Node[] { return [node, ...node.children.flatMap(child => nodes(child))] }
function button(text: string) { return nodes().find(node => node.tag === 'button' && (node.props['aria-label'] === text || node.text === text))! }
function library() { return vi.mocked(useLibraryOrder).mock.results[0]!.value as ReturnType<typeof useLibraryOrder> }
function rows() { return nodes().filter(node => node.props['data-reorder-id']).map(node => node.props['data-reorder-id']) }
async function settle() { for (let i = 0; i < 12; i++) await nextTick() }
async function mount() {
  root = new Node('root')
  const app = renderer.createApp(PromptManageView).use(createPinia())
  app.mount(root)
  dispose = () => app.unmount()
  await settle()
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('Document', class {})
  vi.stubGlobal('ShadowRoot', class {})
  vi.stubGlobal('document', { querySelector: () => ({ scrollIntoView: vi.fn() }) })
  vi.mocked(getPrompts).mockResolvedValue({ success: true, prompts: { outline: [], content: [base], image: [] } })
  vi.mocked(useLibraryOrder).mockImplementation((_resource, _kind, ids) => ({
    order: computed(() => ids.value), busy: ref(false), error: ref(''),
    refresh: vi.fn().mockResolvedValue(true), copy: vi.fn().mockResolvedValue(null),
    move: vi.fn().mockResolvedValue(true), invalidate: vi.fn(),
  }))
})
afterEach(() => { dispose?.(); vi.unstubAllGlobals() })

describe('prompt library integration', () => {
  it('copies a base prompt into an editable custom item and edits only that copy', async () => {
    await mount()
    vi.mocked(library().copy).mockResolvedValue({ id: libraryItemId(duplicate), name: duplicate.name })
    vi.mocked(getPrompts).mockResolvedValue({ success: true, prompts: { outline: [], content: [base, duplicate], image: [] } })
    await button('复制提示词 Default').props.onClick()
    await settle()
    expect(library().copy).toHaveBeenCalledWith(libraryItemId(base))
    expect(rows()).toEqual([libraryItemId(base), libraryItemId(duplicate)])
    const name = nodes().find(node => node.tag === 'input' && node.props.maxlength === '50')!
    expect(name.props['onUpdate:modelValue']).toBeTypeOf('function')
    name.props['onUpdate:modelValue']('Renamed copy')
    vi.mocked(savePrompt).mockResolvedValue({ success: true })
    await nextTick()
    await button('保存').props.onClick()
    expect(savePrompt).toHaveBeenCalledWith('content', 'Renamed copy', duplicate.content, duplicate.name)
    expect(deletePrompt).not.toHaveBeenCalled()
    expect(library().refresh).toHaveBeenCalled()
  })
  it('does not reopen a copied editor after category changes', async () => {
    await mount()
    let resolve!: (result: { id: string; name: string }) => void
    vi.mocked(library().copy).mockReturnValue(new Promise(done => { resolve = done }))
    const pending = button('复制提示词 Default').props.onClick()
    await button('图片提示词').props.onClick()
    resolve({ id: libraryItemId(duplicate), name: duplicate.name })
    await pending
    await settle()
    expect(getPrompts).toHaveBeenCalledTimes(1)
    expect(nodes().some(node => node.tag === 'textarea')).toBe(false)
  })
  it('reports a created copy if refreshing fails instead of opening the original', async () => {
    await mount()
    vi.mocked(library().copy).mockResolvedValue({ id: libraryItemId(duplicate), name: duplicate.name })
    vi.mocked(getPrompts).mockRejectedValue(new Error('offline'))
    await button('复制提示词 Default').props.onClick()
    await settle()
    expect(nodes().map(node => node.text).join('')).toContain('已创建')
    expect(nodes().some(node => node.tag === 'textarea')).toBe(false)
  })
})
