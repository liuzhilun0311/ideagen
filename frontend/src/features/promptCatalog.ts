import { computed, getCurrentInstance, onActivated, onMounted, ref } from 'vue'
import { defineStore, getActivePinia } from 'pinia'
import { getPromptCatalog, type PromptEntry, type PromptModule, type PromptCategory, type PromptOrder } from '../api/promptCenter'
import { getToken } from '../api/token'
import styleBootstrap from '../../../backend/generation/style_catalog.json'

export type CatalogKey = `${PromptModule}.${PromptCategory}`
export const catalogKey = (module: PromptModule, category: PromptCategory): CatalogKey => `${module}.${category}`

export interface CatalogItem {
  content?: string
  id: string
  name: string
  description: string
  legacyValue?: string
  builtin: boolean
  metadata: Record<string, unknown>
}

const legacyLayoutMetadata: Record<string, Record<string, unknown>> = {
  '自动': { preview: 'summary', preview_alt: '根据内容自动选择页面排版结构，示例展示标题、正文和视觉主体的清晰分区。', summary: '根据本页信息关系自动选择清晰、适合阅读的页面结构。' },
  '封面': { preview: 'cover', preview_alt: '主标题与视觉主体集中在页面中央，副标题次级呈现并保留安全边距。', summary: '突出主标题与一个视觉主体，适合内容开场和主题建立。' },
  '清单': { preview: 'list', preview_alt: '多个编号条目纵向排列，短标签和说明形成清晰的层级关系。', summary: '以等距排列的条目组织信息，适合要点、资源和检查项。' },
  '步骤': { preview: 'steps', preview_alt: '步骤节点沿明确阅读路径排列，并用方向关系表达先后顺序。', summary: '沿清晰的阅读路径展示顺序，适合教程和流程说明。' },
  '对比': { preview: 'compare', preview_alt: '两个或多个对象分栏并列，比较维度横向对齐且视觉权重相当。', summary: '将比较对象并列，适合差异、选择和方案分析。' },
  '分类': { preview: 'category', preview_alt: '内容按多个同级类别分区呈现，组间分隔清楚且组内层级一致。', summary: '按同级类别分组，适合整理主题、类型和场景。' },
  '关系': { preview: 'relation', preview_alt: '中心主体与周边关联元素通过连线和标签建立关系，避免无依据的因果表达。', summary: '以主体、连线和标签表达信息关系，适合结构和关联说明。' },
  '例子': { preview: 'example', preview_alt: '示例主体与对应解释文本成组排列，突出具体应用场景和理解入口。', summary: '让示例主体与对应解释明确关联，适合概念到应用。' },
  '总结': { preview: 'summary', preview_alt: '核心结论置于视觉中心，下方保留关键提醒或下一步行动区域。', summary: '收束核心结论，适合总结、复盘和行动提醒。' },
}

const layoutFallbackMetadata: Record<string, Record<string, unknown>> = {
  '强钩子封面': { platforms: ['xiaohongshu', 'douyin', 'multi'], goals: ['follow', 'product', 'inquiry'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'high', summary: '适合首屏吸引停留，突出问题、结果或反常识观点。', preview: 'hook-cover', preview_alt: '大标题占据首屏主要区域，痛点或结果形成视觉焦点，下方保留主体和安全边距。' },
  '痛点—方案': { platforms: ['xiaohongshu', 'douyin', 'wechat', 'multi'], goals: ['product', 'inquiry', 'conversion'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'medium', summary: '适合把用户问题自然连接到方法、产品或服务。', preview: 'pain-solution', preview_alt: '页面分成痛点区和方案区，两个信息块沿明确阅读路径前后衔接。' },
  '误区—真相': { platforms: ['xiaohongshu', 'douyin', 'wechat', 'multi'], goals: ['follow', 'brand', 'engagement'], aspect_ratios: ['3:4', '9:16'], text_density: 'medium', summary: '适合知识澄清、反常识内容和评论讨论。', preview: 'myth-fact', preview_alt: '误区与真相采用对照分区，标签和结论形成清楚的视觉反差。' },
  '前后对比': { platforms: ['xiaohongshu', 'douyin', 'multi'], goals: ['product', 'conversion', 'engagement'], aspect_ratios: ['3:4', '9:16'], text_density: 'medium', summary: '适合展示体验变化、方法效果或方案差异。', preview: 'before-after', preview_alt: '变化前后或两种状态左右并列，比较维度保持对齐。' },
  '案例拆解': { platforms: ['xiaohongshu', 'douyin', 'wechat', 'multi'], goals: ['inquiry', 'conversion', 'brand'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'high', summary: '适合建立专业信任，推动用户进一步咨询。', preview: 'case-study', preview_alt: '案例背景、问题、做法和结果按阶段分区，形成从事实到结论的阅读路径。' },
  '产品卖点': { platforms: ['xiaohongshu', 'douyin', 'multi'], goals: ['product', 'conversion'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'medium', summary: '适合把产品特点翻译成用户能理解的实际收益。', preview: 'product-benefits', preview_alt: '产品主体位于视觉中心，周围围绕用户收益和使用场景组织信息。' },
  '用户评价/证据': { platforms: ['xiaohongshu', 'douyin', 'wechat', 'multi'], goals: ['inquiry', 'conversion', 'brand'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'high', summary: '适合降低决策风险，但不能虚构用户反馈或数据。', preview: 'proof', preview_alt: '评价、数据或证据作为主体突出展示，补充说明放在周边并保留来源位置。' },
  'FAQ问答': { platforms: ['xiaohongshu', 'douyin', 'wechat', 'multi'], goals: ['follow', 'inquiry', 'engagement'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'medium', summary: '适合处理购买前、咨询前和评论区常见问题。', preview: 'faq', preview_alt: '多个问题以问答卡片或分区排列，每个问题对应一段简短直接的回答。' },
  '数据结论': { platforms: ['douyin', 'wechat', 'multi'], goals: ['brand', 'conversion', 'follow'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'high', summary: '适合用事实、趋势或关键数字支撑观点。', preview: 'data-conclusion', preview_alt: '关键数字或趋势图表位于主体区域，结论和必要说明形成上下层级。' },
  '金句观点': { platforms: ['xiaohongshu', 'douyin', 'wechat', 'multi'], goals: ['follow', 'brand', 'engagement'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'low', summary: '适合观点传播、收藏和转发。', preview: 'quote', preview_alt: '核心观点以大字号置于视觉中心，来源和补充解释作为次级信息排列。' },
  '章节分隔': { platforms: ['wechat', 'multi'], goals: ['brand', 'follow'], aspect_ratios: ['3:4', '1:1', '16:9'], text_density: 'low', summary: '适合公众号长文和系列内容分段。', preview: 'chapter-divider', preview_alt: '章节标题和简短导语集中在页面主区域，用留白提示内容转折和阅读节奏。' },
  '行动号召页': { platforms: ['xiaohongshu', 'douyin', 'wechat', 'multi'], goals: ['follow', 'inquiry', 'conversion', 'engagement'], aspect_ratios: ['3:4', '9:16', '1:1'], text_density: 'low', summary: '适合关注、收藏、评论、私信或咨询引导。', preview: 'cta', preview_alt: '核心行动指令位于视觉中心，辅助说明和行动入口集中在底部安全区域。' },
  '口播字幕页': { platforms: ['douyin', 'multi'], goals: ['follow', 'inquiry', 'conversion'], aspect_ratios: ['9:16'], text_density: 'high', summary: '适合抖音口播、知识讲解和字幕卡点。', preview: 'talking-subtitle', preview_alt: '人物或主体保留在画面一侧，分层字幕位于安全区，避免遮挡关键信息。' },
  '产品演示页': { platforms: ['douyin', 'xiaohongshu', 'multi'], goals: ['product', 'conversion', 'inquiry'], aspect_ratios: ['9:16', '3:4', '1:1'], text_density: 'high', summary: '适合展示产品怎么用、怎么选和怎么产生结果。', preview: 'product-demo', preview_alt: '产品主体、操作步骤和结果按顺序排列，形成从操作到收益的演示路径。' },
  '评论/聊天截图页': { platforms: ['xiaohongshu', 'douyin', 'multi'], goals: ['engagement', 'inquiry', 'conversion'], aspect_ratios: ['3:4', '9:16'], text_density: 'high', summary: '适合展示真实互动和问题反馈，不伪造聊天记录。', preview: 'comment-proof', preview_alt: '评论、私信或聊天内容作为主体展示，保留上下文、隐私处理和回应关系。' },
}

const fallback: Record<string, string[]> = {
  'outline.organization': ['自动', '分类递进', '步骤教程', '问题解决', '对比决策', '概念到例子', '故事时间线', '清单合集', '误区纠正', '案例拆解', '产品种草', '观点论证'],
  'outline.audience': ['自动判断', '零基础入门', '有一定基础', '专业读者', '自定义'],
  'outline.tone': ['自动匹配', '亲切易懂', '专业简洁', '轻松幽默', '温柔鼓励'],
  'image.layout': ['自动', '封面', '清单', '步骤', '对比', '分类', '关系', '例子', '总结',
    ...Object.keys(layoutFallbackMetadata)],
  'content.style': ['自动', '自然分享', '简洁干货', '专业科普', '温柔鼓励', '轻松幽默'],
  'content.structure': ['自动', '要点清单', '步骤说明', '问题解答', '对比分析', '故事串联'],
  'content.length': ['简短', '适中', '详细'],
}

export function entryItem(entry: PromptEntry): CatalogItem {
  return { id: entry.id, name: entry.name, description: entry.description || '', legacyValue: entry.legacy_value || undefined,
    builtin: entry.builtin, content: entry.content, metadata: entry.metadata || {} }
}
export function fallbackItems(key: CatalogKey): CatalogItem[] {
  if (key === 'image.style') return [
    { id: 'auto', name: '自动推荐', description: '由内容决定画风', legacyValue: 'auto', builtin: true,
      metadata: { color: '#5b6472', group: '推荐', preview: 'auto' } },
    ...styleBootstrap.map(style => ({ id: style.id, name: style.name, description: style.scenes,
      legacyValue: style.id, builtin: true, content: style.direction, metadata: { ...style } })),
  ]
  return (fallback[key] || []).map(value => ({
    id: key === 'image.layout' && layoutFallbackMetadata[value] ? `image.layout.${layoutFallbackMetadata[value].preview}` : value,
    name: value,
    description: '',
    legacyValue: value,
    builtin: true,
    metadata: key === 'image.layout'
      ? (layoutFallbackMetadata[value] || legacyLayoutMetadata[value] || {})
      : {},
  }))
}

export function layoutPreviewUrl(metadata: Record<string, unknown> = {}) {
  const preview = typeof metadata.preview === 'string' ? metadata.preview : ''
  return preview ? `/assets/layouts/${preview}.png` : ''
}

export function layoutPreviewLabel(item: { name: string; metadata?: Record<string, unknown> }) {
  return layoutPreviewUrl(item.metadata || {}) ? `${item.name}参考图` : '暂无样图'
}
export function layoutPreviewAlt(item: { name: string; metadata?: Record<string, unknown> }) {
  const alt = item.metadata && typeof item.metadata.preview_alt === 'string' ? item.metadata.preview_alt.trim() : ''
  return alt || layoutPreviewLabel(item)
}
export function makeCatalog(entries: PromptEntry[], orders: Record<string, PromptOrder> = {}): Record<string, CatalogItem[]> {
  const result: Record<string, CatalogItem[]> = {}
  for (const entry of entries) {
    if (!entry.enabled || !entry.can_use) continue
    const key = catalogKey(entry.module, entry.category)
    const group = result[key] ||= []
    group.push(entryItem(entry))
  }
  for (const [key, items] of Object.entries(result)) {
    const ids = orders[key]?.ids || []
    const rank = (id: string) => {
      const index = ids.indexOf(id)
      return index < 0 ? ids.length : index
    }
    items.sort((a, b) => rank(a.id) - rank(b.id))
  }
  return result
}
export function itemsFor(catalog: Record<string, CatalogItem[]> | null, module: PromptModule, category: PromptCategory) {
  const key = catalogKey(module, category)
  return catalog === null ? fallbackItems(key) : catalog[key] || []
}
export function findItem(items: CatalogItem[], value: string | undefined) {
  return items.find(item => item.id === value || (item.builtin && item.legacyValue === value))
}
export function findLayoutItem(items: CatalogItem[], value: string | undefined) {
  const identified = items.find(item => item.id === value)
    || items.find(item => item.builtin && item.legacyValue === value)
  if (identified) return identified
  // Outlines use display names; resolve only unique names in the authorized catalog.
  const named = items.filter(item => item.name === value)
  return named.length === 1 ? named[0] : undefined
}
export function isUnavailable(items: CatalogItem[], value: string | undefined) {
  return !!value && !findItem(items, value)
}
export function itemValue(item: CatalogItem): string {
  return item.builtin && item.legacyValue ? item.legacyValue : item.id
}

export const usePromptCatalogStore = defineStore('promptCatalog', () => {
  const catalog = ref<Record<string, CatalogItem[]> | null>(null)
  const identity = ref(getToken())
  const error = ref('')
  const loading = ref(false)
  let pending: { token: string; promise: Promise<void> } | null = null

  function refresh(): Promise<void> {
    const token = getToken()
    if (pending?.token === token) return pending.promise
    if (identity.value !== token) {
      catalog.value = null
      identity.value = token
    }
    loading.value = true
    error.value = ''
    const request = { token, promise: Promise.resolve() }
    pending = request
    request.promise = (async () => {
      try {
        const response = await getPromptCatalog(false)
        if (pending !== request || token !== getToken()) return
        catalog.value = makeCatalog(response.entries, response.orders)
      } catch (cause) {
        if (pending !== request || token !== getToken()) return
        const status = (cause as { response?: { status?: number } })?.response?.status
        // Never resurrect revoked entries after a successful catalog or an authorization failure.
        if (catalog.value !== null || status === 401 || status === 403) catalog.value = {}
        error.value = catalog.value === null
          ? '提示词目录暂不可用，当前显示离线内置选项。'
          : '无法确认提示词权限，请刷新目录后再生成。'
      } finally {
        if (pending === request) {
          loading.value = false
          pending = null
        }
      }
    })()
    return request.promise
  }
  return { catalog, identity, loading, error, refresh }
})

export function promptItems(module: PromptModule, category: PromptCategory): CatalogItem[] {
  if (!getActivePinia()) return itemsFor(null, module, category)
  const store = usePromptCatalogStore()
  return itemsFor(store.identity === getToken() ? store.catalog : null, module, category)
}

export function selectionItems(module: PromptModule, category: PromptCategory, selected?: string) {
  const available = promptItems(module, category)
  const chosen = module === 'image' && category === 'layout'
    ? findLayoutItem(available, selected) : findItem(available, selected)
  const items = available.map(item => ({
    ...item, value: selected === item.id ? item.id : itemValue(item), unavailable: false,
  }))
  if (chosen && selected) items.find(item => item.id === chosen.id)!.value = selected
  if (selected && !chosen) items.push({
    id: selected, value: selected, name: `不可用：${selected}`, description: '已停用、删除或无权使用，请重新选择。',
    builtin: false, metadata: {}, unavailable: true,
  })
  return items
}

export function resolvePromptValue(module: PromptModule, category: PromptCategory, value?: string, preferred?: string): string {
  const items = promptItems(module, category)
  if (value) {
    const layout = module === 'image' && category === 'layout'
    const item = layout ? findLayoutItem(items, value) : findItem(items, value)
    if (!item) throw new Error(`提示词选项不可用或名称不唯一（${value}），请重新选择或刷新目录。`)
    if (layout && value !== item.id && value !== item.legacyValue) return itemValue(item)
    return value
  }
  const item = findItem(items, preferred) || items[0]
  if (!item) throw new Error('此分类没有可用提示词，请检查提示词管理。')
  return itemValue(item)
}

export function usePromptCatalog() {
  if (!getActivePinia()) return {
    loading: computed(() => false),
    error: computed(() => ''),
    refresh: () => Promise.resolve(),
  }
  const store = usePromptCatalogStore()
  if (getCurrentInstance()) {
    onMounted(() => { void store.refresh() })
    onActivated(() => { void store.refresh() })
  }
  return {
    loading: computed(() => store.loading),
    error: computed(() => store.error),
    refresh: store.refresh,
  }
}
