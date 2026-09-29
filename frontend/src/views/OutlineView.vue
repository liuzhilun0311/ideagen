<template>
  <div class="container" style="max-width: 100%;">
    <div class="page-header" style="max-width: 1200px; margin: 0 auto 30px auto; align-items: center;">
      <div>
        <h1 class="page-title">编辑大纲</h1>
        <!-- <p class="page-subtitle">
          调整页面顺序，修改文案，打造完美内容
          <span v-if="isSaving" class="save-indicator saving">保存中...</span>
          <span v-else class="save-indicator saved">已保存</span>
        </p> -->
      </div>
      <!-- 导航按钮一行：进入编辑图文 / 退出编辑 -->
      <div class="nav-row" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        <button
          class="btn btn-info btn-small"
          @click="startGeneration"
          :disabled="isRegenerating || store.outline.pages.length === 0"
          :title="isRegenerating ? '大纲生成中，完成后可进入' : (store.outline.pages.length === 0 ? '请先生成大纲' : '')"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>
          进入编辑图文
        </button>
        <button class="btn btn-warning btn-small" @click="exitEdit">
          退出编辑
        </button>
      </div>
    </div>
    <!-- 大纲模块：大纲提示词/模型选择 + 生成大纲 + 所生成的大纲 -->
    <div class="card outline-module">
      <!-- 生成工具栏：大纲提示词 / 大纲模型 / 生成大纲（含取消）/ 导出大纲 -->
      <div class="toolbar-row card-toolbar-row">
        <div class="inline-prompt">
          <label class="prompt-label" for="outline-prompt">提示词</label>
          <select id="outline-prompt" v-model="store.outlinePromptName" class="prompt-select">
            <option value="">默认提示词</option>
            <option v-for="p in outlinePrompts" :key="p.name" :value="p.name">{{ p.name }}</option>
          </select>
        </div>
        <div class="inline-prompt model-prompt">
          <label class="prompt-label" for="outline-model">模型</label>
          <select id="outline-model" v-model="store.outlineModelName" class="prompt-select">
            <option v-if="outlineModels.length === 0" value="">无可用模型</option>
            <option v-for="m in outlineModels" :key="m.name" :value="m.name">{{ m.display_name }}</option>
          </select>
        </div>
        <button
          class="btn btn-small btn-fixed-4"
          :class="isRegenerating ? 'btn-danger' : 'btn-success'"
          @click="isRegenerating ? cancelOutlineGeneration() : regenerateOutline()"
        >
          {{ isRegenerating ? '取消' : '生成大纲' }}
        </button>
        <button class="btn btn-pink btn-small" @click="exportRawPrompts" :disabled="!store.outline.pages.length">
          导出大纲
        </button>
      </div>
      <div class="outline-grid">
      <div 
        v-for="(page, idx) in store.outline.pages" 
        :key="page.index"
        class="card outline-card"
        :draggable="true"
        @dragstart="onDragStart($event, idx)"
        @dragover.prevent="onDragOver($event, idx)"
        @drop="onDrop($event, idx)"
        :class="{ 'dragging-over': dragOverIndex === idx }"
      >
        <div class="card-top-bar">
          <div class="page-info">
             <span class="page-number">P{{ idx + 1 }}</span>
             <span class="page-type" :class="page.type">{{ getPageTypeName(page.type) }}</span>
          </div>
          
          <div class="card-controls">
            <div class="drag-handle" title="拖拽排序">
               <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#999" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="1"></circle><circle cx="9" cy="5" r="1"></circle><circle cx="9" cy="19" r="1"></circle><circle cx="15" cy="12" r="1"></circle><circle cx="15" cy="5" r="1"></circle><circle cx="15" cy="19" r="1"></circle></svg>
            </div>
            <button class="icon-btn" @click="deletePage(idx)" title="删除此页">
               <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
        </div>
        <textarea
          v-model="page.content"
          class="textarea-paper"
          placeholder="在此输入文案..."
          @input="store.updatePage(page.index, page.content)"
        />
        
        <div class="word-count">{{ page.content.length }} 字</div>
      </div>
      <div class="card add-card-dashed" @click="addPage('content')">
        <div class="add-content">
          <div class="add-icon">+</div>
          <span>添加页面</span>
        </div>
      </div>
      </div>
    </div>
    
    <div style="height: 100px;"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onActivated, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { updateHistory, createHistory, generateOutline, getPrompts, cancelCurrentGeneration, getConfig, type PromptItem } from '../api'
import { outlineRequest } from '../features/outlineRequest'

// 注释掉外部promptBuilder导入，全部内联实现
// import { buildPrompt } from '@/utils/promptBuilder'
// import { buildNegativePrompt } from '@/utils/negativePromptBuilder'

const router = useRouter()
const store = useGeneratorStore()

// 退出编辑：按进入来源返回（历史记录进入回历史，其他回创作中心）
function exitEdit() {
  router.push(store.entrySource === 'history' ? '/history' : '/')
}

const dragOverIndex = ref<number | null>(null)
const dragStartIndex = ref<number | null>(null)
const isSaving = ref(false)
// 大纲提示词列表（不含系统默认）
const outlinePrompts = ref<PromptItem[]>([])
// 大纲模型（服务商）列表（来自模型设置配置）：{ name: 服务商标识, display_name: 列表展示名称 }
const outlineModels = ref<{ name: string; display_name: string }[]>([])

const getPageTypeName = (type: string) => {
  const names: Record<string, string> = {
    cover: '封面',
    content: '内容',
    summary: '总结',
    infographic: '信息图'
  }
  return names[type] || '内容'
}

const onDragStart = (e: DragEvent, index: number) => {
  dragStartIndex.value = index
  if(e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

const onDragOver = (_e: DragEvent, index: number) => {
  if(dragStartIndex.value === index) return
  dragOverIndex.value = index
}

const onDrop = (_e: DragEvent, index: number) => {
  dragOverIndex.value = null
  if(dragStartIndex.value !== null && dragStartIndex.value !== index) {
    store.movePage(dragStartIndex.value, index)
  }
  dragStartIndex.value = null
}

const deletePage = (index: number) => {
  if(confirm('确定要删除这一页吗？')) {
    store.deletePage(index)
  }
}

const addPage = (type: 'cover' | 'content' | 'summary') => {
  store.addPage(type)
  nextTick(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  })
}

const isRegenerating = ref(false)
// 大纲生成的中断控制器（用于"取消生成"）
let outlineAbort: AbortController | null = null

const regenerateOutline = async () => {
  if (!store.topic.trim()) {
    alert('请先输入主题')
    return
  }
  // 重新生成前取消上一次未结束的请求
  if (outlineAbort) {
    outlineAbort.abort()
    outlineAbort = null
  }
  outlineAbort = new AbortController()

  isRegenerating.value = true
  try {
    const input = outlineRequest(store)
    const result = await generateOutline(
      input.topic, input.images, outlineAbort.signal, store.outlinePromptName,
      input.reference_content, input.provider, input.preferences.organization,
      input.preferences, input.reference_roles,
    )
    if (result.success && result.pages) {
      store.setOutline(result.outline || '', result.pages)
      store.outline.requested_preferences = { ...input.preferences }
      store.outline.generation_preferences = result.generation_preferences || { ...input.preferences }
      store.outline.growth_recommendation = result.growth_recommendation
      if (store.recordId) {
        updateHistory(store.recordId, {
          outline: { raw: result.outline || '', pages: result.pages },
          title: store.topic.trim()
        }).catch(() => {})
      }
    } else {
      alert('重新生成大纲失败：' + (result.error || result.error_message || '未知错误'))
    }
  } catch (e: any) {
    // 主动取消不当作错误
    if (e?.name === 'CanceledError' || e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') {
      return
    }
    alert('重新生成大纲失败：' + (e.message || '未知错误'))
  } finally {
    outlineAbort = null
    isRegenerating.value = false
  }
}

/** 取消大纲生成（同时通知后端作废结果） */
const cancelOutlineGeneration = () => {
  if (outlineAbort) {
    outlineAbort.abort()
    outlineAbort = null
  }
  cancelCurrentGeneration().catch(() => {})
  isRegenerating.value = false
}

const startGeneration = async () => {
  // 大纲尚未生成完成时不允许进入编辑图文
  if (isRegenerating.value || store.outline.pages.length === 0) {
    alert(isRegenerating.value ? '大纲正在生成中，请稍候...' : '请先完成大纲生成')
    return
  }
  if (saveTimer !== null) {
    clearTimeout(saveTimer)
    saveTimer = null
    await autoSaveOutline()
  }
  // 进入生成页：已有图片会自动恢复显示；没图才需要点"生成图片"
  router.push('/generate')
}

// 内联导出函数，增加空值兜底，不再依赖外部ts文件
function exportRawPrompts() {
  try {
    const pages = store.outline.pages
    const opts = { style: '', extraPositive: '', extraNegative: '' }
    if (!pages || pages.length === 0) {
      alert('当前没有页面，无法导出')
      return
    }
    let textContent = ''
    for(let i = 0; i < pages.length; i++) {
      const p = pages[i]
      // 内联构建正向prompt
      const baseStyle = opts.style || "小红书摄影，高清，氛围感，胶片质感，8k，细节丰富"
      const pos = `${p.content}\n${baseStyle}\n${opts.extraPositive||''}`.trim()
      // 内联构建反向prompt
      const baseNeg = "模糊，低分辨率，变形，丑，水印，文字，签名，黑白，畸形，手指错误，多余肢体"
      const neg = `${baseNeg} ${opts.extraNegative||''}`.trim()

      textContent += `======== PAGE ${i+1} ========
POSITIVE：
${pos}
NEGATIVE：
${neg}
`
    }
    const content = '\uFEFF' + textContent
    const bytes = new TextEncoder().encode(content)
    const blob = new Blob([bytes], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const aTag = document.createElement('a')
    aTag.href = url
    aTag.download = `prompt_export_${Date.now()}.txt`
    document.body.appendChild(aTag)
    aTag.click()
    aTag.remove()
    URL.revokeObjectURL(url)
  } catch(e) {
    console.error('导出异常', e)
    alert(`导出失败：${(e as Error).message}`)
  }
}

;(window as any).exportRawPrompts = exportRawPrompts

// 自动保存逻辑
let saveTimer: number | null = null
const autoSaveOutline = async () => {
  if (!store.recordId) {
    if (store.outline.pages && store.outline.pages.length > 0) {
      try {
        const res = await createHistory(store.topic || '未命名', store.outline)
        if(res?.record_id) store.setRecordId(res.record_id)
      } catch(err) {
        console.error('创建记录失败', err)
      }
    }
    return
  }
  try {
    isSaving.value = true
    await updateHistory(store.recordId, {
      outline: store.outline
    })
  } catch(err) {
    console.error('保存失败', err)
  } finally {
    isSaving.value = false
  }
}

const debouncedSave = () => {
  if(saveTimer) clearTimeout(saveTimer)
  saveTimer = window.setTimeout(()=>{
    autoSaveOutline()
  }, 300)
}

onMounted(async ()=>{
  // 草稿清理已由路由守卫统一处理（仅新建任务时清空），
  // 这里不再调用 prepareNewOutline，避免从图文页返回/组件重新挂载时误清空当前大纲
  // 加载用户自定义大纲提示词
  try {
    const res = await getPrompts()
    if (res.success && res.prompts?.outline) {
      outlinePrompts.value = res.prompts.outline.filter(p => !p.is_base)
    }
  } catch (e) {
    console.error('加载大纲提示词失败:', e)
  }
  await loadOutlineModels()
  await autoSaveOutline()
})

// 加载可选模型（服务商）列表（模型设置里配置的文本服务商）
// onMounted + onActivated 都调用：KeepAlive 缓存下切回页面时也会刷新启用状态
async function loadOutlineModels() {
  try {
    const cfgRes = await getConfig()
    if (cfgRes.success && cfgRes.config?.text_generation?.providers) {
      const providers = cfgRes.config.text_generation.providers || {}
      // 只展示已启用（enabled !== false）的服务商
      outlineModels.value = Object.keys(providers)
        .filter(n => providers[n]?.enabled !== false)
        .map(n => ({
          name: n,
          display_name: providers[n]?.display_name || n
        }))
      // 默认模型：无记忆时选第一个激活的（没有则为空）；记忆的模型已停用时回退到第一个
      if (outlineModels.value.length > 0) {
        const names = outlineModels.value.map(m => m.name)
        if (!store.outlineModelName || !names.includes(store.outlineModelName)) {
          store.outlineModelName = outlineModels.value[0].name
        }
      } else {
        store.outlineModelName = ''
      }
    }
  } catch (e) {
    console.error('加载大纲模型列表失败:', e)
  }
}

onUnmounted(()=>{
  if(saveTimer) clearTimeout(saveTimer)
})

// KeepAlive 缓存复用：复位可能残留的"生成中"状态
// （上次在生成大纲过程中直接退出页面，isRegenerating 会停留在 true，重新进入会点不了按钮）
onActivated(()=>{
  isRegenerating.value = false
  if (outlineAbort) {
    outlineAbort.abort()
    outlineAbort = null
  }
  // 切回页面时刷新模型列表（模型设置里可能改过启用状态）
  loadOutlineModels()
})

watch(()=>store.outline.pages, ()=>{
  debouncedSave()
}, {deep:true})
</script>

<style scoped>
/* 提示词/模型选择框：浅蓝色主题（与编辑图文界面一致） */
.inline-prompt .prompt-label {
  color: #2563eb;
}
.inline-prompt .prompt-select {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}
.inline-prompt .prompt-select:focus {
  border-color: #2563eb;
}
/* 生成/取消合并按钮：按四个字固定宽度，切换时大小不变 */
.btn-fixed-4 {
  min-width: 98px;
}
.save-indicator {
  margin-left:12px;
  font-size:12px;
  font-weight:500;
  padding:2px 8px;
  border-radius:4px;
}
.save-indicator.saving {
  color:#1890ff;
  background:#e6f7ff;
  border:1px solid #91caff;
}
.save-indicator.saved {
  color:#52c41a;
  background:#f6ffed;
  border:1px solid #b7eb8f;
}
.outline-grid {
  display:grid;
  grid-template-columns: repeat(auto-fill, minmax(280px,1fr));
  gap:24px;
  max-width:1400px;
  margin:0 auto;
  padding:0 20px;
}
.outline-card {
  display:flex;
  flex-direction:column;
  padding:16px;
  border-radius:8px;
  background:#fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  min-height:360px;
}
.outline-card:hover {
  transform: translateY(-4px);
  box-shadow:0 8px 24px rgba(0,0,0,0.08);
  z-index:10;
}
.outline-card.dragging-over {
  border:2px dashed var(--primary-color);
  opacity:0.8;
}
.card-top-bar {
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-bottom:12px;
  padding-bottom:8px;
  border-bottom:1px solid #f5f5f5;
}
.page-info {
  display:flex;
  gap:8px;
  align-items:center;
}
.page-number {
  font-size:14px;
  font-weight:700;
  color:#ccc;
}
.page-type {
  font-size:11px;
  padding:2px 6px;
  border-radius:4px;
  font-weight:600;
  text-transform:uppercase;
  letter-spacing:0.5px;
}
.page-type.cover {
  color:#FF4D4F;
  background:#FFF1F0;
}
.page-type.content {
  color:#1890ff;
  background:#E6F7FF;
}
.page-type.summary {
  color:#52C41A;
  background:#F6FFED;
}
.page-type.infographic {
  color:#7C3AED;
  background:#EDE9FE;
}
.card-controls {
  display:flex;
  gap:8px;
  opacity:0.4;
}
.outline-card:hover .card-controls {
  opacity:1;
}
.drag-handle {
  cursor:grab;
}
.icon-btn {
  border:none;
  background:transparent;
  cursor:pointer;
  color:#999;
}
.icon-btn:hover {
  color:#FF4D4F;
}
.textarea-paper {
  flex:1;
  width:100%;
  border:none;
  background:transparent;
  font-size:16px;
  line-height:1.7;
  color:#333;
  resize:none;
}
.textarea-paper:focus {
  outline:none;
}
.word-count {
  text-align:right;
  font-size:11px;
  color:#ccc;
  margin-top:8px;
}
.add-card-dashed {
  border:2px dashed #eee;
  background:transparent;
  display:flex;
  align-items:center;
  justify-content:center;
  min-height:360px;
  cursor:pointer;
  color:#ccc;
}
.add-card-dashed:hover {
  border-color:var(--primary-color);
  color:var(--primary-color);
  background:rgba(255,36,66,0.02);
}
.add-content {
  text-align:center;
}
.add-icon {
  font-size:32px;
  margin-bottom:8px;
}
/* 导航按钮行：进入编辑图文 / 退出编辑（页头右侧一行） */
.nav-row {
  display:flex;
  align-items:center;
  gap:12px;
  flex-wrap:wrap;
}
/* 大纲模块内的生成工具栏（顶部一行 + 下划线分隔，与图片模块风格一致） */
.toolbar-row {
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap:10px;
  flex-wrap:wrap;
  width:100%;
}
.card-toolbar-row {
  width:100%;
  margin-bottom:16px;
  padding-bottom:16px;
  border-bottom:1px solid var(--border-color);
}
/* 大纲模块：与页头同宽居中；内部大纲网格铺满卡片 */
.outline-module {
  max-width:1200px;
  margin:0 auto 24px auto;
}
.outline-module .outline-grid {
  max-width:none;
  margin:0;
  padding:0;
}
</style>
