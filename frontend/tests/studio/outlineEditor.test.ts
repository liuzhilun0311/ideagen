import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useOutlineEditor } from '../../src/composables/useOutlineEditor'
import { useGeneratorStore } from '../../src/stores/generator'
import { useStudioSession } from '../../src/stores/studioSession'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  useGeneratorStore().setOutline('Original', [{ index: 0, type: 'cover', content: 'Original' }])
})

it('stages edits until saved and restores original content when reopened', () => {
  const editor = useOutlineEditor()
  editor.open()
  editor.pages.value[0]!.content = 'Unsaved'
  expect(useGeneratorStore().outline.raw).toBe('Original')
  editor.open()
  expect(editor.pages.value[0]!.content).toBe('Original')
})

it('saves pages, derived metadata and raw text to the current persisted draft', () => {
  const editor = useOutlineEditor()
  editor.open()
  editor.pages.value[0]!.content = 'Updated\n单页布局：清单\n视觉主体：城市'
  expect(editor.save()).toBe(true)
  const store = useGeneratorStore()
  expect(store.outline.raw).toBe(editor.pages.value[0]!.content)
  expect(store.outline.pages[0]!.layout).toBe('清单')
  expect(store.outline.pages[0]!.visual_focus).toBe('城市')
  expect(JSON.parse(localStorage.getItem('generator-state')!).outline.raw).toBe(store.outline.raw)
})

it('rejects empty pages without partially applying changes', () => {
  const editor = useOutlineEditor()
  editor.open()
  editor.pages.value[0]!.content = '   '
  expect(editor.save()).toBe(false)
  expect(useGeneratorStore().outline.raw).toBe('Original')
})

it.each(['busy', 'revision', 'changed'])('rejects edits when the source is %s', reason => {
  const editor = useOutlineEditor()
  editor.open()
  editor.pages.value[0]!.content = 'Changed'
  if (reason === 'busy') useStudioSession().homeBusy = true
  if (reason === 'revision') useStudioSession().revision++
  if (reason === 'changed') useGeneratorStore().updatePage(0, 'External')
  expect(editor.save()).toBe(false)
  expect(useGeneratorStore().outline.raw).not.toBe('Changed')
})
