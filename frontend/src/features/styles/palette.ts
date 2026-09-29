import catalog from '../../../../backend/generation/palette_catalog.json'

export const palettes = catalog
export interface PaletteChoice {
  mode: string
  primary?: string
  background?: string
  accent?: string
  recommendation?: string
  reason?: string
}
export function paletteColors(value?: PaletteChoice) {
  return value?.mode === 'custom' ? {
    primary: value.primary || '#194B8C', background: value.background || '#F4F8FF', accent: value.accent || '#19A7A0',
  } : palettes.find(item => item.id === (value?.mode === 'auto' ? value.recommendation : value?.mode))
}
