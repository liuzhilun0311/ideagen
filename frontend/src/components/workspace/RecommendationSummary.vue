<script setup lang="ts">
import { computed } from 'vue'
import type { GrowthRecommendation } from '../../features/generationOptions'
import { availableImageStyles } from '../../features/styles/catalog'
import { findItem, promptItems } from '../../features/promptCatalog'
import { contentStructureLabel } from '../../features/contentStructure'
import { useGeneratorStore } from '../../stores/generator'
import { palettes } from '../../features/styles/palette'
const store = useGeneratorStore()
const palette = computed(() => store.imageStyle.palette)
const paletteName = computed(() => palettes.find(item => item.id === palette.value?.recommendation)?.name)

const props = defineProps<{ recommendation: GrowthRecommendation }>()

const platformNames: Record<string, string> = {
  auto: '自动推荐', xiaohongshu: '小红书', douyin: '抖音', wechat: '公众号', multi: '通用多平台',
}
const goalNames: Record<string, string> = {
  share: '知识分享／内容表达',
  auto: '自动推荐', follow: '涨粉关注', product: '产品种草', inquiry: '私信咨询',
  conversion: '课程/服务转化', brand: '品牌认知', engagement: '评论互动',
}
const layoutName = computed(() => findItem(promptItems('image', 'layout'), props.recommendation.layout)?.name || props.recommendation.layout)
const styleName = computed(() => availableImageStyles().find(item =>
  item.id === props.recommendation.image_style || item.catalogId === props.recommendation.image_style,
)?.name || props.recommendation.image_style)
</script>

<template>
  <section class="recommendation" aria-label="本次推荐方案">
    <div class="recommendation-header">
      <div>
        <h3>本次推荐方案</h3>
      </div>
    </div>
    <dl class="recommendation-grid">
      <div><dt>平台</dt><dd>{{ platformNames[recommendation.platform] || recommendation.platform }}</dd></div>
      <div><dt>目标</dt><dd>{{ goalNames[recommendation.goal] || recommendation.goal }}</dd></div>
      <div><dt>页面布局</dt><dd>{{ layoutName }}</dd></div>
      <div><dt>图片风格</dt><dd>{{ styleName }}</dd></div>
      <div v-if="paletteName"><dt>推荐配色</dt><dd>{{ paletteName }}</dd></div>
      <div><dt>推荐比例</dt><dd>{{ recommendation.aspect_ratio }}</dd></div>
      <div v-if="recommendation.content_structure"><dt>推荐叙述顺序</dt><dd>{{ contentStructureLabel(recommendation.content_structure) }}</dd></div>
    </dl>
    <p class="reason"><strong>推荐理由：</strong>{{ recommendation.reason || '未提供推荐理由。' }}</p>
    <p v-if="paletteName" class="reason"><strong>配色理由：</strong>{{ palette?.reason || '本次未返回配色理由。' }}</p>
  </section>
</template>

<style scoped>
.recommendation { border-block:1px solid #d8e1f0; padding:16px 0; display:grid; gap:12px; min-width:0; }
.recommendation-header { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:12px; }
h3 { margin:0; color:#1d2738; font-size:14px; }
.recommendation-header p, .reason { margin:4px 0 0; color:#667085; font-size:12px; line-height:1.5; }
.recommendation-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 130px), 1fr)); gap:12px; margin:0; }
.recommendation-grid div { min-width:0; }
dt { color:#7a8494; font-size:11px; }
dd { margin:3px 0 0; color:#202938; font-size:13px; overflow-wrap:anywhere; }
@media (max-width:700px) { .recommendation-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
</style>
