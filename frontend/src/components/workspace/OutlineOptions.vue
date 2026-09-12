<script setup lang="ts">
import { useGeneratorStore } from '../../stores/generator'
import { computed } from 'vue'
import { selectionItems, findItem, promptItems, usePromptCatalog } from '../../features/promptCatalog'
import HelpTip from '../common/HelpTip.vue'
defineProps<{ disabled?: boolean; id: string }>()
const store = useGeneratorStore()
const catalog = usePromptCatalog()
const organizations = computed(() => selectionItems('outline', 'organization', store.outlineOrganization))
const audiences = computed(() => selectionItems('outline', 'audience', store.outlineAudience))
const tones = computed(() => selectionItems('outline', 'tone', store.outlineTone))
const customAudience = computed(() => findItem(promptItems('outline', 'audience'), store.outlineAudience)?.legacyValue === '自定义')
</script>

<template>
  <fieldset class="outline-options" :disabled="disabled">
    <legend>大纲偏好</legend>
    <p class="options-intro">调整内容的组织方式、受众和表达语气。</p>
    <label :for="`${id}-organization`">大纲组织方式 <HelpTip text="决定整套内容的讲述顺序，例如分类递进、步骤教程或问题解决。" />
      <select :id="`${id}-organization`" v-model="store.outlineOrganization" class="field">
        <option v-for="item in organizations" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.name }}</option>
      </select>
    </label>
    <label :for="`${id}-audience`">目标受众 <HelpTip text="决定解释深度、术语多少和示例难度。" />
      <select :id="`${id}-audience`" v-model="store.outlineAudience" class="field">
        <option v-for="item in audiences" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.name }}</option>
      </select>
    </label>
    <label v-if="customAudience" :for="`${id}-audience-detail`">具体受众
      <input :id="`${id}-audience-detail`" v-model="store.outlineAudienceDetail" class="field" maxlength="120" placeholder="例如：刚入职的上班族" />
    </label>
    <label :for="`${id}-tone`">表达语气 <HelpTip text="决定文字的表达感觉，例如亲切易懂、专业简洁或轻松幽默。" />
      <select :id="`${id}-tone`" v-model="store.outlineTone" class="field">
        <option v-for="item in tones" :key="item.id" :value="item.value" :disabled="item.unavailable">{{ item.name }}</option>
      </select>
    </label>
  </fieldset>
  <p v-if="[...organizations, ...audiences, ...tones].some(item => item.unavailable)" role="alert">所选提示词不可用，请重新选择。</p>
  <p v-if="catalog.error.value" role="status">{{ catalog.error.value }} <button type="button" :disabled="disabled || catalog.loading.value" @click="catalog.refresh">刷新目录</button></p>
</template>

<style scoped>
.outline-options { display:grid; gap:14px; border:0; padding:0; margin:0; min-width:0; }
legend { padding:0; color:#252935; font-size:14px; font-weight:650; }
.options-intro { margin:-6px 0 2px; color:#656b78; font-size:12px; line-height:1.5; }
label { display:grid; gap:7px; font-size:13px; min-width:0; }
.field { width:100%; min-height:44px; min-width:0; font-size:14px; }
@media(max-width:700px) { .field { font-size:16px; } }
</style>
