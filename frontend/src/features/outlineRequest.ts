import type { GeneratorState } from '../stores/generator'
import { outlinePreferences } from './generationOptions'
import { validateReferenceImages } from './referenceImages'

export function outlineRequest(state: GeneratorState, home = false) {
  const preferences = outlinePreferences(home
    ? { ...state, outlineTone: '自动匹配' }
    : state)
  preferences.audience_detail = preferences.audience === '自定义' ? preferences.audience_detail.trim() : ''
  if (preferences.audience === '自定义' && !preferences.audience_detail) {
    throw new Error('请填写具体目标读者。')
  }
  if (preferences.audience_detail.length > 120) throw new Error('具体目标读者不能超过 120 字符。')
  const images = [...state.userImages]
  if (state.referenceImageKey && !images.length) throw new Error('参考图片尚未恢复，请先重试恢复或重新添加图片。')
  validateReferenceImages(images)
  return {
    topic: state.topic.trim(),
    reference_content: state.referenceContent.trim(),
    image_count: images.length,
    reference_roles: [...state.referenceRoles],
    images,
    provider: state.outlineModelName,
    preferences,
  }
}
