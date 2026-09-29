import type { GeneratorState } from '../stores/generator'
import { readFileAsDataUrl } from '../api/image'
import { imageParameters, type OutlinePreferences } from './generationOptions'
import { validateReferenceImages } from './referenceImages'

export interface CreationInputs {
  version: 1
  reference_content: string
  reference_roles: string[]
  reference_images: { name: string; type: string; data: string }[]
  image_parameters: Record<string, string>
  use_cover_reference: boolean
  models: { outline: string; content: string; image: string }
  requested_preferences?: OutlinePreferences
}
const encoded = new WeakMap<File, string>()
const identities = new WeakMap<File, number>()
let sequence = 0

export function creationInputs(store: GeneratorState): CreationInputs {
  return {
    version: 1, reference_content: store.referenceContent, reference_roles: [...store.referenceRoles],
    reference_images: store.userImages.map(file => {
      if (!identities.has(file)) identities.set(file, ++sequence)
      return { name: file.name, type: file.type, data: encoded.get(file) || `pending:${identities.get(file)}` }
    }),
    image_parameters: imageParameters(store), use_cover_reference: store.useCoverAsReference,
    models: { outline: store.outlineModelName, content: store.contentModelName, image: store.imageModelName },
    requested_preferences: store.outline.requested_preferences,
  }
}

export async function encodeReferences(files: File[]) {
  validateReferenceImages(files)
  return Promise.all(files.map(async file => {
    const data = encoded.get(file) || await readFileAsDataUrl(file)
    encoded.set(file, data)
    return { name: file.name, type: file.type, data }
  }))
}

export function restoreCreationInputs(store: GeneratorState, inputs?: CreationInputs) {
  store.referenceContent = inputs?.reference_content || ''
  store.referenceRoles = [...(inputs?.reference_roles || [])]
  store.userImages = (inputs?.reference_images || []).map(reference => {
    const bytes = Uint8Array.from(atob(reference.data.split(',')[1] || ''), char => char.charCodeAt(0))
    const file = new File([bytes], reference.name, { type: reference.type })
    encoded.set(file, reference.data)
    return file
  })
  store.useCoverAsReference = inputs?.use_cover_reference ?? false
  store.imageResolution = (inputs?.image_parameters.resolution || '1K') as GeneratorState['imageResolution']
  store.imageAspectRatio = inputs?.image_parameters.aspect_ratio || '3:4'
  store.imageQuality = (inputs?.image_parameters.quality || 'auto') as GeneratorState['imageQuality']
  store.imageOutputFormat = (inputs?.image_parameters.output_format || 'png') as GeneratorState['imageOutputFormat']
  if (inputs?.models) {
    store.outlineModelName = inputs.models.outline
    store.contentModelName = inputs.models.content
    store.imageModelName = inputs.models.image
  }
}
