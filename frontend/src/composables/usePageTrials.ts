import { computed, ref, watch } from 'vue'
import { useGeneratorStore } from '../stores/generator'
import { useStudioSession } from '../stores/studioSession'
import { adoptCandidate, generateCandidate, listCandidates, type ImageCandidate } from '../api/candidates'
import { styleChoice, resolveImageStyle, type StyleChoice } from '../features/styles/catalog'
import { withToken } from '../api/image'
import { getToken } from '../api/token'
import { normalizeApiError, type AppError } from '../utils/errors'
import { imageParameters, readLayout } from '../features/generationOptions'
import { resolvePromptValue } from '../features/promptCatalog'

export function usePageTrials(save: () => Promise<boolean>, report: (error: AppError | null) => void) {
  const store = useGeneratorStore()
  const session = useStudioSession()
  const candidates = ref<ImageCandidate[]>([])
  const busy = ref(false)
  const stopping = ref(false)
  const notice = ref('')
  const missing = computed(() => store.outline.pages.filter(page =>
    !store.images.some(image => image.index === page.index && image.status === 'done' && image.url)))
  let load = 0
  let active = () => true
  async function refresh() {
    const record = store.recordId
    const ticket = ++load
    const token = getToken()
    if (!record) { candidates.value = []; return }
    try {
      const result = await listCandidates(record)
      if (ticket === load && record === store.recordId && token === getToken()) candidates.value = result
    } catch (cause) {
      if (ticket === load && token === getToken()) report(normalizeApiError(cause, '候选版本加载失败'))
    }
  }
  watch(() => store.recordId, () => { candidates.value = []; notice.value = ''; void refresh() }, { immediate: true })

  function expected(index: number) {
    const url = store.images.find(image => image.index === index)?.url
    return url ? decodeURIComponent(url.split('?')[0].split('/').pop() || '') : ''
  }
  async function publish(candidate: ImageCandidate) {
    const result = await adoptCandidate(store.recordId!, candidate.id, expected(candidate.index))
    if (!active()) return
    store.taskId = result.task_id
    const existing = store.images.find(image => image.index === candidate.index)
    if (existing) store.updateImage(candidate.index, result.image_url)
    else store.images.push({ index: candidate.index, url: withToken(result.image_url), status: 'done' })
    store.syncImageProgress()
    store.progress.total = store.outline.pages.length
    store.progress.status = store.progress.current === store.progress.total ? 'done' : 'idle'
    store.stage = store.progress.status === 'done' ? 'result' : 'outline'
    store.saveToStorage()
    await refresh()
  }
  async function operation(action: () => Promise<void>) {
    if (session.busy) return
    busy.value = true
    session.trialBusy = true
    stopping.value = false
    report(null)
    const token = getToken()
    const revision = session.revision
    active = () => token === getToken() && session.revision === revision
    try {
      if (!await save()) return
      if (!active()) return
      const record = store.recordId
      active = () => token === getToken() && session.revision === revision && store.recordId === record
      await action()
    } catch (cause) {
      if (active()) {
        report(normalizeApiError(cause, '图片操作失败，已有图片已保留'))
        notice.value = '操作失败，已采用的图片保持不变'
        await refresh()
      }
    } finally {
      busy.value = false
      session.trialBusy = false
      stopping.value = false
    }
  }
  async function trial(index: number, style: StyleChoice) {
    await operation(async () => {
      const choice = resolveImageStyle(style, store.imageStyle.recommendation)
      const page = store.outline.pages.find(page => page.index === index)
      if (page) resolvePromptValue('image', 'layout', readLayout(page.content))
      notice.value = `正在生成第 ${index + 1} 页候选图，本次 1 张`
      const candidate = await generateCandidate(store.recordId!, index, choice, store.imageModelName, '', [...store.userImages], imageParameters(store), store.useCoverAsReference, store.referenceRoles)
      if (!active()) return
      await refresh()
      notice.value = candidate.status === 'ready' ? '候选图已生成，尚未采用' : '请求仍在处理中，请稍后刷新候选版本'
    })
  }
  async function adopt(candidate: ImageCandidate) {
    await operation(async () => {
      await publish(candidate)
      if (!active()) return
      notice.value = '已采用此版本'
    })
  }
  async function applyStyle(candidate: ImageCandidate) {
    if (session.busy || candidate.status !== 'ready') return
    const previous = store.imageStyle
    store.imageStyle = { ...store.imageStyle, ...styleChoice(candidate.style) }
    if (await save()) {
      store.saveToStorage()
      notice.value = '已设为整套默认风格，已有图片保持不变'
    } else store.imageStyle = previous
  }
  async function batch(replace = false) {
    const pages = (replace ? store.outline.pages : missing.value).map(page => ({ ...page }))
    if (!pages.length || session.busy) return
    if (replace && !window.confirm(`重新生成整套 ${pages.length} 张图片？成功后逐页采用新版本，原版本保留在候选列表中。`)) return
    const style = { ...store.imageStyle }
    const provider = store.imageModelName
    const prompt = ''
    const references = [...store.userImages]
    const referenceRoles = [...store.referenceRoles]
    const parameters = imageParameters(store)
    const useReference = store.useCoverAsReference
    await operation(async () => {
      const choice = resolveImageStyle(style)
      for (const page of pages) resolvePromptValue('image', 'layout', readLayout(page.content))
      let completed = 0
      for (const page of pages) {
        if (stopping.value || !active()) break
        // Recheck publication before each missing-page request.
        if (!replace && expected(page.index)) continue
        notice.value = `本次 ${pages.length} 张，已完成 ${completed} 张，正在生成第 ${page.index + 1} 页`
        const candidate = await generateCandidate(store.recordId!, page.index, choice, provider, prompt, references, parameters, useReference, referenceRoles)
        if (!active()) return
        if (candidate.status !== 'ready') throw new Error('候选图尚未生成成功')
        await publish(candidate)
        if (!active()) return
        completed++
      }
      if (completed === pages.length && !stopping.value && store.images.every(image =>
        candidates.value.some(candidate => candidate.adopted && candidate.index === image.index
          && JSON.stringify(styleChoice(candidate.style)) === JSON.stringify(styleChoice(choice))))) {
        store.imageStyle.applied = choice
        store.saveToStorage()
        await save()
      }
      notice.value = `${stopping.value ? '已停止后续生成' : '生成结束'}，本次已采用 ${completed} 张图片`
    })
  }
  function clear() {
    ++load
    candidates.value = []
    notice.value = ''
  }
  return { candidates, busy, missing, notice, stopping, refresh, clear, trial, adopt, applyStyle, batch,
    stop: () => { stopping.value = true } }
}
