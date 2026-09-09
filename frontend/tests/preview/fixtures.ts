import { AxiosError, CanceledError, type AxiosAdapter } from 'axios'
import type { AuthUser } from '../../src/api/auth'
import type { PromptItem, PromptKind } from '../../src/api/prompts'
import type { Config, HistoryDetail, Page } from '../../src/api/types'

export const previewUser: AuthUser = {
  id: 'preview-user', username: '开发预览', is_admin: true, created_at: '2026-09-09T10:00:00',
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
  outline: { raw: previewPages.map(page => page.content).join('\n\n<page>\n\n'), pages: previewPages },
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
    ? url.pathname.match(/^\/api\/images\/[^/]+\/(\d+)\.png$/) : null
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
export function createPreviewFixtures(delay = 1200) {
  delay = previewDelay(`delay=${delay}`)
  let sequence = 0
  let currentUser: AuthUser | null = clone(previewUser)
  const users = new Map<string, AuthUser>([
    [previewUser.id, clone(previewUser)],
    ['preview-reader', { id: 'preview-reader', username: '演示成员', is_admin: false, created_at: previewUser.created_at }],
  ])
  const passwords = new Map<string, string>()
  const records = new Map<string, HistoryDetail>([[previewRecord.id, clone(previewRecord)]])
  const tasks = new Map<string, string[]>([['preview-task', ['0.png', '1.png', '2.png']]])
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
    return { id, title, created_at, updated_at, status, thumbnail, page_count: record.outline.pages.length, task_id: record.images.task_id }
  }
  const publicProvider = (value: Record<string, unknown>, previous: Record<string, unknown> = {}) => {
    const result = { ...clone(value) }
    result.api_key_masked = value.api_key ? 'preview-****' : previous.api_key_masked || value.api_key_masked || ''
    delete result.api_key
    return result
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
    if (method === 'POST' && path === '/api/generate/cancel') {
      running.forEach(controller => controller.abort())
      return ok()
    }
    if (method === 'POST' && ['/api/outline', '/api/content', '/api/regenerate'].includes(path)) {
      const op = operation(signal)
      try {
        await wait(delay, op.controller.signal)
        if (path === '/api/outline') return ok({ outline: previewRecord.outline.raw, pages: previewPages, has_images: Boolean(data.images) })
        if (path === '/api/content') return ok(previewCopy)
        if (!Number.isInteger(data.page?.index)) return fail(400, 'Missing page index')
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
    if (path === '/api/prompts' && method === 'GET') return ok({ prompts })
    if (method === 'POST' && ['/api/prompts/save', '/api/prompts/delete', '/api/prompts/base/save', '/api/prompts/admin/users', '/api/prompts/admin/delete'].includes(path)) {
      const kind = data.kind as PromptKind
      if (!Object.prototype.hasOwnProperty.call(prompts, kind)) return fail(400, 'Invalid prompt kind')
      const items = prompts[kind]
      if (path === '/api/prompts/base/save') {
        if (!currentUser?.is_admin) return fail(403, 'Administrator required')
        if (!data.content?.trim()) return fail(400, 'Content required')
        items[0]!.content = data.content
        return ok()
      }
      if (!data.name?.trim() || data.name === '默认提示词') return fail(400, 'Invalid prompt name')
      const ownerId = path.includes('/admin/') ? data.owner_id : currentUser?.id
      const index = items.findIndex(item => item.name === data.name && item.owner_id === ownerId)
      if (path === '/api/prompts/save') {
        if (!data.content?.trim()) return fail(400, 'Content required')
        if (index >= 0) items[index]!.content = data.content
        else items.push({ name: data.name, content: data.content, type: kind, is_base: false, can_edit: true, owner: currentUser?.username, owner_id: currentUser?.id, is_shared: false, allowed_users: [] })
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
    if (path === '/api/config' && method === 'GET') return ok({ config })
    if (path === '/api/config' && method === 'POST') {
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
      return ok({ record_id: id })
    }
    if (path === '/api/history/stats' && method === 'GET') {
      const by_status: Record<string, number> = {}
      records.forEach(record => { by_status[record.status] = (by_status[record.status] || 0) + 1 })
      return ok({ total: records.size, by_status })
    }
    if ((path === '/api/history' || path === '/api/history/search') && method === 'GET') {
      let items = [...records.values()].sort((a, b) => b.created_at.localeCompare(a.created_at))
      if (path.endsWith('/search')) {
        const keyword = url.searchParams.get('keyword')?.trim().toLowerCase()
        if (!keyword) return fail(400, 'Keyword required')
        items = items.filter(item => `${item.title} ${item.outline.raw} ${item.content?.copywriting || ''}`.toLowerCase().includes(keyword))
        return ok({ records: items.map(listItem) })
      }
      const status = url.searchParams.get('status')
      if (status && status !== 'all') items = items.filter(item => item.status === status)
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
      tasks.forEach((_, id) => syncTask(id))
      return ok({ total_tasks: tasks.size, synced: tasks.size, failed: 0, orphan_tasks: [] })
    }
    const scan = path.match(/^\/api\/history\/scan\/([^/]+)$/)
    if (scan && method === 'POST') return syncTask(scan[1]!) ? ok({ images: tasks.get(scan[1]!) }) : fail(404, 'Task not found')
    const history = path.match(/^\/api\/history\/([^/]+)(\/exists)?$/)
    if (history) {
      const id = history[1]!
      const record = records.get(id)
      if (history[2] && method === 'GET') return { status: 200, data: { exists: Boolean(record) } }
      if (!record) return fail(404, 'History record not found')
      if (!history[2]) {
        if (method === 'GET') return ok({ record })
        if (method === 'DELETE') {
          records.delete(id)
          if (record.images.task_id) tasks.delete(record.images.task_id)
          return ok()
        }
        if (method === 'PUT') {
          for (const key of ['title', 'outline', 'images', 'status', 'thumbnail', 'content'] as const) {
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
