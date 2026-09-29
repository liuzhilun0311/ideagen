<script setup lang="ts">
import { useGeneratorStore } from '../../stores/generator'
import HelpTip from '../common/HelpTip.vue'
import { computed } from 'vue'
import { selectionItems, findItem, promptItems } from '../../features/promptCatalog'
import { contentFormDescriptions, contentForms, informationDensities, informationDensityDescriptions, organizationDescriptions } from '../../features/generationOptions'

defineProps<{ disabled?: boolean }>()
const store = useGeneratorStore()
const audiences = computed(() => selectionItems('outline', 'audience', store.outlineAudience))
const organizations = computed(() => selectionItems('outline', 'organization', store.outlineOrganization))
const customAudience = computed(() =>
  findItem(promptItems('outline', 'audience'), store.outlineAudience)?.legacyValue === '自定义')
const selectedOrganization = computed(() => findItem(organizations.value, store.outlineOrganization))
const selectedContentFormDescription = computed(() =>
  contentFormDescriptions[store.outlineContentForm as keyof typeof contentFormDescriptions] || contentFormDescriptions.auto)
const selectedDensityDescription = computed(() =>
  informationDensityDescriptions[store.outlineInformationDensity as keyof typeof informationDensityDescriptions] || informationDensityDescriptions.auto)

const platformOptions = [
  ['auto', '自动推荐'],
  ['xiaohongshu', '小红书'],
  ['douyin', '抖音'],
  ['wechat', '公众号'],
  ['multi', '通用多平台'],
] as const

const goalOptions = [
  ['auto', '自动推荐'],
  ['share', '知识分享／内容表达'],
  ['follow', '涨粉关注'],
  ['product', '产品种草'],
  ['inquiry', '私信咨询'],
  ['conversion', '课程/服务转化'],
  ['brand', '品牌认知'],
  ['engagement', '评论互动'],
] as const
</script>

<template>
  <fieldset class="growth-target-options" :disabled="disabled" aria-label="发布平台、创作目标、目标读者与内容结构">
    <div class="growth-target-grid">
      <div class="option-field">
        <div class="option-heading">
          <label for="creation-platform">发布平台</label>
          <HelpTip label="发布平台帮助" text="选择内容主要发布的平台，系统会据此调整大纲表达，并推荐图片风格、布局和比例。尚未确定时选自动推荐；需要兼顾多个平台时选通用多平台。" />
        </div>
        <select id="creation-platform" v-model="store.outlinePlatform" class="field">
          <option v-for="[value, name] in platformOptions" :key="value" :value="value">{{ name }}</option>
        </select>
      </div>
      <div class="option-field">
        <div class="option-heading">
          <label for="creation-goal">创作目标</label>
          <HelpTip label="创作目标帮助" text="选择这次创作最希望达成的结果，系统会据此调整大纲重点和结尾引导。以分享知识为主可选知识分享／内容表达；希望吸引关注可选涨粉关注。不确定时选自动推荐。" />
        </div>
        <select id="creation-goal" v-model="store.outlineGoal" class="field">
          <option v-for="[value, name] in goalOptions" :key="value" :value="value">{{ name }}</option>
        </select>
      </div>
      <div class="option-field">
        <div class="option-heading">
          <label for="creation-audience">目标读者</label>
          <HelpTip label="目标读者帮助" text="决定内容的解释深度、术语多少和示例难度。可以选择读者的知识基础，或选择自定义填写具体人群；不确定时选自动判断。" />
        </div>
        <select id="creation-audience" v-model="store.outlineAudience" class="field">
          <option v-for="item in audiences" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.name === '自动判断' ? '自动推荐' : item.name }}</option>
        </select>
        <template v-if="customAudience">
          <label for="creation-audience-detail">具体读者</label>
          <input id="creation-audience-detail" v-model="store.outlineAudienceDetail" class="field"
            maxlength="120" placeholder="例如：刚入职的上班族、企业采购负责人" />
        </template>
        <p v-if="audiences.some(item => item.unavailable)" role="alert">所选目标读者不可用，请重新选择。</p>
      </div>
      <div class="option-field">
        <div class="option-heading">
          <label for="creation-organization">内容结构</label>
          <HelpTip label="内容结构帮助" text="决定大纲的叙述顺序。首次创作建议选择自动推荐，生成后可在查看大纲中对照系统实际采用的结构；不满意时再固定选择一种结构重新生成。" />
        </div>
        <select id="creation-organization" v-model="store.outlineOrganization" class="field">
          <option v-for="item in organizations" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.legacyValue === '自动' ? '自动推荐' : item.name }}</option>
        </select>
        <small class="option-description">{{ selectedOrganization?.description || organizationDescriptions[selectedOrganization?.legacyValue || store.outlineOrganization] || organizationDescriptions.自动 }}</small>
        <p v-if="organizations.some(item => item.unavailable)" role="alert">所选内容结构不可用，请重新选择。</p>
      </div>
      <div class="option-field">
        <div class="option-heading">
          <label for="creation-content-form">内容形态</label>
          <HelpTip label="内容形态帮助" text="决定是一张完整的信息图、多页知识卡片，还是流程图、对比图等表达形式。首次创作建议自动推荐；生成后可在查看编辑大纲中查看实际采用的形态。" />
        </div>
        <select id="creation-content-form" v-model="store.outlineContentForm" class="field">
          <option v-for="[value, name] in contentForms" :key="value" :value="value">{{ name }}</option>
        </select>
        <small class="option-description">{{ selectedContentFormDescription }}</small>
      </div>
      <div class="option-field">
        <div class="option-heading">
          <label for="creation-information-density">信息密度</label>
          <HelpTip label="信息密度帮助" text="控制一页或整套内容放多少信息。高密度会增加模块，但仍以手机可读和清晰分层为前提，不会靠缩小字体堆字。" />
        </div>
        <select id="creation-information-density" v-model="store.outlineInformationDensity" class="field">
          <option v-for="[value, name] in informationDensities" :key="value" :value="value">{{ name }}</option>
        </select>
        <small class="option-description">{{ selectedDensityDescription }}</small>
      </div>
    </div>
  </fieldset>
</template>

<style scoped>
.growth-target-options { display: grid; gap: 14px; margin: 0; padding: 0; border: 0; min-width: 0; }
.growth-target-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
.option-field { display: grid; gap: 7px; min-width: 0; }
.option-heading { display: flex; align-items: center; gap: 6px; }
label { color: #252935; font-size: 13px; }
.field { width: 100%; min-height: 44px; min-width: 0; font-size: 14px; }
.option-description { color: #656b78; font-size: 12px; line-height: 1.5; }
@media (max-width: 700px) {
  .field { font-size: 16px; }
}
</style>
