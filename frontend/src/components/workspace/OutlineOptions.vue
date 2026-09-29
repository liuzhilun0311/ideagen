<script setup lang="ts">
import { useGeneratorStore } from '../../stores/generator'
import { computed } from 'vue'
import { selectionItems, findItem, promptItems } from '../../features/promptCatalog'
import HelpTip from '../common/HelpTip.vue'
import GenerationGuide from './GenerationGuide.vue'
import { contentFormDescriptions, contentForms, informationDensities, informationDensityDescriptions, organizationDescriptions } from '../../features/generationOptions'
const props = withDefaults(defineProps<{ disabled?: boolean; id: string; showGrowth?: boolean; showAdvanced?: boolean }>(), {
  showGrowth: true,
  showAdvanced: true,
})
const store = useGeneratorStore()
const organizations = computed(() => selectionItems('outline', 'organization', store.outlineOrganization))
const audiences = computed(() => selectionItems('outline', 'audience', store.outlineAudience))
const tones = computed(() => selectionItems('outline', 'tone', store.outlineTone))
const customAudience = computed(() => findItem(promptItems('outline', 'audience'), store.outlineAudience)?.legacyValue === '自定义')
const selectedOrganization = computed(() => findItem(organizations.value, store.outlineOrganization))
const selectedContentFormDescription = computed(() =>
  contentFormDescriptions[store.outlineContentForm as keyof typeof contentFormDescriptions] || contentFormDescriptions.auto)
const selectedDensityDescription = computed(() =>
  informationDensityDescriptions[store.outlineInformationDensity as keyof typeof informationDensityDescriptions] || informationDensityDescriptions.auto)
const platformOptions = [
  ['auto', '自动推荐'], ['xiaohongshu', '小红书'], ['douyin', '抖音'], ['wechat', '公众号'], ['multi', '通用多平台'],
]
const goalOptions = [
  ['share', '知识分享／内容表达'],
  ['auto', '自动推荐'], ['follow', '涨粉关注'], ['product', '产品种草'], ['inquiry', '私信咨询'],
  ['conversion', '课程/服务转化'], ['brand', '品牌认知'], ['engagement', '评论互动'],
]
</script>

<template>
  <fieldset class="outline-options" :disabled="disabled">
    <legend v-if="props.showAdvanced">大纲偏好 <GenerationGuide kind="outline" /></legend>
    <p v-if="props.showAdvanced" class="options-intro">调整内容形态、组织方式、受众、信息密度和表达语气。</p>
    <label v-if="props.showAdvanced" :for="`${id}-organization`">内容结构 <HelpTip text="决定图片和文案共同遵循的讲述顺序；自动时综合主题、受众、页数、平台与目标推荐。" />
      <select :id="`${id}-organization`" v-model="store.outlineOrganization" class="field">
        <option v-for="item in organizations" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.name === '自动' ? '自动推荐' : item.name }}</option>
      </select>
      <small class="option-description">{{ selectedOrganization?.description || organizationDescriptions[selectedOrganization?.legacyValue || store.outlineOrganization] || organizationDescriptions.自动 }}</small>
    </label>
    <label v-if="props.showAdvanced" :for="`${id}-audience`">目标受众 <HelpTip text="决定解释深度、术语多少和示例难度。" />
      <select :id="`${id}-audience`" v-model="store.outlineAudience" class="field">
        <option v-for="item in audiences" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.name === '自动判断' ? '自动推荐' : item.name }}</option>
      </select>
    </label>
    <label v-if="props.showAdvanced && customAudience" :for="`${id}-audience-detail`">具体受众
      <input :id="`${id}-audience-detail`" v-model="store.outlineAudienceDetail" class="field" maxlength="120" placeholder="例如：刚入职的上班族" />
    </label>
    <label v-if="props.showAdvanced" :for="`${id}-tone`">表达语气 <HelpTip text="决定文字的表达感觉，例如亲切易懂、专业简洁或轻松幽默。" />
      <select :id="`${id}-tone`" v-model="store.outlineTone" class="field">
        <option v-for="item in tones" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.name }}</option>
      </select>
    </label>
    <label v-if="props.showAdvanced" :for="`${id}-content-form`">内容形态 <HelpTip text="决定大纲采用单页信息图、多页卡片、流程图解等形式。自动推荐时先生成，再在查看编辑大纲中确认实际采用。" />
      <select :id="`${id}-content-form`" v-model="store.outlineContentForm" class="field">
        <option v-for="[value, name] in contentForms" :key="value" :value="value">{{ name }}</option>
      </select>
      <small class="option-description">{{ selectedContentFormDescription }}</small>
    </label>
    <label v-if="props.showAdvanced" :for="`${id}-information-density`">信息密度 <HelpTip text="控制内容量和模块数量；高密度仍必须保持手机可读，不能靠缩小文字堆叠。" />
      <select :id="`${id}-information-density`" v-model="store.outlineInformationDensity" class="field">
        <option v-for="[value, name] in informationDensities" :key="value" :value="value">{{ name }}</option>
      </select>
      <small class="option-description">{{ selectedDensityDescription }}</small>
    </label>
    <label :for="`${id}-page-count`">大纲页数 <HelpTip text="普通多页内容的页数包含封面和总结；单页知识信息图会只生成一页。选择自动时由系统按主题判断。" />
      <select :id="`${id}-page-count`" v-model="store.outlinePageCount" class="field">
        <option value="auto">自动推荐</option>
        <option v-for="count in 15" :key="count" :value="count">{{ count }} 页</option>
      </select>
    </label>
    <template v-if="props.showGrowth">
      <label :for="`${id}-platform`">发布平台 <HelpTip text="决定页面比例、信息密度和行动号召的推荐方向。" />
        <select :id="`${id}-platform`" v-model="store.outlinePlatform" class="field">
          <option v-for="[value, name] in platformOptions" :key="value" :value="value">{{ name }}</option>
        </select>
      </label>
      <label :for="`${id}-goal`">获客目标 <HelpTip text="决定内容更强调关注、种草、咨询、转化还是互动。" />
        <select :id="`${id}-goal`" v-model="store.outlineGoal" class="field">
          <option v-for="[value, name] in goalOptions" :key="value" :value="value">{{ name }}</option>
        </select>
      </label>
    </template>
  </fieldset>
  <p v-if="[...organizations, ...audiences, ...tones].some(item => item.unavailable)" role="alert">所选提示词不可用，请重新选择。</p>
</template>

<style scoped>
.outline-options { display:grid; gap:14px; border:0; padding:0; margin:0; min-width:0; }
legend { padding:0; color:#252935; font-size:14px; font-weight:650; }
.options-intro { margin:-6px 0 2px; color:#656b78; font-size:12px; line-height:1.5; }
label { display:flex; flex-wrap:wrap; align-items:center; gap:4px 6px; font-size:13px; min-width:0; }
label .field { flex-basis:100%; }
.field { width:100%; min-height:44px; min-width:0; font-size:14px; }
.option-description { color:#656b78; font-size:12px; line-height:1.5; }
@media(max-width:700px) { .field { font-size:16px; } }
</style>
