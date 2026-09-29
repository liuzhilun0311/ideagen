import { afterEach, beforeEach, expect, it } from 'vitest'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import { renderer, root, text, nodes } from '../history/renderer'
import Summary from '../../src/components/workspace/OutlineParameterSummary.vue'
import { useGeneratorStore } from '../../src/stores/generator'
import { outlinePreferences } from '../../src/features/generationOptions'

let unmount: (() => void) | undefined
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => unmount?.())
function mount() {
  const app = renderer.createApp(Summary)
  app.use(getActivePinia()!)
  app.mount(root)
  unmount = () => app.unmount()
}
it('aligns four columns with separate parameter names and keeps manual reasons out of the table', () => {
  const store = useGeneratorStore()
  store.outline.requested_preferences = { ...outlinePreferences(store), audience: '专业读者' }
  store.outline.generation_preferences = {
    ...store.outline.requested_preferences, platform: 'douyin', goal: 'share', organization: '清单合集',
  }
  store.outline.growth_recommendation = {
    platform: 'douyin', goal: 'share', layout: '清单', image_style: 'collage',
    aspect_ratio: '9:16', content_structure: '引入、总结', reason: '',
    outline_explanation: { platform: '适合短图文', audience: '不应显示的理由' },
  }
  mount()
  expect(nodes().filter(node => node.tag === 'th' && node.props.scope === 'col').map(text))
    .toEqual(['参数', '参数设置', '实际采用', '理由'])
  const rowHeaders = nodes().filter(node => node.tag === 'th' && node.props.scope === 'row')
  expect(rowHeaders.map(text)).toEqual(['发布平台', '创作目标', '目标读者', '内容结构', '表达语气', '内容形态', '信息密度'])
  expect(rowHeaders[0]!.parent!.children.filter(node => node.tag === 'td').map(text))
    .toEqual(['自动推荐', '抖音', '适合短图文'])
  expect(text()).toContain('适合短图文')
  expect(text()).toContain('用户指定')
  expect(text()).not.toContain('不应显示的理由')
  expect(nodes().some(node => node.tag === 'td' && node.props.colspan === '4')).toBe(true)
})
it('does not invent reasons for historical records', () => {
  mount()
  expect(text()).toContain('本次未记录采用理由')
})
it('shows a concrete automatic tone and reason, but not an unresolved tone as adopted', () => {
  const store = useGeneratorStore()
  store.outline.requested_preferences = outlinePreferences(store)
  store.outline.generation_preferences = { ...outlinePreferences(store), tone: '亲切易懂' }
  store.outline.growth_recommendation = {
    platform: 'douyin', goal: 'share', layout: '清单', image_style: 'collage',
    aspect_ratio: '9:16', content_structure: '', reason: '',
    outline_explanation: { tone: '生活主题适合自然表达' },
  }
  mount()
  const row = nodes().find(node => node.tag === 'th' && text(node) === '表达语气')!.parent!
  expect(row.children.filter(node => node.tag === 'td').map(text))
    .toEqual(['自动匹配', '亲切易懂', '生活主题适合自然表达'])
})
it('keeps unresolved historical automatic tone unrecorded', () => {
  const store = useGeneratorStore()
  store.outline.requested_preferences = outlinePreferences(store)
  store.outline.generation_preferences = outlinePreferences(store)
  mount()
  const row = nodes().find(node => node.tag === 'th' && text(node) === '表达语气')!.parent!
  expect(row.children.filter(node => node.tag === 'td').map(text))
    .toEqual(['自动匹配', '未记录', '本次未记录采用理由'])
})
