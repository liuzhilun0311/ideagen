export const copyStyles = ['自动', '自然分享', '简洁干货', '专业科普', '温柔鼓励', '轻松幽默'] as const
export const copyStructures = ['自动', '要点清单', '步骤说明', '问题解答', '对比分析', '故事串联'] as const
export const copyLengths = ['简短', '适中', '详细'] as const
export const emojiLevels = ['无', '克制', '丰富'] as const
export type CopyField = 'style' | 'structure' | 'length' | 'emoji_level'
export interface CopyPreferences {
  style: string
  structure: string
  length: string
  emoji_level: string
  modes?: Partial<Record<CopyField, 'auto' | 'manual'>>
  recommendations?: Partial<Record<CopyField, string>>
}
export function copyPreferences(value?: Partial<CopyPreferences> | null): CopyPreferences {
  return {
    style: defaultCopyValue('style', value?.style, '自动'),
    structure: defaultCopyValue('structure', value?.structure, '自动'),
    length: defaultCopyValue('length', value?.length, '适中'),
    emoji_level: emojiLevels.includes(value?.emoji_level as any) ? value!.emoji_level! : '克制',
    ...(value?.modes ? { modes: { ...value.modes } } : {}),
    ...(value?.recommendations ? { recommendations: { ...value.recommendations } } : {}),
  }
}
export function isAutomaticCopy(value: Partial<CopyPreferences> | undefined, key: CopyField): boolean {
  if (value?.modes?.[key]) return value.modes[key] === 'auto'
  if (!value?.[key]) return true
  return key !== 'emoji_level' && (value[key] === '自动'
    || findItem(promptItems('content', key), value[key])?.legacyValue === '自动')
}
export function recommendCopyPreferences(previous: CopyPreferences | undefined, recommendation: Record<string, unknown>): CopyPreferences {
  const next = copyPreferences(previous)
  next.modes = {}
  next.recommendations = {}
  const fields: CopyField[] = ['style', 'structure', 'length', 'emoji_level']
  const defaults = copyPreferences()
  for (const key of fields) {
    const automatic = isAutomaticCopy(previous, key)
    next.modes[key] = automatic ? 'auto' : 'manual'
    const candidate = recommendation[key === 'emoji_level' ? key : `copy_${key}`]
    const valid = typeof candidate === 'string' && (key === 'emoji_level'
      ? emojiLevels.includes(candidate as any) : !!findItem(promptItems('content', key), candidate))
    // Body organization follows the outline instead of a second, competing recommendation.
    const recommended = key === 'structure' ? defaults.structure : valid ? candidate as string : defaults[key]
    next.recommendations[key] = recommended
    if (automatic) next[key] = recommended
  }
  return next
}
export function selectCopyPreference(value: CopyPreferences | undefined, key: CopyField, selected: string): CopyPreferences {
  const next = copyPreferences(value)
  for (const field of ['style', 'structure', 'length', 'emoji_level'] as CopyField[]) {
    next.modes = { ...next.modes, [field]: isAutomaticCopy(value, field) ? 'auto' : 'manual' }
  }
  const automatic = selected === '__auto__' || (key === 'structure'
    && (selected === '自动' || findItem(promptItems('content', key), selected)?.legacyValue === '自动'))
  next.modes = { ...next.modes, [key]: automatic ? 'auto' : 'manual' }
  next[key] = automatic ? next.recommendations?.[key] || copyPreferences()[key] : selected
  return next
}
function defaultCopyValue(category: CopyField, value: string | undefined, preferred: string) {
  if (typeof value === 'string' && value) return value
  if (category === 'emoji_level') return preferred
  const items = promptItems('content', category)
  const item = findItem(items, preferred) || items[0]
  return item ? itemValue(item) : ''
}
export function resolveCopyPreferences(value?: Partial<CopyPreferences> | null): CopyPreferences {
  const selected = copyPreferences(value)
  return {
    style: resolvePromptValue('content', 'style', selected.style),
    structure: resolvePromptValue('content', 'structure', selected.structure),
    length: resolvePromptValue('content', 'length', selected.length),
    emoji_level: selected.emoji_level,
  }
}
import { promptItems, findItem, itemValue, resolvePromptValue } from './promptCatalog'
