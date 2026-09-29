<script setup lang="ts">
import { computed } from 'vue'
import { useGeneratorStore } from '../../stores/generator'
import { findItem, promptItems } from '../../features/promptCatalog'
import { contentStructureLabel } from '../../features/contentStructure'
import { contentForms, informationDensities } from '../../features/generationOptions'

const store = useGeneratorStore()
const platformNames: Record<string, string> = {
  auto: '自动推荐', xiaohongshu: '小红书', douyin: '抖音', wechat: '公众号', multi: '通用多平台',
}
const goalNames: Record<string, string> = {
  auto: '自动推荐', share: '知识分享／内容表达', follow: '涨粉关注', product: '产品种草',
  inquiry: '私信咨询', conversion: '课程/服务转化', brand: '品牌认知', engagement: '评论互动',
}
const audienceName = (value: string | undefined, detail?: string) => {
  if (!value) return '未记录'
  if (value === '自定义') return detail?.trim() || '自定义'
  return findItem(promptItems('outline', 'audience'), value)?.name || value
}
const structureName = (value: string | undefined) =>
  value === '自动' ? '自动推荐' : findItem(promptItems('outline', 'organization'), value)?.name || value || '未记录'
const actual = (value?: string) => !value || ['auto', '自动', '自动判断', '自动匹配'].includes(value) ? undefined : value
const toneName = (value: string | undefined) =>
  value === '自动匹配' ? '自动匹配' : findItem(promptItems('outline', 'tone'), value)?.name || value || '未记录'
const optionName = (options: readonly (readonly [string, string])[], value: string | undefined) =>
  options.find(([key]) => key === value)?.[1] || (value === 'auto' ? '自动推荐' : value || '未记录')
const requested = computed(() => store.outline.requested_preferences)
const adopted = computed(() => store.outline.generation_preferences)
const requestedItems = computed(() => [
  ['发布平台', platformNames[requested.value?.platform || ''] || '未记录'],
  ['创作目标', goalNames[requested.value?.goal || ''] || '未记录'],
  ['目标读者', audienceName(requested.value?.audience, requested.value?.audience_detail)],
  ['内容结构', structureName(requested.value?.organization)],
  ['表达语气', toneName(requested.value?.tone)],
  ['内容形态', optionName(contentForms, requested.value?.content_form)],
  ['信息密度', optionName(informationDensities, requested.value?.information_density)],
])
const adoptedItems = computed(() => [
  ['发布平台', platformNames[actual(adopted.value?.platform) || actual(store.outline.growth_recommendation?.platform) || ''] || '未记录'],
  ['创作目标', goalNames[actual(adopted.value?.goal) || actual(store.outline.growth_recommendation?.goal) || ''] || '未记录'],
  ['目标读者', audienceName(actual(adopted.value?.audience), adopted.value?.audience_detail)],
  ['内容结构', structureName(actual(adopted.value?.organization) || actual(store.outline.organization))],
  ['表达语气', toneName(actual(adopted.value?.tone))],
  ['内容形态', optionName(contentForms, actual(adopted.value?.content_form))],
  ['信息密度', optionName(informationDensities, actual(adopted.value?.information_density))],
])
const adoptedStructure = computed(() =>
  store.outline.growth_recommendation?.content_structure
    ? contentStructureLabel(store.outline.growth_recommendation.content_structure) : '')
const keys = ['platform', 'goal', 'audience', 'organization', 'tone', 'content_form', 'information_density'] as const
const explanation = computed(() => store.outline.growth_recommendation?.outline_explanation)
function reason(index: number) {
  const key = keys[index]!
  const selected = requested.value?.[key]
  if (selected && !['auto', '自动', '自动判断', '自动匹配'].includes(selected)) return '用户指定'
  if (adoptedItems.value[index]?.[1] === '未记录') return '本次未记录采用理由'
  return explanation.value?.[key] || '本次未记录采用理由'
}
</script>

<template>
  <section class="outline-parameter-summary" aria-label="大纲参数摘要">
    <table>
      <colgroup><col class="parameter-col"><col class="setting-col"><col class="adopted-col"><col class="reason-col"></colgroup>
      <thead><tr><th scope="col">参数</th><th scope="col">参数设置</th><th scope="col">实际采用</th><th scope="col">理由</th></tr></thead>
      <tbody>
        <tr v-for="([label, value], index) in requestedItems" :key="label">
          <th scope="row">{{ label }}</th>
          <td>{{ value }}</td>
          <td>{{ adoptedItems[index]?.[1] }}</td>
          <td class="reason">{{ reason(index) }}</td>
        </tr>
        <tr v-if="adoptedStructure" class="sequence-row">
          <td colspan="4">
            <p><span class="parameter-name">叙述顺序</span>{{ adoptedStructure }}</p>
            <p v-if="explanation?.sequence_meaning" class="reason">含义：{{ explanation.sequence_meaning }}</p>
            <p v-if="explanation?.sequence_reason" class="reason">采用理由：{{ explanation.sequence_reason }}</p>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="explanation" class="note">推荐理由由 AI 提供，对应生成时的大纲；编辑后的内容需重新判断。</p>
  </section>
</template>

<style scoped>
.outline-parameter-summary { margin:16px 0 4px; padding:14px; border:1px solid #e2e5eb; border-radius:6px; background:#f8fafc; }
table { width:100%; table-layout:fixed; border-collapse:collapse; color:#202938; font-size:13px; line-height:1.6; }
.parameter-col { width:14%; } .setting-col { width:22%; } .adopted-col { width:26%; } .reason-col { width:38%; }
th, td { text-align:left; vertical-align:top; padding:9px 12px; overflow-wrap:anywhere; font-weight:400; }
thead th { font-size:14px; font-weight:650; padding-top:0; }
tbody tr + tr { border-top:1px solid #e2e5eb; }
th:first-child, td:first-child { padding-left:0; }
td:last-child, th:last-child { padding-right:0; }
.parameter-name { display:block; color:#7a8494; font-size:12px; margin-bottom:3px; }
.reason, .note { color:#697386; font-size:12px; }
.sequence-row p { margin:0; }
.sequence-row .parameter-name { display:inline; margin-right:10px; }
.sequence-row .reason { margin-top:5px; }
.note { margin:8px 0 0; }
@media(max-width:600px) {
  .outline-parameter-summary { padding:10px; }
  th, td { padding:8px 6px; }
  .parameter-col { width:20%; } .setting-col { width:23%; } .adopted-col { width:25%; } .reason-col { width:32%; }
}
</style>
