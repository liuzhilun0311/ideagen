export const organizations = ['自动', '分类递进', '步骤教程', '问题解决', '对比决策', '概念到例子', '故事时间线', '清单合集', '误区纠正', '案例拆解', '产品种草', '观点论证']
export const organizationDescriptions: Record<string, string> = {
  自动: '由模型综合主题、读者、页数、平台和目标推荐最合适的叙述顺序。',
  分类递进: '先建立主题范围，再按类别或层级逐步展开，适合知识整理和系统介绍。',
  步骤教程: '按照先后顺序说明怎么做，适合方法、流程、操作和执行指南。',
  问题解决: '先呈现问题和原因，再给出解决方法与行动建议，适合痛点型主题。',
  对比决策: '围绕统一维度并列比较不同选择，帮助读者理解差异并做决定。',
  概念到例子: '先解释抽象概念，再用具体例子降低理解门槛，适合科普和入门内容。',
  故事时间线: '按时间、过程或事件推进内容，适合经历、案例和变化过程。',
  清单合集: '把多个要点整理成可扫描、可收藏和可执行的清单。',
  误区纠正: '先指出常见误解，再给出准确解释和正确做法，适合澄清认知。',
  案例拆解: '从背景、问题、做法到结果拆解一个案例，适合建立专业信任。',
  产品种草: '从使用场景和用户需求切入，再介绍产品价值、边界和适用条件。',
  观点论证: '提出核心观点，依次给出依据、解释和结论，适合表达判断与立场。',
}
export const pageLayouts = ['自动', '封面', '清单', '步骤', '对比', '分类', '关系', '例子', '总结']
export const audiences = ['自动判断', '零基础入门', '有一定基础', '专业读者', '自定义']
export const tones = ['自动匹配', '亲切易懂', '专业简洁', '轻松幽默', '温柔鼓励']
export const contentForms = [
  ['auto', '自动推荐'],
  ['single_infographic', '单页知识信息图'],
  ['multi_page_cards', '多页知识卡片'],
  ['flowchart', '流程图解'],
  ['comparison', '对比分析图'],
  ['methodology_poster', '方法论海报'],
  ['product_long_graphic', '产品介绍长图'],
  ['data_conclusion', '数据结论图'],
  ['checklist_poster', '清单海报'],
] as const
export const informationDensities = [
  ['auto', '自动推荐'],
  ['concise', '简洁'],
  ['standard', '标准'],
  ['high', '高密度'],
] as const
export const contentFormDescriptions: Record<OutlineContentForm, string> = {
  auto: '由模型结合主题、平台、读者、页数和资料选择最合适的图文形态。',
  single_infographic: '把一个主题完整压缩到一张纵向信息图中，适合知识分享和内容表达。',
  multi_page_cards: '拆成多页卡片，每页突出一个重点，适合连续滑动阅读。',
  flowchart: '突出步骤、判断、输入输出和先后关系，适合流程明确的主题。',
  comparison: '按统一维度并列比较不同方案、状态或选择，帮助读者快速判断。',
  methodology_poster: '突出可复用的方法、框架、工具和验收标准，适合系统方法分享。',
  product_long_graphic: '围绕产品用途、适用人群、核心能力、边界和下一步行动组织内容。',
  data_conclusion: '突出有来源的数据、变化和结论，不补写未经提供的数字。',
  checklist_poster: '整理为分组清单、检查项和完成标准，适合收藏和执行。',
}
export const informationDensityDescriptions: Record<InformationDensity, string> = {
  auto: '由模型根据主题复杂度和平台阅读场景选择合适的信息量。',
  concise: '只保留核心结论和少量支撑信息，留出更明显的留白。',
  standard: '在表达完整和手机可读之间保持平衡，每个模块保留必要解释。',
  high: '允许更多模块和短句，但必须分层清楚，不能靠缩小文字堆叠。',
}
export const publishingPlatforms = ['auto', 'xiaohongshu', 'douyin', 'wechat', 'multi'] as const
export const growthGoals = ['auto', 'follow', 'product', 'inquiry', 'conversion', 'brand', 'engagement', 'share'] as const
export type PublishingPlatform = typeof publishingPlatforms[number]
export type GrowthGoal = typeof growthGoals[number]
export type OutlineContentForm = typeof contentForms[number][0]
export type InformationDensity = typeof informationDensities[number][0]
export type OutlinePageCount = 'auto' | number
export interface OutlinePreferences {
  organization: string; audience: string; audience_detail: string; tone: string
  page_count: OutlinePageCount; platform: PublishingPlatform; goal: GrowthGoal
  content_form?: OutlineContentForm; information_density?: InformationDensity
}

export interface GrowthRecommendation {
  source?: 'model' | 'rules'
  outline_explanation?: Partial<Record<'platform' | 'goal' | 'audience' | 'organization' | 'tone' | 'content_form' | 'information_density' | 'sequence_meaning' | 'sequence_reason', string>>
  platform: PublishingPlatform
  goal: GrowthGoal
  layout: string
  image_style: string
  aspect_ratio: string
  content_structure: string
  reason: string
}

function normalizeContractValue<T extends string>(value: string | undefined, allowed: readonly T[], label: string): T {
  if (value === undefined || value === '') return 'auto' as T
  if (typeof value !== 'string') throw new Error(`${label}必须是有效选项。`)
  if (!allowed.includes(value as T)) throw new Error(`${label}必须是有效选项。`)
  return value as T
}

export function normalizePublishingPlatform(value?: string): PublishingPlatform {
  return normalizeContractValue(value, publishingPlatforms, '发布平台')
}

export function normalizeGrowthGoal(value?: string): GrowthGoal {
  return normalizeContractValue(value, growthGoals, '获客目标')
}

export function outlinePreferences(state: {
  outlineOrganization: string; outlineAudience: string; outlineAudienceDetail: string; outlineTone: string
  outlinePageCount: OutlinePageCount; outlinePlatform?: string; outlineGoal?: string
  outlineContentForm?: string; outlineInformationDensity?: string
}): OutlinePreferences {
  return { organization: resolvePromptValue('outline', 'organization', state.outlineOrganization, '自动'),
    audience: resolvePromptValue('outline', 'audience', state.outlineAudience, '自动判断'),
    audience_detail: state.outlineAudienceDetail,
    tone: resolvePromptValue('outline', 'tone', state.outlineTone, '自动匹配'),
    page_count: state.outlinePageCount,
    platform: normalizePublishingPlatform(state.outlinePlatform),
    goal: normalizeGrowthGoal(state.outlineGoal),
    content_form: (state.outlineContentForm || 'auto') as OutlineContentForm,
    information_density: (state.outlineInformationDensity || 'auto') as InformationDensity,
  }
}

export function imageParameters(state: {
  imageResolution: string; imageAspectRatio: string; imageQuality: string; imageOutputFormat: string
}): Record<string, string> {
  return { resolution: state.imageResolution, aspect_ratio: state.imageAspectRatio,
    quality: state.imageQuality, output_format: state.imageOutputFormat }
}

export function readLayout(content: string): string {
  return content.match(/^\s*单页布局\s*[:：]\s*([^\n]+)/m)?.[1].trim() || '自动'
}

export function withLayout(content: string, layout: string): string {
  if (/^\s*单页布局\s*[:：]/m.test(content)) {
    return content.replace(/^\s*单页布局\s*[:：][^\n]*/m, `单页布局：${layout}`)
  }
  const firstLine = content.indexOf('\n')
  return firstLine >= 0 ? `${content.slice(0, firstLine)}\n单页布局：${layout}${content.slice(firstLine)}`
    : `${content}\n单页布局：${layout}`
}
import { resolvePromptValue } from './promptCatalog'
