import { ref } from 'vue'
import type { Page } from '../api'
import { useGeneratorStore } from '../stores/generator'
import { useStudioSession } from '../stores/studioSession'

export function useOutlineEditor() {
  const store = useGeneratorStore()
  const session = useStudioSession()
  const pages = ref<Page[]>([])
  const error = ref('')
  let baseline = ''
  let revision = 0

  function open() {
    pages.value = store.outline.pages.map(page => ({ ...page }))
    baseline = JSON.stringify(store.outline)
    revision = session.revision
    error.value = ''
  }

  function save() {
    error.value = ''
    if (session.busy) {
      error.value = '任务正在进行，请结束后再保存。'
      return false
    }
    if (revision !== session.revision || baseline !== JSON.stringify(store.outline)) {
      error.value = '当前大纲已发生变化，请关闭弹窗后重新打开编辑。'
      return false
    }
    const empty = pages.value.findIndex(page => !page.content.trim())
    if (!pages.value.length || empty >= 0) {
      error.value = empty >= 0 ? `第 ${empty + 1} 页内容不能为空。` : '大纲不能为空。'
      return false
    }
    for (const page of pages.value) {
      store.updatePage(page.index, page.content)
    }
    session.dirty = true
    store.saveToStorage()
    return true
  }

  return { pages, error, open, save }
}
