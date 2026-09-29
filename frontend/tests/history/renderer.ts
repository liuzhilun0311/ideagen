import { createRenderer, nextTick } from 'vue'

export class Node {
  children: Node[] = []
  parent: Node | null = null
  props: Record<string, any> = {}
  text = ''
  value: unknown
  selected = false
  checked = false
  selectedIndex = -1
  focus() {}
  addEventListener() {}
  removeEventListener() {}
  getRootNode() { return { activeElement: null } }
  get options() { return this.children }
  constructor(public tag: string) {}
  get tagName() { return this.tag.toUpperCase() }
}
export const root = new Node('root')
export const renderer = createRenderer<Node, Node>({
  createElement: tag => new Node(tag),
  createText: text => Object.assign(new Node('#text'), { text }),
  createComment: () => new Node('#comment'),
  setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.text = text; node.children = [] },
  parentNode: node => node.parent,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  patchProp: (node, key, _old, value) => { node.props[key] = value; if (key === 'value') node.value = value },
  insert: (node, parent, anchor) => {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
    node.parent = parent
  },
  remove: node => { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) },
  setScopeId: () => {},
  querySelector: () => root,
  insertStaticContent: (text, parent) => {
    const node = Object.assign(new Node('#static'), { text, parent })
    parent.children.push(node)
    return [node, node]
  },
})
export function nodes(node = root): Node[] { return [node, ...node.children.flatMap(child => nodes(child))] }
export function text(node = root): string { return node.text + node.children.map(text).join('') }
export function button(label: string) {
  return nodes().find(node => node.tag === 'button' && (text(node).trim() === label || node.props['aria-label'] === label))
}
export async function settle() { for (let i = 0; i < 20; i++) await nextTick() }
export function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}
