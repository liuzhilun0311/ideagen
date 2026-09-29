<template>
  <div class="container">
    <div class="page-header">
      <h1 class="page-title">模型设置</h1>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p>加载配置中...</p>
    </div>

    <div v-else class="settings-container">
      <ErrorCard
        v-if="feedback?.type === 'error'"
        :error="feedback.error"
        dismissible
        @dismiss="clearFeedback"
        style="margin-bottom: 16px;"
      />

      <div
        v-else-if="feedback?.type === 'success' || feedback?.type === 'warning'"
        class="success-card"
        :class="{ 'connection-warning': feedback.type === 'warning' }"
        role="status"
        aria-live="polite"
      >
        <span>{{ feedback.type === 'warning' ? '尚未验证生成：' : '' }}{{ feedback.message }}</span>
        <button type="button" @click="clearFeedback" aria-label="关闭提示">×</button>
      </div>

      <nav class="model-tabs" aria-label="模型类型">
        <button type="button" :class="{ active: activeModelType === 'text' }" :aria-pressed="activeModelType === 'text'" @click="activeModelType = 'text'">
          文本生成 <span>{{ Object.keys(textConfig.providers || {}).length }}</span>
        </button>
        <button type="button" :class="{ active: activeModelType === 'image' }" :aria-pressed="activeModelType === 'image'" @click="activeModelType = 'image'">
          图片生成 <span>{{ Object.keys(imageConfig.providers || {}).length }}</span>
        </button>
      </nav>

      <!-- 文本生成配置 -->
      <div v-if="activeModelType === 'text'" class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">文本生成配置</h2>
          </div>
          <button class="btn btn-primary btn-small" :disabled="textBusy" @click="openAddTextModal">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            添加
          </button>
        </div>

        <!-- 服务商列表表格 -->
        <p v-if="textOrder.error.value" role="alert">{{ textOrder.error.value }}</p>
        <ProviderTable
          :order="textOrder.order.value"
          :busy="textBusy"
          :providers="textConfig.providers"
          :activeProvider="textConfig.active_provider"
          :canConfigureUsers="isAdmin"
          @activate="activateTextProvider"
          @edit="openEditTextModal"
          @delete="deleteTextProvider"
          @test="testTextProviderInList"
          @users="(name, provider) => openProviderUsersModal('text', name, provider)"
          @copy="name => copyProvider('text', name)"
          @move="(source, target) => moveProvider('text', source, target)"
        />
      </div>

      <!-- 图片生成配置 -->
      <div v-else class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">图片生成配置</h2>
          </div>
          <button class="btn btn-primary btn-small" :disabled="imageBusy" @click="openAddImageModal">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            添加
          </button>
        </div>

        <!-- 服务商列表表格 -->
        <p v-if="imageOrder.error.value" role="alert">{{ imageOrder.error.value }}</p>
        <ProviderTable
          :order="imageOrder.order.value"
          :busy="imageBusy"
          :providers="imageConfig.providers"
          :activeProvider="imageConfig.active_provider"
          :canConfigureUsers="isAdmin"
          @activate="activateImageProvider"
          @edit="openEditImageModal"
          @delete="deleteImageProvider"
          @test="testImageProviderInList"
          @users="(name, provider) => openProviderUsersModal('image', name, provider)"
          @copy="name => copyProvider('image', name)"
          @move="(source, target) => moveProvider('image', source, target)"
        />
      </div>
    </div>

    <!-- 文本服务商弹窗 -->
    <ProviderModal
      :visible="showTextModal"
      :isEditing="!!editingTextProvider"
      :formData="textForm"
      :testing="testingText"
      :typeOptions="textTypeOptions"
      providerCategory="text"
      @close="closeTextModal"
      @save="saveTextProvider"
      @test="testTextConnection"
      @update:formData="updateTextForm"
    />

    <!-- 图片服务商弹窗 -->
    <ImageProviderModal
      :visible="showImageModal"
      :isEditing="!!editingImageProvider"
      :formData="imageForm"
      :testing="testingImage"
      :typeOptions="imageTypeOptions"
      @close="closeImageModal"
      @save="saveImageProvider"
      @test="testImageConnection"
      @update:formData="updateImageForm"
    />

    <!-- 配置服务商可用用户弹窗（仅管理员） -->
    <div v-if="providerUsersModal" class="modal-overlay" @click.self="providerUsersModal = false">
      <div class="modal card">
        <div class="modal-head">
          <h3>配置可用用户 - {{ providerUsersName }}</h3>
          <button class="icon-btn" title="关闭" @click="providerUsersModal = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="modal-sub">
            勾选后，仅这些用户可见并使用该服务商；不勾选任何用户则仅管理员可见。拥有者已默认勾选、始终可见。
          </p>
          <div class="user-check-list">
            <label v-for="u in providerUsersList" :key="u.id" class="user-check">
              <input type="checkbox" :value="u.username" v-model="providerUsersSelected" :disabled="u.username === providerUsersOwner" />
              {{ u.username }}
              <span v-if="u.username === providerUsersOwner" class="owner-flag">（拥有者，始终可见）</span>
              <span v-else-if="u.is_admin" class="admin-flag">（管理员）</span>
            </label>
            <div v-if="providerUsersList.length === 0" class="empty-users-tip">暂无可选用户</div>
          </div>
          <div class="editor-actions">
            <button class="btn btn-primary btn-small" :disabled="savingProviderUsers" @click="saveProviderUsers">
              {{ savingProviderUsers ? '保存中...' : '保存' }}
            </button>
            <button class="btn btn-ghost btn-small" @click="providerUsersModal = false">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onDeactivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useLibraryOrder } from '../composables/useLibraryOrder'
import ProviderTable from '../components/settings/ProviderTable.vue'
import ProviderModal from '../components/settings/ProviderModal.vue'
import ImageProviderModal from '../components/settings/ImageProviderModal.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import { setProviderUsers } from '../api'
import { listUsers } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import { normalizeApiError } from '../utils/errors'
import {
  useProviderForm,
  textTypeOptions,
  imageTypeOptions
} from '../composables/useProviderForm'

/**
 * 系统设置页面
 *
 * 功能：
 * - 管理文本生成服务商配置
 * - 管理图片生成服务商配置
 * - 测试 API 连接
 */

// 使用 composable 管理表单状态和逻辑
const {
  // 状态
  loading,
  testingText,
  testingImage,
  feedback,

  // 配置数据
  textConfig,
  imageConfig,

  // 文本服务商弹窗
  showTextModal,
  editingTextProvider,
  textForm,

  // 图片服务商弹窗
  showImageModal,
  editingImageProvider,
  imageForm,

  // 方法
  loadConfig,
  invalidateConfigLoad,
  clearFeedback,

  // 文本服务商方法
  activateTextProvider,
  openAddTextModal,
  openEditTextModal,
  closeTextModal,
  saveTextProvider,
  deleteTextProvider,
  testTextConnection,
  testTextProviderInList,
  updateTextForm,

  // 图片服务商方法
  activateImageProvider,
  openAddImageModal,
  openEditImageModal,
  closeImageModal,
  saveImageProvider,
  deleteImageProvider,
  testImageConnection,
  testImageProviderInList,
  updateImageForm
} = useProviderForm()

// 是否管理员（"用户配置"按钮仅管理员可见可操作）
const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

const textIds = computed(() => Object.keys(textConfig.value.providers))
const imageIds = computed(() => Object.keys(imageConfig.value.providers))
const activeModelType = ref<'text' | 'image'>('text')
const textOrder = useLibraryOrder('models', ref('text'), textIds)
const imageOrder = useLibraryOrder('models', ref('image'), imageIds)
const copying = ref({ text: false, image: false })
const contextActive = ref(true)
let contextEpoch = 0
const textBusy = computed(() => !contextActive.value || copying.value.text || textOrder.busy.value)
const imageBusy = computed(() => !contextActive.value || copying.value.image || imageOrder.busy.value)

function invalidateContext() {
  ++contextEpoch
  invalidateConfigLoad()
  contextActive.value = false
  copying.value = { text: false, image: false }
  textOrder.invalidate()
  imageOrder.invalidate()
  closeTextModal()
  closeImageModal()
  providerUsersModal.value = false
  textConfig.value = { active_provider: '', providers: {} }
  imageConfig.value = { active_provider: '', providers: {} }
  clearFeedback()
}

watch(() => [authStore.token, authStore.user?.id, authStore.sessionRevision], invalidateContext, { flush: 'sync' })
// The form loader writes its refs internally; discard late config reads after navigation/session changes.
watch([textConfig, imageConfig, feedback], () => {
  if (contextActive.value) return
  if (Object.keys(textConfig.value.providers).length) textConfig.value = { active_provider: '', providers: {} }
  if (Object.keys(imageConfig.value.providers).length) imageConfig.value = { active_provider: '', providers: {} }
  if (feedback.value) clearFeedback()
}, { flush: 'sync' })
onBeforeRouteLeave(invalidateContext)
onDeactivated(invalidateContext)
onBeforeUnmount(invalidateContext)
onActivated(() => {
  if (!contextActive.value) {
    contextActive.value = true
    void loadConfig()
  }
})

async function moveProvider(kind: 'text' | 'image', source: string, target: string) {
  if ((kind === 'text' ? textBusy : imageBusy).value) return
  await (kind === 'text' ? textOrder : imageOrder).move(source, target)
}

async function copyProvider(kind: 'text' | 'image', source: string) {
  const library = kind === 'text' ? textOrder : imageOrder
  const config = kind === 'text' ? textConfig : imageConfig
  if ((kind === 'text' ? textBusy : imageBusy).value || !Object.prototype.hasOwnProperty.call(config.value.providers, source)) return
  const epoch = contextEpoch
  const current = () => contextActive.value && epoch === contextEpoch
  copying.value[kind] = true
  clearFeedback()
  let created: { id: string; name: string } | null = null
  try {
    created = await library.copy(source)
    if (!current() || !created) return
    const loaded = await loadConfig()
    if (!current()) return
    const provider = config.value.providers[created.id]
    if (!loaded || !provider) throw new Error('刷新列表失败')
    if (kind === 'text') openEditTextModal(created.id, provider)
    else openEditImageModal(created.id, provider)
  } catch (error) {
    if (!current()) return
    feedback.value = {
      type: 'error',
      error: normalizeApiError(
        created ? '副本已创建，但刷新列表失败。请刷新页面查看副本，不要重复复制。' : error,
        created ? '副本已创建，刷新失败' : '复制失败',
      ),
    }
  } finally {
    if (current()) copying.value[kind] = false
  }
}

// ==================== 管理员：配置服务商可用用户 ====================

const providerUsersModal = ref(false)
const providerUsersKind = ref<'text' | 'image'>('text')
const providerUsersName = ref('')
const providerUsersOwner = ref('')
const providerUsersSelected = ref<string[]>([])
const providerUsersList = ref<{ id: string; username: string; is_admin: boolean }[]>([])
const savingProviderUsers = ref(false)

async function openProviderUsersModal(kind: 'text' | 'image', name: string, provider: any) {
  providerUsersKind.value = kind
  providerUsersName.value = name
  // 拥有者（创建者 = 当前管理员）默认打勾、始终可见
  providerUsersOwner.value = authStore.username || ''
  const selected = new Set<string>([...(provider.allowed_users || [])])
  if (providerUsersOwner.value) selected.add(providerUsersOwner.value)
  providerUsersSelected.value = [...selected]
  providerUsersModal.value = true
  if (providerUsersList.value.length === 0) {
    try {
      const res = await listUsers()
      if (res.success && res.users) {
        providerUsersList.value = res.users
      }
    } catch {
      // 用户列表加载失败时保持空，弹窗内提示暂无可选用户
    }
  }
}

async function saveProviderUsers() {
  savingProviderUsers.value = true
  clearFeedback()
  try {
    const res = await setProviderUsers(
      providerUsersKind.value,
      providerUsersName.value,
      providerUsersSelected.value
    )
    if (res?.success) {
      providerUsersModal.value = false
      await loadConfig()
      feedback.value = { type: 'success', message: '已更新使用名单' }
    } else {
      feedback.value = {
        type: 'error',
        error: normalizeApiError(res?.error || res?.error_message || '保存失败', '保存失败')
      }
    }
  } catch (e) {
    feedback.value = { type: 'error', error: normalizeApiError(e, '保存失败') }
  } finally {
    savingProviderUsers.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.model-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  padding: 4px;
  background: #eef3fb;
  border-radius: 10px;
  width: fit-content;
}
.model-tabs button {
  border: 0;
  background: transparent;
  color: #52627a;
  padding: 10px 18px;
  border-radius: 7px;
  cursor: pointer;
  font-size: 14px;
}
.model-tabs button.active {
  background: #fff;
  color: #285de8;
  box-shadow: 0 1px 4px rgba(24, 55, 110, .12);
  font-weight: 600;
}
.model-tabs span {
  display: inline-block;
  min-width: 20px;
  margin-left: 5px;
  color: #7d8da6;
  font-size: 12px;
}
@media (max-width: 600px) {
  .model-tabs { width: 100%; }
  .model-tabs button { flex: 1; padding: 10px 8px; }
}
.success-card.connection-warning {
  background: #fff8dd;
  border-color: #dbc26b;
  color: #705619;
}
.settings-container {
  max-width: 1200px;
  margin: 0 auto;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #1a1a1a;
}

.section-desc {
  font-size: 14px;
  color: #666;
  margin: 0;
}

/* 加载状态 */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #666;
}

/* 配置用户弹窗 */
.modal {
  width: 420px;
  max-width: 92vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}
.modal-head h3 {
  margin: 0;
  font-size: 16px;
}
.icon-btn {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-sub);
}
.modal-body {
  padding: 20px;
  overflow: auto;
}
.modal-sub {
  font-size: 13px;
  color: #555;
  margin: 0 0 14px;
}
.user-check-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.user-check {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}
.user-check:hover {
  background: #f7f9fc;
}
.user-check input {
  margin: 0;
}
.admin-flag {
  font-size: 12px;
  color: #999;
}
.owner-flag {
  font-size: 12px;
  color: #2e7d32;
  font-weight: 600;
}
.empty-users-tip {
  text-align: center;
  padding: 16px;
  color: #999;
  font-size: 13px;
}
.editor-actions {
  display: flex;
  gap: 10px;
}
</style>
