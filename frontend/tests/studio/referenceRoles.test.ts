import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../../src/stores/generator'
import { usePageTrials } from '../../src/composables/usePageTrials'
import { generateCandidate } from '../../src/api/candidates'
import { h, nextTick, ref } from 'vue'
import ComposerInput from '../../src/components/home/ComposerInput.vue'
import { renderer, root, nodes } from '../history/renderer'

vi.mock('../../src/api/candidates', () => ({
  generateCandidate: vi.fn(async () => ({ status: 'ready' })),
  adoptCandidate: vi.fn(),
  listCandidates: vi.fn(async () => []),
}))

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

it.each([['subject'], []])('preserves explicit selection %j across reload', (...roles) => {
  const store = useGeneratorStore()
  store.referenceRoles = roles
  store.saveToStorage()
  setActivePinia(createPinia())
  expect(useGeneratorStore().referenceRoles).toEqual(roles)
})

it('starts a new generator with no reference role selected', () => {
  expect(useGeneratorStore().referenceRoles).toEqual([])
})

it('sends only subject to candidate generation', async () => {
  const store = useGeneratorStore()
  store.recordId = 'record'
  store.referenceRoles = ['subject']
  await usePageTrials(async () => true, vi.fn()).trial(0, { preset: 'pencil', notes: '' })
  expect(vi.mocked(generateCandidate).mock.calls[0]?.[8]).toEqual(['subject'])
})

it('can uncheck the last default then select only subject', async () => {
  const selected = ref(['style'])
  const app = renderer.createApp({
    render: () => h(ComposerInput, {
      modelValue: '', loading: false, referenceMode: selected.value,
      'onUpdate:referenceMode': (value: string[]) => { selected.value = value },
    }),
  })
  app.mount(root)
  try {
    const checkboxes = () => nodes().filter(node => node.props.type === 'checkbox')
    checkboxes()[0]!.props.onChange()
    await nextTick()
    expect(selected.value).toEqual([])
    checkboxes()[1]!.props.onChange()
    await nextTick()
    expect(selected.value).toEqual(['subject'])
    expect(checkboxes()[0]!.props.checked).toBe(false)
    expect(checkboxes()[1]!.props.checked).toBe(true)
  } finally {
    app.unmount()
  }
})

it('accepts selected, dropped and pasted images into the same list and rejects duplicates', async () => {
  const images = ref<File[]>([])
  const app = renderer.createApp({
    render: () => h(ComposerInput, {
      modelValue: '', loading: false, images: images.value,
      onImagesChange: (value: File[]) => { images.value = value },
    }),
  })
  app.mount(root)
  try {
    const file = new File(['image'], 'first.png', { type: 'image/png' })
    const input = nodes().find(node => node.props.id === 'creation-images')!
    input.props.onChange({ target: { files: [file], value: 'first.png' } })
    await nextTick()
    const zone = nodes().find(node => node.props.role === 'group')!
    zone.props.onDrop({ preventDefault: vi.fn(), dataTransfer: { files: [file] } })
    await nextTick()
    expect(images.value).toHaveLength(1)
    const second = new File(['second'], 'second.webp', { type: 'image/webp' })
    zone.props.onDrop({ preventDefault: vi.fn(), dataTransfer: { files: [second] } })
    await nextTick()
    const pasted = new File(['paste'], 'image.png', { type: 'image/png' })
    const preventDefault = vi.fn()
    zone.props.onPaste({ preventDefault, clipboardData: { items: [{ kind: 'file', getAsFile: () => pasted }] } })
    await nextTick()
    expect(preventDefault).toHaveBeenCalledOnce()
    expect(images.value.map(image => image.name)).toEqual(['first.png', 'second.webp', 'image.png'])
    expect(nodes().filter(node => node.tag === 'img')).toHaveLength(3)
  } finally { app.unmount() }
})

it.each([false, true])('validates uploads and respects locked=%s for drop and paste', async locked => {
  const changed = vi.fn()
  const app = renderer.createApp({
    render: () => h(ComposerInput, { modelValue: '', loading: false, locked, onImagesChange: changed }),
  })
  app.mount(root)
  try {
    const zone = nodes().find(node => node.props.role === 'group')!
    const files = [
      new File(['text'], 'text.txt', { type: 'text/plain' }),
      new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.png', { type: 'image/png' }),
      ...Array.from({ length: 6 }, (_, i) => new File(['png'], `${i}.png`, { type: 'image/png' })),
    ]
    zone.props.onDrop({ preventDefault: vi.fn(), dataTransfer: { files } })
    await nextTick()
    if (locked) {
      zone.props.onPaste({ preventDefault: vi.fn(), clipboardData: { items: [{ kind: 'file', getAsFile: () => files[2] }] } })
      expect(changed).not.toHaveBeenCalled()
    } else {
      expect(changed.mock.calls[0]![0]).toHaveLength(6)
      expect(nodes().find(node => node.props.role === 'alert')?.text).toContain('仅支持 JPEG')
      expect(nodes().find(node => node.props.role === 'alert')?.text).toContain('超过 5 MiB')
    }
  } finally { app.unmount() }
})
