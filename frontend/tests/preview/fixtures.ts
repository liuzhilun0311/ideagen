import { AxiosError, CanceledError, type AxiosAdapter } from 'axios'
import type { AuthUser } from '../../src/api/auth'
import type { PromptItem, PromptKind } from '../../src/api/prompts'
import type { Config, HistoryDetail, Page } from '../../src/api/types'
import type { ProcessingPage, ProcessingState, ProcessingStrength } from '../../src/api/postprocessing'
import { libraryItemId, type LibraryResource, type LibraryCopy } from '../../src/api/library'
import type { ImageCandidate } from '../../src/api/candidates'
import { imageStyles } from '../../src/features/styles/catalog'
import { fallbackItems, type CatalogKey } from '../../src/features/promptCatalog'
import type { OutlineRun } from '../../src/api/outline'

export const previewUser: AuthUser = {
  id: 'preview-user', username: '开发预览', is_admin: true, created_at: '2026-09-09T10:00:00',
}
export const previewReader: AuthUser = {
  id: 'preview-reader', username: '演示成员', is_admin: false, created_at: previewUser.created_at,
}
export const previewPhotos = [
  '/assets/inspiration/city.jpg', '/assets/inspiration/coffee.jpg', '/assets/inspiration/plants.jpg',
]
export const previewPages: Page[] = [
  { index: 0, type: 'cover', content: '把周末，留给城市的一角\n不赶路的城市漫步\n街道、咖啡和那些不经意的美好。' },
  { index: 1, type: 'content', content: '在街角喝一杯咖啡\n选一家有窗边座位的小店，留一点时间观察街上的人。' },
  { index: 2, type: 'summary', content: '把一点绿色带回家\n散步的终点，是属于自己的生活节奏。' },
]
export const previewCopy = {
  titles: ['周末不赶路，去城市里慢慢走', '一场没有目的地的城市漫步'],
  copywriting: '关掉导航，走进一条还没去过的小巷。\n\n在街角喝一杯咖啡，经过花店时停下来。原来周末的好心情，不一定需要一张远行的车票。\n\n把时间留给自己，也留给生活里那些不起眼的小事。',
  tags: ['城市漫步', '周末日常', '生活记录'],
}
export const previewRecord: HistoryDetail = {
  id: 'preview-record', title: '周末城市漫步图文', created_at: '2026-09-09T10:00:00',
  updated_at: '2026-09-09T10:00:00',
  outline: { raw: previewPages.map(page => page.content).join('\n\n<page>\n\n'), pages: previewPages,
    growth_recommendation: {
      platform: 'douyin', goal: 'follow', layout: '清单', image_style: 'collage',
      aspect_ratio: '9:16', content_structure: '场景、体验、行动', reason: '用城市片段呈现适合周末实践的路线。',
    } },
  content: previewCopy, images: { task_id: 'preview-task', generated: ['0.png', '1.png', '2.png'] },
  status: 'completed', thumbnail: previewPhotos[0]!,
}

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value))
const abortError = () => new DOMException('Preview generation cancelled', 'AbortError')

export function previewDelay(search: string): number {
  const value = new URLSearchParams(search).get('delay')
  const parsed = value === null || value.trim() === '' ? 1200 : Number(value)
  return Number.isFinite(parsed) ? Math.min(15000, Math.max(0, parsed)) : 1200
}

export function previewImageUrl(source: string, origin: string): string {
  const url = new URL(source, origin)
  const match = url.origin === new URL(origin).origin
    ? url.pathname.match(/^\/api\/(?:images\/[^/]+|postprocessing\/images\/[^/]+\/[^/]+)\/(\d+)\.png$/) : null
  return match ? previewPhotos[Number(match[1]) % previewPhotos.length]! : source
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(abortError()); return }
    const abort = () => { clearTimeout(timer); reject(abortError()) }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', abort)
      resolve()
    }, ms)
    signal.addEventListener('abort', abort, { once: true })
  })
}

// Every factory owns its state. No storage, account service or provider is consulted.
export function createPreviewFixtures(delay = 1200, options: { candidateDelay?: number; processingDelay?: number; failIndices?: number[]; reader?: boolean; shared?: boolean; revokeAfterMs?: number; missingWork?: boolean } = {}) {
  const candidates = new Map<string, ImageCandidate[]>()
  const outlineRuns: OutlineRun[] = []
  delay = previewDelay(`delay=${delay}`)
  let sequence = 0
  let currentUser: AuthUser | null = clone(options.reader ? previewReader : previewUser)
  const users = new Map<string, AuthUser>([
    [previewUser.id, clone(previewUser)],
    [previewReader.id, clone(previewReader)],
  ])
  const passwords = new Map<string, string>()
  const records = new Map<string, HistoryDetail>([[previewRecord.id, clone(previewRecord)]])
  if (options.missingWork) records.clear()
  const recordOwners = new Map<string, string>([[previewRecord.id, previewUser.id]])
  const grants = new Map<string, Set<string>>([[previewRecord.id, new Set(options.shared ? [previewReader.id] : [])]])
  let revokeAt: number | null = null
  const ownRecord = (record: HistoryDetail) => recordOwners.get(record.id) === currentUser?.id
  const canEditRecord = (record: HistoryDetail) => Boolean(currentUser && (currentUser.is_admin || ownRecord(record)))
  const grantedRecord = (record: HistoryDetail) => Boolean(currentUser
    && users.get(recordOwners.get(record.id) || '')?.is_admin && grants.get(record.id)?.has(currentUser.id))
  const canReadRecord = (record: HistoryDetail) => canEditRecord(record) || grantedRecord(record)
  const canShareRecord = (record: HistoryDetail) => Boolean(currentUser?.is_admin && ownRecord(record))
  function capabilities(record: HistoryDetail) {
    const owner = users.get(recordOwners.get(record.id) || '')
    return {
      user_id: owner?.id, owner: owner ? { id: owner.id, username: owner.username } : undefined,
      can_edit: canEditRecord(record), can_share: canShareRecord(record),
      is_shared: Boolean(owner?.is_admin && grants.get(record.id)?.size),
      ...(canShareRecord(record) ? { shared_count: grants.get(record.id)?.size || 0 } : {}),
    }
  }
  function visibleRecords(source: string | null) {
    return [...records.values()].filter(record => source === 'shared'
      ? !ownRecord(record) && grantedRecord(record) : canEditRecord(record))
  }
  function referencedRecords(data: Record<string, any>) {
    return [...records.values()].filter(record => record.id === data.record_id || (
      data.task_id && record.images.task_id === data.task_id
    ))
  }
  const tasks = new Map<string, string[]>([['preview-task', ['0.png', '1.png', '2.png']]])
  const processing = new Map<string, ProcessingState>()
  const sourceRevisions = new Map<string, number>()
  const adoptionRevisions = new Map<string, number>()
  const jobs = new Map<string, { recordId: string; index: number; source: string; strength: ProcessingStrength; started: number; adoption: number }>()
  const processingDelay = Math.max(100, options.processingDelay ?? 1800)
  const failIndices = new Set(options.failIndices || [])
  const pageKey = (id: string, index: number) => JSON.stringify([id, index])
  function processingState(record: HistoryDetail): ProcessingState {
    let state = processing.get(record.id)
    if (!state) {
      state = { success: true, preferences: { automatic: false, strength: 'light' }, pages: [] }
      processing.set(record.id, state)
    }
    const filenames = record.images.generated || []
    const pages: ProcessingPage[] = []
    for (const page of record.outline.pages) {
      if (!filenames.includes(`${page.index}.png`) || !record.images.task_id) continue
      const key = pageKey(record.id, page.index)
      const source = `${record.images.task_id}:${page.index}:${sourceRevisions.get(key) || 0}`
      const previous = state.pages.find(item => item.index === page.index && item.source_revision === source)
      pages.push(previous || {
        index: page.index, source_revision: source,
        original_url: candidates.get(record.id)?.find(item => item.index === page.index && item.adopted)?.image_url
          || `/api/images/${record.images.task_id}/${page.index}.png?revision=${sourceRevisions.get(key) || 0}`,
        processed_url: null, strength: null, status: 'idle', error: '', adopted: 'original',
      })
    }
    state.pages = pages
    for (const page of pages) {
      const key = pageKey(record.id, page.index)
      const job = jobs.get(key)
      if (!job || job.source !== page.source_revision) continue
      const elapsed = Date.now() - job.started
      if (elapsed < processingDelay) page.status = 'queued'
      else if (elapsed < processingDelay * 2) page.status = 'processing'
      else {
        jobs.delete(key)
        if (failIndices.has(page.index)) {
          page.status = 'error'
          page.error = '模拟处理失败，可重试；原图与此前处理结果仍保留。'
        } else {
          page.status = 'done'
          page.error = ''
          page.strength = job.strength
          page.processed_url = `/api/postprocessing/images/${record.id}/${encodeURIComponent(job.source)}-${job.started}/${page.index}.png`
          if ((adoptionRevisions.get(key) || 0) === job.adoption) page.adopted = 'processed'
        }
      }
    }
    return state
  }
  function enqueue(record: HistoryDetail, indices: number[], strength: ProcessingStrength, force: boolean) {
    const state = processingState(record)
    for (const page of state.pages) {
      if (!indices.includes(page.index) || ['queued', 'processing'].includes(page.status) || (!force && page.processed_url)) continue
      const key = pageKey(record.id, page.index)
      jobs.set(key, { recordId: record.id, index: page.index, source: page.source_revision, strength,
        started: Date.now(), adoption: adoptionRevisions.get(key) || 0 })
      page.status = 'queued'
      page.error = ''
    }
    return state
  }
  function publishOriginal(taskId: string, index: number, recordId?: string) {
    records.forEach(record => {
      if (recordId ? record.id !== recordId : record.images.task_id !== taskId) return
      record.images.task_id = taskId
      if (!record.images.generated.includes(`${index}.png`)) record.images.generated.push(`${index}.png`)
      const key = pageKey(record.id, index)
      sourceRevisions.set(key, (sourceRevisions.get(key) || 0) + 1)
      jobs.delete(key)
      const state = processingState(record)
      if (state.preferences.automatic) enqueue(record, [index], state.preferences.strength, false)
    })
  }
  const running = new Set<AbortController>()
  const prompts: Record<PromptKind, PromptItem[]> = { outline: [], content: [], image: [] }
  for (const kind of ['outline', 'content', 'image'] as const) {
    prompts[kind].push({
      name: '默认提示词', content: `开发预览 ${kind}：{topic}`, type: kind,
      is_base: true, can_edit: true, owner: null, owner_id: null, is_shared: false, allowed_users: [],
    })
  }
  const config: Config = {
    text_generation: { active_provider: 'preview-text', providers: {
      'preview-text': { type: 'openai_compatible', model: 'preview-text', enabled: true, display_name: '演示文本模型', api_key_masked: 'preview-****', allowed_users: [] },
    } },
    image_generation: { active_provider: 'preview-image', providers: {
      'preview-image': { type: 'image_api', model: 'preview-image', enabled: true, display_name: '演示图片模型', api_key_masked: 'preview-****', allowed_users: [] },
    } },
  }
  const ok = (data: object = {}) => ({ status: 200, data: clone({ success: true, ...data }) })
  const fail = (status: number, message: string) => ({
    status, data: { success: false, error: message, error_message: message },
  })
  const listItem = (record: HistoryDetail) => {
    const { id, title, created_at, updated_at, status, thumbnail } = record
    return {
      id, title, created_at, updated_at, status,
      thumbnail: thumbnail?.startsWith('/assets/') ? record.images.generated[0] || null : thumbnail,
      page_count: record.outline.pages.length, task_id: record.images.task_id, ...capabilities(record),
    }
  }
  const publicProvider = (value: Record<string, unknown>, previous: Record<string, unknown> = {}) => {
    const result = { ...clone(value) }
    result.api_key_masked = value.api_key ? 'preview-****' : previous.api_key_masked || value.api_key_masked || ''
    delete result.api_key
    return result
  }
  const libraryOrders = new Map<string, { userId: string; resource: LibraryResource; kind: string; revision: number; order: string[] }>()
  const copyRequests = new Map<string, { resource: LibraryResource; kind: string; source: string; revision: number; response: LibraryCopy }>()
  function visiblePrompts(kind: PromptKind): PromptItem[] {
    const ownNames = new Set(prompts[kind].filter(item => item.owner_id === currentUser?.id).map(item => item.name))
    return prompts[kind].filter(item => item.is_base || item.owner_id === currentUser?.id
      || (!ownNames.has(item.name) && users.has(item.owner_id || '')
        && (currentUser?.is_admin || item.allowed_users?.includes(currentUser?.username || ''))))
      .map(item => ({
        ...clone(item),
        can_edit: item.is_base ? !!currentUser?.is_admin : item.owner_id === currentUser?.id,
        is_shared: !item.is_base && item.owner_id !== currentUser?.id,
        allowed_users: currentUser?.is_admin || item.owner_id === currentUser?.id ? clone(item.allowed_users || []) : [],
      }))
  }
  function visibleModels(kind: string) {
    const section = kind === 'text' ? config.text_generation : config.image_generation
    return Object.fromEntries(Object.entries(section.providers).filter(([, provider]) =>
      currentUser?.is_admin || provider.allowed_users?.includes(currentUser?.username || '')))
  }
  function visibleIds(resource: LibraryResource, kind: string): string[] {
    return resource === 'models' ? Object.keys(visibleModels(kind)) : visiblePrompts(kind as PromptKind).map(libraryItemId)
  }
  function libraryState(resource: LibraryResource, kind: string) {
    const key = JSON.stringify([currentUser!.id, resource, kind])
    let state = libraryOrders.get(key)
    if (!state) {
      state = { userId: currentUser!.id, resource, kind, revision: 0, order: [] }
      libraryOrders.set(key, state)
    }
    return state
  }
  function effectiveOrder(resource: LibraryResource, kind: string): string[] {
    const visible = visibleIds(resource, kind)
    return [...new Set([...libraryState(resource, kind).order.filter(id => visible.includes(id)), ...visible])]
  }
  function copyName(source: string, occupied: string[]): string {
    for (let number = 1; ; number++) {
      const suffix = number === 1 ? '（副本）' : `（副本${number}）`
      const name = Array.from(source).slice(0, 50 - Array.from(suffix).length).join('') + suffix
      if (!occupied.includes(name)) return name
    }
  }
  function renamePrompt(kind: PromptKind, item: PromptItem, name: string, content: string) {
    const oldId = libraryItemId(item)
    const ownerState = libraryState('prompts', kind)
    const ownerOrder = effectiveOrder('prompts', kind)
    item.name = name
    item.content = content
    const newId = libraryItemId(item)
    if (oldId === newId) return
    ownerState.order = ownerOrder
    for (const state of libraryOrders.values()) {
      if (state.resource !== 'prompts' || state.kind !== kind || !state.order.includes(oldId)) continue
      state.order = [...new Set(state.order.filter(id => id !== newId).map(id => id === oldId ? newId : id))]
      state.revision++
    }
  }
  function operation(signal?: AbortSignal | null) {
    const controller = new AbortController()
    const abort = () => controller.abort()
    if (signal?.aborted) abort()
    else signal?.addEventListener('abort', abort, { once: true })
    running.add(controller)
    return {
      controller,
      cleanup() {
        signal?.removeEventListener('abort', abort)
        running.delete(controller)
      },
    }
  }

  // The request body is an untrusted JSON boundary, just like the backend views.
  async function request(method: string, url: URL, data: Record<string, any>, signal?: AbortSignal | null) {
    const path = url.pathname
    if (method === 'GET' && path === '/api/prompt-center') {
      const entries = ['image.style', 'image.layout', 'outline.organization', 'outline.audience',
        'outline.tone', 'content.style', 'content.structure', 'content.length'].flatMap(key =>
        fallbackItems(key as CatalogKey).map(item => ({
          id: item.id.startsWith(`${key}.`) ? item.id : `${key}.${item.id}`,
          module: key.split('.')[0], category: key.split('.')[1], name: item.name,
          description: item.description, content: item.content || '',
          metadata: item.metadata, legacy_value: item.legacyValue,
          builtin: true, enabled: true, visibility: 'public', allowed_users: [],
          owner_id: null, owner_name: '', revision: 1, can_edit: true, can_use: true,
        })))
      return ok({ entries, categories: [], orders: {} })
    }
    if (method === 'POST' && path === '/api/content/preview') {
      return ok({ prompt: `开发预览（模拟，不调用模型）\n主题：${data.topic}\n当前逐页内容：${data.outline}\n文案选项：${JSON.stringify(data.copy_preferences)}\n保持事实一致，输出标题、正文和标签。`,
        preferences: data.copy_preferences, audience: data.generation_preferences || { audience: '自动判断' } })
    }
    if (method === 'POST' && path === '/api/image-prompt/preview') {
      const parameters = data.image_parameters || { resolution: '1K', aspect_ratio: '3:4', quality: 'low', output_format: 'png' }
      return ok({ prompt: `开发预览（模拟，不调用模型）\n本页内容：${data.page?.content}\n最终风格：${data.image_style?.preset}\n风格补充：${data.image_style?.notes || ''}\n图片规格以接口参数为准。`,
        parameters, gpt_images_parameters: { size: '768x1024', quality: parameters.quality, output_format: parameters.output_format, n: 1 },
        references: { count: data.reference_count || 0, user_count: data.reference_count || 0, cover_count: 0, mode: data.reference_count ? 'reference' : 'text_to_image' } })
    }
    if (method === 'POST' && path === '/api/outline/preview') {
      return ok({ prompt: `开发预览（模拟，不调用模型）\n主题：${data.topic}\n组织方式：${data.organization}\n目标受众：${data.audience}\n表达语气：${data.tone}\n参考资料：${data.reference_content || ''}`, image_count: data.image_count || 0 })
    }
    if (method === 'GET' && path === '/api/outline/records') {
      return ok({ records: outlineRuns })
    }
    const outlineDiagnostic = path.match(/^\/api\/outline\/records\/([^/]+)\/diagnostics$/)
    if (method === 'GET' && outlineDiagnostic) {
      const run = outlineRuns.find(item => item.id === outlineDiagnostic[1])
      if (!run) return fail(404, '大纲记录不存在')
      return ok({ record_id: run.id, status: run.status, response_available: true, events: [
        { at: run.created_at, source: 'upstream', event: 'request', model: run.model,
          body: { model: run.model, input: run.prompt, stream: false } },
        { at: run.created_at, source: 'upstream', event: 'response', http_status: 200,
          body: { status: 'completed', output_text: previewRecord.outline.raw } },
      ] })
    }
    const candidateMatch = path.match(/^\/api\/image-candidates\/([^/]+)(?:\/([^/]+)\/adopt)?$/)
    if (candidateMatch) {
      const record = records.get(candidateMatch[1]!)
      if (!record || !canEditRecord(record)) return fail(403, '候选版本不可访问')
      const items = candidates.get(record.id) || []
      if (method === 'GET') return ok({ success: true, candidates: clone(items) })
      if (method === 'POST' && candidateMatch[2]) {
        const candidate = items.find(item => item.id === candidateMatch[2])
        if (!candidate) return fail(404, '候选版本不存在')
        items.filter(item => item.index === candidate.index).forEach(item => { item.adopted = item.id === candidate.id })
        record.images.generated[candidate.index] = `${candidate.index}.png`
        const key = pageKey(record.id, candidate.index)
        sourceRevisions.set(key, (sourceRevisions.get(key) || 0) + 1)
        return ok({ success: true, task_id: record.images.task_id || 'preview-task',
          image_url: candidate.image_url, candidate })
      }
      if (method === 'POST') {
        const page = record.outline.pages.find(page => page.index === data.index)
        if (!page) return fail(400, '页面不存在')
        if (options.candidateDelay) await wait(options.candidateDelay, signal || new AbortController().signal)
        const candidate: ImageCandidate = {
          id: data.request_id, index: page.index, style: data.image_style,
          prompt: `预览模拟提示词：${data.image_style.preset}\n${page.content}`,
          provider: data.provider_name, status: 'ready', image_url: `/assets/styles/${imageStyles.find(s => s.id === data.image_style.preset)?.preview || 'infographic'}.png`,
          adopted: false, stale: false, created_at: new Date().toISOString(),
        }
        items.push(candidate)
        candidates.set(record.id, items)
        return ok({ success: true, candidate: clone(candidate) })
      }
    }
    // Optional deterministic revocation after opening a recipient preview.
    if (revokeAt !== null && Date.now() >= revokeAt) {
      grants.get(previewRecord.id)?.clear()
      revokeAt = null
    }
    if (path.startsWith('/api/history') || path.startsWith('/api/postprocessing')) {
      if (!currentUser) return fail(401, '请先登录')
    }
    if (method === 'POST' && ['/api/outline', '/api/content', '/api/regenerate', '/api/retry'].includes(path)) {
      if (!currentUser) return fail(401, '请先登录')
      if (referencedRecords(data).some(record => !canEditRecord(record))) return fail(403, '共享作品仅可查看')
    }
    const imageMatch = path.match(/^\/api\/images\/([^/]+)\/(\d+)\.png$/)
    const processedMatch = path.match(/^\/api\/postprocessing\/images\/([^/]+)\/[^/]+\/(\d+)\.png$/)
    if (imageMatch || processedMatch) {
      const record = imageMatch
        ? [...records.values()].find(record => record.images.task_id === imageMatch[1])
        : records.get(processedMatch![1]!)
      const filename = `${(imageMatch || processedMatch)![2]}.png`
      if (!record || !canReadRecord(record) || !record.images.generated.includes(filename)) return fail(403, '图片不可访问')
      return ok({ image: filename })
    }
    if (/^\/api\/(?:library|prompts|config)(?:\/|$)/.test(path) && !currentUser) return fail(401, 'Login required')
    const libraryMatch = path.match(/^\/api\/library\/(models|prompts)\/([^/]+)(?:\/(copy|reorder))?$/)
    if (libraryMatch) {
      const resource = libraryMatch[1] as LibraryResource
      const kind = decodeURIComponent(libraryMatch[2]!)
      const action = libraryMatch[3]
      if (!(resource === 'models' ? ['text', 'image'] : ['outline', 'content', 'image']).includes(kind)) {
        return fail(404, 'Unknown resource or category')
      }
      const state = libraryState(resource, kind)
      const order = effectiveOrder(resource, kind)
      if (method === 'GET' && !action) return ok({ revision: state.revision, order })
      if (method !== 'POST' || !action) return fail(405, 'Method not supported')
      if (!Number.isInteger(data.revision) || data.revision < 0) return fail(400, 'Invalid revision')
      if (action === 'reorder') {
        if (!Array.isArray(data.order) || data.order.some((id: unknown) => typeof id !== 'string')
          || new Set(data.order).size !== data.order.length) return fail(400, 'Expected unique IDs')
        if (state.revision !== data.revision) return fail(409, 'The list has changed. Refresh before retrying.')
        if (data.order.length !== order.length || data.order.some((id: string) => !order.includes(id))) {
          return fail(400, 'Order must contain exactly the visible IDs')
        }
        state.order = [...data.order]
        state.revision++
        return ok({ revision: state.revision, order: state.order })
      }
      if (typeof data.source !== 'string' || !data.source || typeof data.request_id !== 'string'
        || !data.request_id.trim() || data.request_id.length > 128) return fail(400, 'Invalid copy request')
      const requestKey = JSON.stringify([currentUser!.id, data.request_id])
      const previous = copyRequests.get(requestKey)
      if (previous && (previous.resource !== resource || previous.kind !== kind
        || previous.source !== data.source || previous.revision !== data.revision)) {
        return fail(409, 'Request ID already used for a different request')
      }
      if (resource === 'models' && !currentUser!.is_admin) return fail(403, 'Only configurations you manage can be copied')
      if (!order.includes(data.source) || (previous && !order.includes(previous.response.created.id))) {
        return fail(404, 'Source or copy is no longer available')
      }
      if (previous) return ok(previous.response)
      if (state.revision !== data.revision) return fail(409, 'The list has changed. Refresh before retrying.')
      let created: LibraryCopy['created']
      if (resource === 'models') {
        const providers = (kind === 'text' ? config.text_generation : config.image_generation).providers
        const name = copyName(data.source, Object.keys(providers))
        const source = providers[data.source]!
        const occupiedLabels = Object.entries(providers).map(([id, provider]) => String(provider.provider_label || id))
        const occupiedDisplays = Object.entries(providers).map(([id, provider]) => String(provider.display_name || id))
        let label: string
        let displayName: string
        do {
          label = copyName(String(source.provider_label || data.source), occupiedLabels)
          displayName = `${label}:${source.model || ''}`
          occupiedLabels.push(label)
        } while (occupiedDisplays.includes(displayName))
        providers[name] = {
          ...clone(source), provider_label: label, display_name: displayName, enabled: false, allowed_users: [],
        }
        if (kind === 'image' && !providers[name].type) providers[name].type = data.source
        created = { id: name, name }
      } else {
        const items = prompts[kind as PromptKind]
        const source = visiblePrompts(kind as PromptKind).find(item => libraryItemId(item) === data.source)!
        const name = copyName(source.name, items.filter(item => item.owner_id === currentUser!.id).map(item => item.name))
        const item: PromptItem = {
          name, content: source.content, type: kind as PromptKind, is_base: false, can_edit: true,
          owner: currentUser!.username, owner_id: currentUser!.id, is_shared: false, allowed_users: [],
        }
        items.push(item)
        created = { id: libraryItemId(item), name }
      }
      order.splice(order.indexOf(data.source) + 1, 0, created.id)
      state.order = order
      state.revision++
      const response: LibraryCopy = { success: true, revision: state.revision, order, created }
      copyRequests.set(requestKey, { resource, kind, source: data.source, revision: data.revision, response: clone(response) })
      return ok(response)
    }
    const processingMatch = path.match(/^\/api\/postprocessing\/([^/]+)$/)
    if (processingMatch) {
      const record = records.get(decodeURIComponent(processingMatch[1]!))
      if (!record) return fail(404, 'Preview record not found')
      if (!canReadRecord(record)) return fail(403, '作品不可访问或共享已取消')
      const state = processingState(record)
      if (method === 'GET') return ok(state)
      if (method !== 'POST') return fail(405, 'Method not supported')
      if (!canEditRecord(record)) return fail(403, '共享作品仅可查看')
      if (data.action === 'preferences') {
        if (typeof data.automatic !== 'boolean' || !['light', 'medium', 'heavy'].includes(data.strength)) return fail(400, 'Invalid preferences')
        state.preferences = { automatic: data.automatic, strength: data.strength }
      } else if (data.action === 'process') {
        if (!Array.isArray(data.indices) || data.indices.some((index: unknown) => !Number.isInteger(index) || !state.pages.some(page => page.index === index))
          || !['light', 'medium', 'heavy'].includes(data.strength) || typeof data.force !== 'boolean') return fail(400, 'Invalid processing request')
        enqueue(record, data.indices, data.strength, data.force)
      } else if (data.action === 'adopt') {
        const page = state.pages.find(page => page.index === data.index)
        if (!page || page.source_revision !== data.source_revision) return fail(409, 'Source revision changed')
        if (!['original', 'processed'].includes(data.version) || (data.version === 'processed' && !page.processed_url)) return fail(400, 'Version unavailable')
        page.adopted = data.version
        const key = pageKey(record.id, page.index)
        adoptionRevisions.set(key, (adoptionRevisions.get(key) || 0) + 1)
      } else return fail(400, 'Unknown processing action')
      return ok(state)
    }
    if (method === 'POST' && path === '/api/generate/cancel') {
      running.forEach(controller => controller.abort())
      return ok()
    }
    if (method === 'POST' && ['/api/outline', '/api/content', '/api/regenerate'].includes(path)) {
      const op = operation(signal)
      try {
        await wait(delay, op.controller.signal)
        if (path === '/api/outline') {
          const run: OutlineRun = {
            id: `preview-outline-${++sequence}`, created_at: new Date().toISOString(),
            prompt: `开发预览：${data.topic}`, preferences: data as OutlineRun['preferences'],
            provider: 'preview-text', model: 'preview-text', status: 'succeeded', sent: true, references: [],
          }
          outlineRuns.unshift(run)
          return ok({ outline: previewRecord.outline.raw, pages: previewPages, has_images: Boolean(data.images),
            organization: data.organization && data.organization !== '自动' ? data.organization : '清单合集',
            growth_recommendation: clone(previewRecord.outline.growth_recommendation),
            generation_record: run,
            style_recommendation: { preset: 'collage', reason: '以编辑式构图串联城市片段。', alternatives: ['photography', 'sketch-note'] } })
        }
        if (path === '/api/content') return ok(previewCopy)
        if (!Number.isInteger(data.page?.index)) return fail(400, 'Missing page index')
        publishOriginal(data.task_id || 'preview-task', data.page.index, data.record_id)
        return ok({ index: data.page.index, image_url: previewPhotos[data.page.index % previewPhotos.length] })
      } finally { op.cleanup() }
    }
    if (path === '/api/auth/me' && method === 'GET') return ok({ user: currentUser })
    if (path === '/api/auth/logout' && method === 'POST') { currentUser = null; return ok() }
    if (path === '/api/auth/login' && method === 'POST') {
      const user = [...users.values()].find(user => user.username === data.username)
      if (!user || !data.password || (passwords.has(user.id) && passwords.get(user.id) !== data.password)) return fail(400, 'Invalid preview credentials')
      currentUser = user
      return ok({ token: 'local-preview-not-a-real-token', user })
    }
    if (path === '/api/auth/register' && method === 'POST') {
      if (!data.username?.trim() || typeof data.password !== 'string' || data.password.length < 6) return fail(400, 'Username and a six-character password are required')
      if ([...users.values()].some(user => user.username === data.username.trim())) return fail(400, 'Username already exists')
      const user: AuthUser = { id: `preview-user-${++sequence}`, username: data.username.trim(), is_admin: false, created_at: new Date().toISOString() }
      users.set(user.id, user)
      passwords.set(user.id, data.password)
      return ok({ user })
    }
    if (path === '/api/auth/users' && method === 'GET') {
      return currentUser?.is_admin ? ok({ users: [...users.values()] }) : fail(403, 'Administrator required')
    }
    const userMatch = path.match(/^\/api\/auth\/users\/([^/]+)(\/password)?$/)
    if (userMatch) {
      if (!currentUser?.is_admin) return fail(403, 'Administrator required')
      const id = userMatch[1]!
      if (!users.has(id)) return fail(404, 'User not found')
      if (method === 'DELETE' && !userMatch[2]) {
        if (id === currentUser.id) return fail(400, 'Cannot delete the current user')
        users.delete(id)
        passwords.delete(id)
        return ok({ message: 'Preview user deleted' })
      }
      if (method === 'POST' && userMatch[2]) {
        if (typeof data.new_password !== 'string' || data.new_password.length < 6) return fail(400, 'Password must contain six characters')
        passwords.set(id, data.new_password)
        return ok({ message: 'Preview password updated' })
      }
    }
    if (path === '/api/prompts' && method === 'GET') {
      return ok({ prompts: Object.fromEntries((['outline', 'content', 'image'] as const).map(kind => {
        const byId = new Map(visiblePrompts(kind).map(item => [libraryItemId(item), item]))
        return [kind, effectiveOrder('prompts', kind).map(id => byId.get(id)!)]
      })) })
    }
    if (method === 'POST' && ['/api/prompts/save', '/api/prompts/delete', '/api/prompts/base/save', '/api/prompts/admin/users', '/api/prompts/admin/delete'].includes(path)) {
      const kind = data.kind as PromptKind
      if (!Object.prototype.hasOwnProperty.call(prompts, kind)) return fail(400, 'Invalid prompt kind')
      const items = prompts[kind]
      if (path === '/api/prompts/base/save') {
        if (!currentUser?.is_admin) return fail(403, 'Administrator required')
        if (!data.content?.trim()) return fail(400, 'Content required')
        items.find(item => item.is_base)!.content = data.content
        return ok()
      }
      if (typeof data.name !== 'string' || !data.name.trim() || data.name.trim() === '默认提示词'
        || Array.from(data.name.trim()).length > 50) return fail(400, 'Invalid prompt name')
      const name = data.name.trim()
      const ownerId = path.includes('/admin/') ? data.owner_id : currentUser?.id
      const index = items.findIndex(item => item.name === name && item.owner_id === ownerId)
      if (path === '/api/prompts/save') {
        if (typeof data.content !== 'string' || !data.content.trim() || Array.from(data.content).length > 20000) return fail(400, 'Invalid content')
        if (data.original_name !== undefined) {
          if (typeof data.original_name !== 'string' || !data.original_name.trim() || data.original_name.trim() === '默认提示词') {
            return fail(400, 'Invalid original name')
          }
          const source = items.find(item => item.name === data.original_name.trim() && item.owner_id === ownerId && !item.is_base)
          if (!source) return fail(400, 'Original prompt no longer exists')
          if (index >= 0 && items[index] !== source) return fail(400, 'Name already exists')
          renamePrompt(kind, source, name, data.content)
          return ok()
        }
        if (index >= 0) items[index]!.content = data.content
        else items.push({ name, content: data.content, type: kind, is_base: false, can_edit: true, owner: currentUser?.username, owner_id: currentUser?.id, is_shared: false, allowed_users: [] })
      } else {
        if (path.includes('/admin/') && !currentUser?.is_admin) return fail(403, 'Administrator required')
        if (index < 0) return fail(404, 'Prompt not found')
        if (path.endsWith('/users')) {
          if (!Array.isArray(data.allowed_users)) return fail(400, 'Expected allowed_users')
          items[index]!.allowed_users = clone(data.allowed_users)
        } else items.splice(index, 1)
      }
      return ok()
    }
    if (path === '/api/config' && method === 'GET') {
      return ok({ config: Object.fromEntries((['text', 'image'] as const).map(kind => {
        const section = config[`${kind}_generation`]
        const visible = visibleModels(kind)
        return [`${kind}_generation`, {
          ...section,
          active_provider: Object.prototype.hasOwnProperty.call(visible, section.active_provider) ? section.active_provider : '',
          providers: Object.fromEntries(effectiveOrder('models', kind).map(id => [id, visible[id]])),
        }]
      })) })
    }
    if (path === '/api/config' && method === 'POST') {
      if (!currentUser?.is_admin) return fail(403, 'Administrator required')
      for (const kind of ['text_generation', 'image_generation'] as const) {
        if (!data[kind]) continue
        const section = data[kind]
        if (!section.providers || typeof section.active_provider !== 'string') return fail(400, 'Invalid provider configuration')
      }
      for (const kind of ['text_generation', 'image_generation'] as const) {
        if (!data[kind]) continue
        config[kind] = {
          active_provider: data[kind].active_provider,
          providers: Object.fromEntries(Object.entries(data[kind].providers).map(([name, value]) => [
            name, publicProvider(value as Record<string, unknown>, config[kind].providers[name]),
          ])),
        }
      }
      return ok({ message: 'Preview configuration saved' })
    }
    if (method === 'POST' && ['/api/config/providers/save', '/api/config/providers/users'].includes(path)) {
      if (!currentUser?.is_admin) return fail(403, 'Administrator required')
      if (!['text', 'image'].includes(data.kind)) return fail(400, 'Invalid provider kind')
      const section = data.kind === 'text' ? config.text_generation : config.image_generation
      const name = path.endsWith('/save') ? data.name : data.provider_name
      if (!name?.trim()) return fail(400, 'Provider name required')
      if (path.endsWith('/save')) {
        if (!data.config || typeof data.config !== 'object') return fail(400, 'Provider config required')
        section.providers[name] = publicProvider({ ...section.providers[name], ...data.config }, section.providers[name])
        if (!section.active_provider) section.active_provider = name
      } else {
        if (!currentUser?.is_admin) return fail(403, 'Administrator required')
        if (!section.providers[name]) return fail(404, 'Provider not found')
        if (!Array.isArray(data.usernames)) return fail(400, 'Expected usernames')
        section.providers[name].allowed_users = clone(data.usernames)
      }
      return ok({ message: 'Preview provider saved' })
    }
    if (path === '/api/config/test' && method === 'POST') return ok({ message: '开发预览：模拟连接成功，未调用真实服务' })
    if (path === '/api/config/deai' && method === 'GET') return ok({ config: { deai_script: '', python_script: '' } })
    if (path === '/api/history' && method === 'POST') {
      if (!data.topic || !Array.isArray(data.outline?.pages)) return fail(400, 'Topic and outline required')
      const id = `preview-record-${++sequence}`
      const now = new Date().toISOString()
      records.set(id, { id, title: data.topic, outline: clone(data.outline), images: { task_id: data.task_id || null, generated: [] }, status: 'draft', thumbnail: null, created_at: now, updated_at: now })
      recordOwners.set(id, currentUser!.id)
      return ok({ record_id: id })
    }
    if (path === '/api/history/stats' && method === 'GET') {
      const by_status: Record<string, number> = {}
      const visible = visibleRecords(url.searchParams.get('source'))
      visible.forEach(record => { by_status[record.status] = (by_status[record.status] || 0) + 1 })
      return ok({ total: visible.length, by_status })
    }
    if ((path === '/api/history' || path === '/api/history/search') && method === 'GET') {
      let items = visibleRecords(url.searchParams.get('source')).sort((a, b) => b.created_at.localeCompare(a.created_at))
      const keyword = url.searchParams.get('keyword')?.trim().toLowerCase()
      if (keyword) items = items.filter(item => `${item.title} ${item.outline.raw} ${item.content?.copywriting || ''}`.toLowerCase().includes(keyword))
      const status = url.searchParams.get('status')
      if (status && status !== 'all') items = items.filter(item => item.status === status)
      if (path.endsWith('/search')) {
        if (!keyword) return fail(400, 'Keyword required')
        return ok({ records: items.map(listItem) })
      }
      const page = Math.max(1, Math.trunc(Number(url.searchParams.get('page'))) || 1)
      const size = Math.max(1, Math.min(100, Math.trunc(Number(url.searchParams.get('page_size'))) || 20))
      return ok({ records: items.slice((page - 1) * size, page * size).map(listItem), total: items.length, page, page_size: size, total_pages: Math.ceil(items.length / size) })
    }
    const syncTask = (taskId: string) => {
      const images = tasks.get(taskId)
      if (!images) return false
      records.forEach(record => {
        if (record.images.task_id !== taskId) return
        record.images.generated = [...images]
        record.status = images.length >= record.outline.pages.length ? 'completed' : images.length ? 'partial' : 'draft'
        record.thumbnail = images.length ? previewPhotos[Number(images[0]!.split('.')[0]) % previewPhotos.length]! : null
        record.updated_at = new Date().toISOString()
      })
      return true
    }
    if (path === '/api/history/scan-all' && method === 'POST') {
      const writableTasks = [...tasks.keys()].filter(id => {
        const related = [...records.values()].filter(record => record.images.task_id === id)
        return related.length > 0 && related.every(canEditRecord)
      })
      writableTasks.forEach(id => syncTask(id))
      return ok({ total_tasks: writableTasks.length, synced: writableTasks.length, failed: 0, orphan_tasks: [] })
    }
    const scan = path.match(/^\/api\/history\/scan\/([^/]+)$/)
    if (scan && method === 'POST') {
      const record = [...records.values()].find(item => item.images.task_id === scan[1])
      if (!record || !canEditRecord(record)) return fail(403, '共享作品仅可查看')
      return syncTask(scan[1]!) ? ok({ images: tasks.get(scan[1]!) }) : fail(404, 'Task not found')
    }
    const sharing = path.match(/^\/api\/history\/([^/]+)\/sharing$/)
    if (sharing) {
      const record = records.get(sharing[1]!)
      if (!record) return fail(404, '作品不存在')
      if (!canShareRecord(record)) return fail(403, '只能配置管理员自己的作品')
      if (method === 'PUT') {
        if (!Array.isArray(data.user_ids) || data.user_ids.some((id: unknown) => typeof id !== 'string' || !users.has(id) || id === currentUser!.id)) {
          return fail(400, '用户列表无效')
        }
        grants.set(record.id, new Set(data.user_ids.filter((id: string) => id !== currentUser!.id)))
      } else if (method !== 'GET') return fail(405, 'Method not supported')
      return ok({ user_ids: [...(grants.get(record.id) || [])] })
    }
    const history = path.match(/^\/api\/history\/([^/]+)(\/exists)?$/)
    if (history) {
      const id = history[1]!
      const record = records.get(id)
      if (history[2] && method === 'GET') return { status: 200, data: { exists: Boolean(record && canReadRecord(record)) } }
      if (!record) return fail(404, 'History record not found')
      if (!canReadRecord(record)) return fail(403, '作品不可访问或共享已取消')
      if (!history[2]) {
        if (method === 'GET') {
          if (options.revokeAfterMs && !ownRecord(record) && revokeAt === null) revokeAt = Date.now() + options.revokeAfterMs
          return ok({ record: { ...record, ...capabilities(record) } })
        }
        if (!canEditRecord(record)) return fail(403, '共享作品仅可查看')
        if (method === 'DELETE') {
          records.delete(id)
          processing.delete(id)
          jobs.forEach((job, key) => { if (job.recordId === id) jobs.delete(key) })
          if (record.images.task_id) tasks.delete(record.images.task_id)
          return ok()
        }
        if (method === 'PUT') {
          for (const key of ['title', 'outline', 'images', 'status', 'thumbnail', 'content', 'image_style'] as const) {
            if (data[key] != null) Object.assign(record, { [key]: clone(data[key]) })
          }
          record.updated_at = new Date().toISOString()
          return ok()
        }
      }
    }
    return fail(404, `Unimplemented preview request: ${method} ${path}`)
  }

  const adapter: AxiosAdapter = async config => {
    const url = new URL(config.url || '', 'http://preview.local')
    Object.entries(config.params || {}).forEach(([key, value]) => {
      if (value != null) url.searchParams.set(key, String(value))
    })
    const data = config.data instanceof FormData ? Object.fromEntries(config.data.entries())
      : typeof config.data === 'string' ? JSON.parse(config.data) : config.data || {}
    let result
    try { result = await request((config.method || 'GET').toUpperCase(), url, data, config.signal as AbortSignal) }
    catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw new CanceledError('Preview request cancelled', config)
      throw error
    }
    const response = { config, data: result.data, headers: {}, status: result.status, statusText: result.status === 200 ? 'OK' : 'Preview error' }
    if (result.status >= 400) throw new AxiosError('Preview request failed', 'ERR_BAD_REQUEST', config, undefined, response)
    return response
  }

  const fetchMock: typeof fetch = async (input, init) => {
    const req = new Request(input instanceof Request ? input : new URL(String(input), 'http://preview.local'), init)
    if (req.signal.aborted) throw abortError()
    const url = new URL(req.url)
    const data = req.method === 'GET' || req.method === 'HEAD' ? {} : await req.json().catch(() => ({}))
    if (req.method !== 'POST' || !['/api/generate', '/api/retry-failed'].includes(url.pathname)) {
      const result = await request(req.method, url, data, req.signal)
      return new Response(JSON.stringify(result.data), { status: result.status, headers: { 'Content-Type': 'application/json' } })
    }
    const pages: Page[] = data.pages
    if (!currentUser || referencedRecords(data).some(record => !canEditRecord(record))) {
      return new Response(JSON.stringify(fail(403, '共享作品仅可查看').data), { status: 403, headers: { 'Content-Type': 'application/json' } })
    }
    if (!Array.isArray(pages) || !pages.length || pages.some(page => !Number.isInteger(page.index) || page.index < 0)) {
      return new Response(JSON.stringify(fail(400, 'Pages required').data), { status: 400, headers: { 'Content-Type': 'application/json' } })
    }
    const taskId = data.task_id || `preview-task-${++sequence}`
    const op = operation(req.signal)
    const retry = url.pathname === '/api/retry-failed'
    const encoder = new TextEncoder()
    let cancelled = false
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const emit = (event: string, value: object) => controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(value)}\n\n`))
        void (async () => {
          try {
            const images = [...(tasks.get(taskId) || [])]
            for (const [position, page] of pages.entries()) {
              emit('progress', { index: page.index, status: 'generating', current: position, total: pages.length })
              await wait(delay, op.controller.signal)
              const filename = `${page.index}.png`
              if (!images.includes(filename)) images.push(filename)
              tasks.set(taskId, [...images])
              publishOriginal(taskId, page.index, data.record_id)
              emit('complete', { index: page.index, status: 'done', image_url: previewPhotos[page.index % previewPhotos.length], current: position + 1, total: pages.length })
            }
            emit(retry ? 'retry_finish' : 'finish', { success: true, task_id: taskId, images, total: pages.length, completed: pages.length, failed: 0 })
            controller.close()
          } catch (error) {
            if (!cancelled) controller.error(error)
          } finally { op.cleanup() }
        })()
      },
      cancel() { cancelled = true; op.controller.abort(); op.cleanup() },
    })
    return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } })
  }
  return { adapter, fetch: fetchMock }
}
