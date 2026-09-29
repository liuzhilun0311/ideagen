import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../../src/stores/generator'
import { useReferenceDraftPersistence } from '../../src/composables/useReferenceDraftPersistence'
import { referenceDraftStorage } from '../../src/features/referenceDraftStorage'

if (!import.meta.env.DEV) throw new Error('Development check only')
// Only synthetic data: never read or change the real local draft or account.
const memory = new Map<string, string>([
  ['ideagen_user', JSON.stringify({ id: '__reference-storage-check__', username: 'Synthetic', is_admin: false })],
])
Object.defineProperty(window, 'localStorage', { configurable: true, value: {
  getItem: (key: string) => memory.get(key) ?? null,
  setItem: (key: string, value: string) => memory.set(key, value),
  removeItem: (key: string) => memory.delete(key),
} })

async function run() {
  let stop: (() => void) | undefined
  try {
    setActivePinia(createPinia())
    const first = useGeneratorStore()
    first.topic = 'Synthetic reference recovery'
    first.referenceContent = 'Synthetic text'
    const persistence = useReferenceDraftPersistence()
    stop = persistence.stop
    await persistence.ready
    first.userImages = [new File(['synthetic-bytes'], 'fixture.png', { type: 'image/png', lastModified: 123 })]
    await persistence.retry()
    const key = first.referenceImageKey
    const saved = await referenceDraftStorage.read('__reference-storage-check__')
    if (saved?.key !== key || await saved.files[0]?.blob.text() !== 'synthetic-bytes') throw new Error('Native write/read mismatch')
    stop()
    setActivePinia(createPinia())
    const restored = useGeneratorStore()
    const next = useReferenceDraftPersistence()
    stop = next.stop
    await next.ready
    if (restored.referenceContent !== 'Synthetic text' || restored.topic !== 'Synthetic reference recovery'
      || restored.userImages[0]?.name !== 'fixture.png'
      || restored.userImages[0]?.lastModified !== 123
      || await restored.userImages[0]?.text() !== 'synthetic-bytes') throw new Error('Draft rehydration mismatch')
    restored.userImages = []
    await next.retry()
    if ((await referenceDraftStorage.read('__reference-storage-check__'))?.files.length) throw new Error('Removal not persisted')
    document.querySelector('#result')!.textContent = 'PASS: native IndexedDB write/read\nPASS: fresh store restores image bytes, filename, timestamp and text\nPASS: removal persists\nNo real account or draft was accessed.'
  } catch (error) {
    document.querySelector('#result')!.textContent = `FAIL: ${String(error)}`
  } finally { stop?.() }
}
void run()
