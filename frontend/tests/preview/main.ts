import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import axios from 'axios'
import {
  createPreviewFixtures, previewCopy as copy, previewDelay, previewImageUrl,
  previewPages as pages, previewPhotos as photos, previewRecord as record, previewUser, previewReader,
} from './fixtures'
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
const previewParameters = new URLSearchParams(location.search)
memory.set('ideagen_user', JSON.stringify(previewParameters.get('reader') === '1' ? previewReader : previewUser))
// Keep reference-image persistence isolated from real browser drafts as well.
const { referenceDraftStorage } = await import('../../src/features/referenceDraftStorage')
const referenceMemory = new Map<string, import('../../src/features/referenceDraftStorage').ReferenceDraft>()
referenceDraftStorage.read = async owner => referenceMemory.get(owner)
referenceDraftStorage.write = async (owner, value) => { referenceMemory.set(owner, value) }

const fixtures = createPreviewFixtures(previewDelay(location.search), {
  candidateDelay: previewParameters.has('candidate-delay')
    ? previewDelay(`delay=${previewParameters.get('candidate-delay')}`) : 0,
  processingDelay: 1800,
  failIndices: previewParameters.get('processing') === 'partial-failure' ? [1] : [],
  reader: previewParameters.get('reader') === '1',
  shared: previewParameters.get('shared') === '1',
  revokeAfterMs: previewParameters.get('revoke') === '1' ? 5000 : undefined,
  missingWork: previewParameters.get('missing') === '1',
})
axios.defaults.adapter = fixtures.adapter

// Intercept before assigning a URL so <img> never requests the real image API.
// This shim exists only in the dev-preview document, not production URL helpers.
for (const [prototype, property] of [
  [HTMLImageElement.prototype, 'src'], [HTMLAnchorElement.prototype, 'href'],
] as const) {
  const descriptor = Object.getOwnPropertyDescriptor(prototype, property)!
  Object.defineProperty(prototype, property, {
    ...descriptor,
    set(value: string) { descriptor.set!.call(this, previewImageUrl(value, location.origin)) },
  })
}
const setAttribute = Element.prototype.setAttribute
Element.prototype.setAttribute = function (name, value) {
  const attribute = name.toLowerCase()
  if ((this instanceof HTMLImageElement && attribute === 'src') ||
      (this instanceof HTMLAnchorElement && attribute === 'href')) {
    value = previewImageUrl(value, location.origin)
  }
  setAttribute.call(this, name, value)
}

const nativeFetch = window.fetch.bind(window)
window.fetch = async (input, init) => {
  const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.origin)
  const image = previewImageUrl(url.href, location.origin)
  if (image !== url.href) return nativeFetch(image, { signal: init?.signal ?? (input instanceof Request ? input.signal : undefined) })
  if (url.pathname.startsWith('/api/')) return fixtures.fetch(input, init)
  return nativeFetch(input, init)
}

async function mount() {
  const [{ default: App }, { default: liveRouter }, { useGeneratorStore }] = await Promise.all([
    import('../../src/App.vue'), import('../../src/router'), import('../../src/stores/generator'),
  ])
  const pinia = createPinia()
  const store = useGeneratorStore(pinia)
  const screen = new URLSearchParams(location.search).get('screen') || 'home'
  if (['workspace', 'workspace-images', 'workspace-copy', 'result'].includes(screen)) {
    store.topic = record.title
    store.setOutline(record.outline.raw, pages.map(page => ({ ...page })))
    store.outline.growth_recommendation = record.outline.growth_recommendation
    store.setRecordId(record.id)
    store.setEntrySource('history')
    if (screen === 'workspace-copy') store.setContent([...copy.titles], copy.copywriting, [...copy.tags])
    if (screen === 'result' || screen === 'workspace-images') {
      store.startGeneration()
      photos.forEach((url, index) => store.updateProgress(index, 'done', url))
      store.finishGeneration('preview-task')
      store.setContent([...copy.titles], copy.copywriting, [...copy.tags])
    }
  }
  const router = createRouter({ history: createMemoryHistory(), routes: liveRouter.options.routes })
  const paths: Record<string, string> = {
    home: '/', login: '/login', result: '/result', workspace: '/workspace',
    'workspace-images': '/workspace', 'workspace-copy': '/workspace/copy', history: '/history', works: '/history',
    prompts: '/prompts', settings: '/settings', models: '/settings', users: '/users',
  }
  const path = paths[screen] || '/'
  await router.push(path)
  const app = createApp(App)
  app.use(pinia)
  app.use(router)
  app.mount('#app')
}
void mount()
