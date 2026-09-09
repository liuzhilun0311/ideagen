import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import axios, { type AxiosResponse } from 'axios'
import '../../src/assets/css/variables.css'
import '../../src/assets/css/base.css'
import '../../src/assets/css/components.css'
import '../../src/assets/css/home.css'
import '../../src/assets/css/history.css'

if (!import.meta.env.DEV) throw new Error('Development preview only')

// This page uses ephemeral storage, never the user's persisted account or drafts.
const memory = new Map<string, string>()
const previewStorage: Storage = {
  getItem: key => memory.get(key) ?? null,
  setItem: (key, value) => { memory.set(key, value) },
  removeItem: key => { memory.delete(key) },
  clear: () => { memory.clear() },
  key: index => [...memory.keys()][index] ?? null,
  get length() { return memory.size },
}
Object.defineProperty(window, 'localStorage', { value: previewStorage, configurable: true })
memory.set('ideagen_token', 'local-preview-not-a-real-token')
memory.set('ideagen_user', JSON.stringify({ id: 'preview-user', username: '开发预览', is_admin: false }))

const pages = [
  { index: 0, type: 'cover' as const, content: '把周末，留给城市的一角\n不赶路的城市漫步\n街道、咖啡和那些不经意的美好。' },
  { index: 1, type: 'content' as const, content: '在街角喝一杯咖啡\n选一家有窗边座位的小店，留一点时间观察街上的人。' },
  { index: 2, type: 'summary' as const, content: '把一点绿色带回家\n散步的终点，是属于自己的生活节奏。' },
]
const photos = ['/assets/inspiration/city.jpg', '/assets/inspiration/coffee.jpg', '/assets/inspiration/plants.jpg']
const copy = {
  titles: ['周末不赶路，去城市里慢慢走', '一场没有目的地的城市漫步'],
  copywriting: '关掉导航，走进一条还没去过的小巷。\n\n在街角喝一杯咖啡，经过花店时停下来。原来周末的好心情，不一定需要一张远行的车票。\n\n把时间留给自己，也留给生活里那些不起眼的小事。',
  tags: ['城市漫步', '周末日常', '生活记录'],
}
let record = {
  id: 'preview-record', title: '周末城市漫步图文', created_at: '2026-09-09 10:00:00',
  updated_at: '2026-09-09 10:00:00', outline: { raw: pages.map(page => page.content).join('\n\n<page>\n\n'), pages },
  content: copy, images: { task_id: 'preview-task', generated: ['0.png', '1.png', '2.png'] },
  status: 'completed', thumbnail: photos[0],
}

axios.defaults.adapter = async config => {
  const path = (config.url || '').split('?')[0]
  const data = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
  let result: object = { success: true }
  if (path === '/api/config') {
    result = { success: true, config: {
      text_generation: { active_provider: 'preview-text', providers: { 'preview-text': { enabled: true, display_name: '演示文本模型' } } },
      image_generation: { active_provider: 'preview-image', providers: { 'preview-image': { enabled: true, display_name: '演示图片模型' } } },
    } }
  } else if (path === '/api/prompts') {
    result = { success: true, prompts: { outline: [], content: [], image: [] } }
  } else if (path === '/api/outline') {
    result = { success: true, outline: record.outline.raw, pages }
  } else if (path === '/api/content') {
    result = { success: true, ...copy }
  } else if (path === '/api/regenerate') {
    result = { success: true, index: data.page.index, image_url: photos[data.page.index % photos.length] }
  } else if (path === '/api/history' && config.method === 'post') {
    record = { ...record, title: data.topic, outline: data.outline }
    result = { success: true, record_id: record.id }
  } else if (path === '/api/history/preview-record' && config.method === 'put') {
    record = { ...record, ...data }
  } else if (path === '/api/history/preview-record') {
    result = { success: true, record }
  } else if (path === '/api/history/stats') {
    result = { success: true, total: 1, by_status: { completed: 1 } }
  } else if (path === '/api/history' || path === '/api/history/search') {
    result = { success: true, records: [{ ...record, page_count: 3 }], total: 1, page: 1, page_size: 20, total_pages: 1 }
  }
  await new Promise(resolve => setTimeout(resolve, 90))
  return { config, data: result, headers: {}, status: 200, statusText: 'OK' } as AxiosResponse
}

const nativeFetch = window.fetch.bind(window)
window.fetch = async (input, init) => {
  const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.origin)
  if (!url.pathname.startsWith('/api/')) return nativeFetch(input, init)
  if (url.pathname === '/api/generate') {
    const events = pages.map(page => `event: complete\ndata: ${JSON.stringify({
      index: page.index, status: 'done', image_url: photos[page.index],
    })}\n\n`).join('')
    return new Response(events + `event: finish\ndata: ${JSON.stringify({
      success: true, task_id: 'preview-task', images: ['0.png', '1.png', '2.png'],
    })}\n\n`, { headers: { 'Content-Type': 'text/event-stream' } })
  }
  return new Response(JSON.stringify({ success: true }), { headers: { 'Content-Type': 'application/json' } })
}

async function mount() {
  const [{ default: App }, { default: liveRouter }, { useGeneratorStore }] = await Promise.all([
    import('../../src/App.vue'), import('../../src/router'), import('../../src/stores/generator'),
  ])
  const pinia = createPinia()
  const store = useGeneratorStore(pinia)
  const screen = new URLSearchParams(location.search).get('screen') || 'home'
  if (screen !== 'home' && screen !== 'login') {
    store.topic = record.title
    store.setOutline(record.outline.raw, pages.map(page => ({ ...page })))
    store.setRecordId(record.id)
    store.setEntrySource('history')
    if (screen === 'result' || screen === 'workspace-images') {
      store.startGeneration()
      photos.forEach((url, index) => store.updateProgress(index, 'done', url))
      store.finishGeneration('preview-task')
      store.setContent([...copy.titles], copy.copywriting, [...copy.tags])
    }
  }
  const router = createRouter({ history: createMemoryHistory(), routes: liveRouter.options.routes })
  const path = screen === 'home' ? '/' : screen === 'login' ? '/login' : screen === 'result' ? '/result' : '/workspace'
  await router.push(path)
  const app = createApp(App)
  app.use(pinia)
  app.use(router)
  app.mount('#app')
}
void mount()
