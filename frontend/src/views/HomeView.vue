<template>
  <div class="container home-container">
    <!-- 图片网格轮播背景 -->
    <ShowcaseBackground />
    <!-- Hero Area -->
    <div class="hero-section">
      <div class="hero-content">
        <h1 class="page-title">灵感一触而就</h1>
        <p class="page-subtitle">您专注奇思妙想，AI完成内容创作</p>
      </div>
      <!-- 主题输入组合框 -->
      <div class="composer-wrap">
        <ComposerInput
          v-model="topic"
          v-model:reference-content="referenceContent"
          :loading="loading"
          :button-text="'进入编辑大纲'"
          @generate="handleGenerate"
          @imagesChange="handleImagesChange"
          style="width: 100%"
        />
      </div>
    </div>
    <ErrorCard
      v-if="error"
      class="home-error"
      :error="error"
      dismissible
      @dismiss="error = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
// 引入组件
import ShowcaseBackground from '../components/home/ShowcaseBackground.vue'
import ComposerInput from '../components/home/ComposerInput.vue'
import ErrorCard from '../components/common/ErrorCard.vue'

const router = useRouter()
const store = useGeneratorStore()

// 状态
const topic = ref('')
// 参考内容（选填）
const referenceContent = ref('')
const loading = ref(false)
const error = ref<AppError | null>(null)
// 上传的图片文件
const uploadedImageFiles = ref<File[]>([])

/**
 * 处理图片变化
 */
function handleImagesChange(images: File[]) {
  uploadedImageFiles.value = images
}

// 主题/参考内容与 store 保持同步：
// 点击输入栏的 × 清空时，必须连 store 记忆一起清空，
// 否则切到其他页面再回来（restoreHomeInputs 从 store 恢复）旧内容又会重新出现
watch(topic, (val) => {
  store.topic = val
})
watch(referenceContent, (val) => {
  store.referenceContent = val
})



/**
 * 进入编辑大纲
 * 不在首页生成大纲，携带主题/参考图直接进入编辑大纲页面，生成大纲在那边进行
 */
function handleGenerate() {
  if (!topic.value.trim()) {
    error.value = normalizeApiError('请先输入主题', '主题为空')
    return
  }

  const imageFiles = uploadedImageFiles.value

  // 保存主题、参考内容与参考图到 store，进入编辑大纲页面
  store.setTopic(topic.value.trim())
  store.referenceContent = referenceContent.value.trim()
  if (imageFiles.length > 0) {
    store.userImages = imageFiles
  } else {
    store.userImages = []
  }
  store.setEntrySource('home')

  // 清空上一次任务的草稿（旧大纲/图片/文案/历史记录ID），但保留本次新输入的主题、参考内容与参考图
  // 必须在这里清理（而不是 OutlineView 的 onMounted）：页面组件被 KeepAlive 缓存后，
  // 再次进入 /outline 不会重新执行 onMounted，旧内容会残留
  store.prepareNewOutline()

  // 保留首页已填内容（主题/参考图预览），退出编辑回到首页时仍能恢复
  router.push('/outline')
}

// 各输入栏内部自带 × 清空按钮（主题/参考内容），参考图片可单张删除，不再需要外部清空按钮
// 记忆恢复：从其他模块/页面刷新回来时，恢复之前填写的主题
// （KeepAlive 下本地状态通常还在，这里兜底恢复更早会话的主题）
onMounted(() => {
  restoreHomeInputs()
})
onActivated(() => {
  restoreHomeInputs()
})

/**
 * 恢复首页已填内容（主题 + 参考内容）
 */
function restoreHomeInputs() {
  if (!topic.value && store.topic) {
    topic.value = store.topic
  }
  if (!referenceContent.value && store.referenceContent) {
    referenceContent.value = store.referenceContent
  }
}
</script>

<style scoped>
.home-container {
  max-width: 1100px;
  padding-top: 10px;
  position: relative;
  z-index: 1;
}
/* Hero Section */
.hero-section {
  text-align: center;
  margin-bottom: 40px;
  padding: 50px 60px;
  animation: fadeIn 0.6s ease-out;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
  backdrop-filter: blur(10px);
}
.hero-content {
  margin-bottom: 36px;
}
/* 首页主标题：颜色与侧边栏「AI 图文创作」品牌渐变一致 */
.hero-content .page-title {
  background: linear-gradient(135deg, #ff2442 0%, #ff5c72 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  letter-spacing: -1px;
}
.page-subtitle {
  font-size: 16px;
  color: var(--text-sub);
  margin-top: 12px;
}
/* 输入+取消按钮容器，加宽输入区域 */
.composer-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  width: 100%;
}
/* 穿透scoped，让子组件输入框占满父容器宽度 */
.composer-wrap :deep(.composer-input) {
  width: 100%;
}
.btn-cancel {
  padding: 8px 20px;
  border: 1px solid #cccccc;
  background: #ffffff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #666666;
  transition: all 0.2s;
}
.btn-cancel:hover {
  background: #f5f5f5;
}

/* 各输入栏内部自带 × 清空按钮（见 ComposerInput），外部清空按钮已移除 */
.home-error {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s ease-out;
}
/* Animations */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes slideUp {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
</style>