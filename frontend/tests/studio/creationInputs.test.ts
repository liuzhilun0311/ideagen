import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../../src/stores/generator'
import { creationInputs, restoreCreationInputs } from '../../src/features/creationInputs'

beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })

it('restores work-specific parameters, models, material and image bytes', () => {
  const store = useGeneratorStore()
  store.referenceContent = 'Original source'
  store.referenceRoles = ['subject']
  store.imageResolution = '2K'
  store.imageOutputFormat = 'webp'
  store.imageModelName = 'saved-model'
  store.useCoverAsReference = true
  const snapshot = creationInputs(store)
  snapshot.reference_images = [{ name: 'ref.png', type: 'image/png', data: 'data:image/png;base64,AQID' }]
  store.imageModelName = 'other-model'
  restoreCreationInputs(store, snapshot)
  expect(store.referenceRoles).toEqual(['subject'])
  expect(store.userImages[0]?.size).toBe(3)
  expect(creationInputs(store)).toEqual(snapshot)
})

it('legacy work does not inherit another work material or output settings', () => {
  const store = useGeneratorStore()
  store.referenceContent = 'Other work'
  store.referenceRoles = ['style']
  store.imageResolution = '4K'
  store.useCoverAsReference = true
  restoreCreationInputs(store)
  expect(store.referenceContent).toBe('')
  expect(store.referenceRoles).toEqual([])
  expect(store.imageResolution).toBe('1K')
  expect(store.useCoverAsReference).toBe(false)
})
