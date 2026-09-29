<template>
  <!-- 服务商编辑/添加弹窗 -->
  <!-- @click.self 仅在直接点击遮罩时关闭，避免全选文字拖拽越界误触发关闭 -->
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>{{ isEditing ? '编辑服务商' : '添加服务商' }}</h3>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>

      <div class="modal-body">
        <!-- 名称（自动生成：服务商:模型） -->
        <div class="form-group">
          <label>名称</label>
          <input type="text" class="form-input" :value="autoName" disabled placeholder="自动生成：服务商:模型" />
          <span class="form-hint">名称自动生成，格式：服务商:模型</span>
        </div>

        <!-- 服务商（唯一标识） -->
        <div class="form-group">
          <label>服务商</label>
          <div class="input-wrap">
            <input
              type="text"
              class="form-input"
              v-model="local.name"
              placeholder="例如: deepseek"
              autocomplete="off"
            />
            <button
              v-if="local.name"
              type="button"
              class="input-clear"
              title="清空"
              @click="local.name = ''"
            >×</button>
          </div>
          <span class="form-hint">服务商名称</span>
        </div>

        <!-- 类型选择 -->
        <div class="form-group">
          <label>类型</label>
          <select class="form-select" v-model="local.type">
            <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <!-- API Key -->
        <div class="form-group">
          <label>API Key</label>
          <div class="input-wrap">
            <input
              type="text"
              class="form-input"
              v-model="local.api_key"
              :placeholder="isEditing && local._has_api_key ? local.api_key_masked : '输入 API Key'"
              autocomplete="off"
            />
            <button
              v-if="local.api_key"
              type="button"
              class="input-clear"
              title="清空"
              @click="local.api_key = ''"
            >×</button>
          </div>
          <span class="form-hint" v-if="isEditing && local._has_api_key">
            已配置 API Key，留空表示不修改
          </span>
        </div>

        <!-- Base URL -->
        <div class="form-group" v-if="showBaseUrl">
          <label>Base URL</label>
          <div class="input-wrap">
            <input
              type="text"
              class="form-input"
              v-model="local.base_url"
              :placeholder="baseUrlPlaceholder"
              autocomplete="off"
            />
            <button
              v-if="local.base_url"
              type="button"
              class="input-clear"
              title="清空"
              @click="local.base_url = ''"
            >×</button>
          </div>
          <span class="form-hint" v-if="previewUrl">
            预览: {{ previewUrl }}
          </span>
        </div>

        <!-- 模型 -->
        <div class="form-group">
          <label>模型</label>
          <div class="input-wrap">
            <input
              type="text"
              class="form-input"
              v-model="local.model"
              :placeholder="modelPlaceholder"
              autocomplete="off"
            />
            <button
              v-if="local.model"
              type="button"
              class="input-clear"
              title="清空"
              @click="local.model = ''"
            >×</button>
          </div>
        </div>

        <div class="form-group" v-if="showEndpointType">
          <label for="text-api-protocol">API 协议</label>
          <select
            id="text-api-protocol"
            class="form-select"
            v-model="local.api_protocol"
            @change="changeProtocol"
          >
            <option value="chat_completions">Chat Completions</option>
            <option value="responses">Responses</option>
          </select>
        </div>

        <!-- 端点路径（仅 OpenAI 兼容接口） -->
        <div class="form-group" v-if="showEndpointType">
          <label for="text-api-endpoint">API 端点路径{{ customEndpoint ? '（自定义路径）' : '' }}</label>
          <div class="input-wrap">
            <input
              type="text"
              id="text-api-endpoint"
              class="form-input"
              v-model="local.endpoint_type"
              :placeholder="defaultEndpoint"
              autocomplete="off"
            />
            <button
              v-if="local.endpoint_type"
              type="button"
              class="input-clear"
              title="清空"
              @click="local.endpoint_type = ''"
            >×</button>
          </div>
          <span class="form-hint">
            默认端点：{{ defaultEndpoint }}
          </span>
        </div>

        <!-- 备注 -->
        <div class="form-group">
          <label>备注</label>
          <div class="textarea-wrap">
            <textarea
              class="form-input form-textarea"
              v-model="local.remark"
              rows="3"
              placeholder="记录该模型的强项、优势、注意事项等，保存后可在列表预览"
            ></textarea>
            <button
              v-if="local.remark"
              type="button"
              class="input-clear textarea-clear"
              title="清空"
              @click="local.remark = ''"
            >×</button>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn" @click="$emit('close')">取消</button>
        <button
          class="btn btn-secondary"
          @click="commit(); $emit('test')"
          :disabled="testing || (!local.api_key && !isEditing)"
        >
          <span v-if="testing" class="spinner-small"></span>
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
        <button class="btn btn-primary" @click="commit(); $emit('save')">
          {{ isEditing ? '保存' : '添加' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TextProviderForm } from '../../composables/useProviderForm'
import { defaultTextEndpoint, endpointForTextProtocol, isCustomTextEndpoint } from '../../utils/textProtocol'

/**
 * 服务商编辑/添加弹窗组件
 *
 * 功能：
 * - 添加新服务商
 * - 编辑现有服务商
 * - 测试连接
 * - 备注填写与预览
 */

// 定义类型选项
interface TypeOption {
  value: string
  label: string
}

// 定义 Props
const props = defineProps<{
  visible: boolean
  isEditing: boolean
  formData: TextProviderForm
  testing: boolean
  typeOptions: TypeOption[]
  providerCategory: 'text' | 'image'
}>()

// 定义 Emits
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save'): void
  (e: 'test'): void
  (e: 'update:formData', data: TextProviderForm): void
}>()

// 本地编辑副本：表单直接 v-model 到本地，避免受控输入在快速操作（如全选替换）时的异常
const local = ref<TextProviderForm>({ ...props.formData })
const defaultEndpoint = computed(() => defaultTextEndpoint(local.value.api_protocol))
const customEndpoint = computed(() => isCustomTextEndpoint(local.value.endpoint_type))

function changeProtocol() {
  local.value.endpoint_type = endpointForTextProtocol(local.value.endpoint_type, local.value.api_protocol)
}

// 父级传入的数据变化时同步
watch(
  () => props.formData,
  (v) => {
    local.value = { ...(v as TextProviderForm) }
  },
  { deep: true }
)

// 弹窗打开时重新同步（防止上次未保存的编辑残留）
watch(
  () => props.visible,
  (v) => {
    if (v) local.value = { ...props.formData }
  }
)

// 名称自动生成：服务商:模型（模型为空时退化为服务商）
const autoName = computed(() => {
  const s = local.value.name.trim()
  const m = local.value.model.trim()
  return s ? (m ? `${s}:${m}` : s) : ''
})

// 把本地编辑同步回父级（保存/测试前调用）
function commit() {
  emit('update:formData', { ...local.value, display_name: autoName.value })
}

// 是否显示 Base URL
const showBaseUrl = computed(() => {
  return ['openai_compatible', 'google_gemini', 'google_genai', 'image_api'].includes(local.value.type)
})

// 是否显示端点类型
const showEndpointType = computed(() => {
  return local.value.type === 'openai_compatible'
})

// Base URL 占位符
const baseUrlPlaceholder = computed(() => {
  switch (local.value.type) {
    case 'google_gemini':
    case 'google_genai':
      return '例如: https://generativelanguage.googleapis.com'
    default:
      return '例如: https://api.openai.com'
  }
})

// 模型占位符
const modelPlaceholder = computed(() => {
  switch (local.value.type) {
    case 'google_gemini':
      return '例如: gemini-2.0-flash-exp'
    case 'google_genai':
      return '例如: imagen-3.0-generate-002'
    case 'image_api':
      return '例如: flux-pro'
    default:
      return '例如: gpt-4o'
  }
})

// 预览 URL
const previewUrl = computed(() => {
  if (!local.value.base_url) return ''

  const baseUrl = local.value.base_url.replace(/\/$/, '').replace(/\/v1$/, '')

  switch (local.value.type) {
    case 'openai_compatible': {
      // 使用用户自定义的端点路径
      let endpoint = local.value.endpoint_type || defaultEndpoint.value
      if (!endpoint.startsWith('/')) {
        endpoint = '/' + endpoint
      }
      return `${baseUrl}${endpoint}`
    }
    case 'google_gemini':
    case 'google_genai':
      return `${baseUrl}/v1beta/models/${local.value.model || '{model}'}:generateContent`
    case 'image_api':
      return `${baseUrl}/v1/images/generations`
    default:
      return ''
  }
})
</script>

<style scoped>
/* 模态框内容 */
.modal-content {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

/* 头部 */
.modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color, #eee);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  color: #333;
}

/* 主体 */
.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

/* 表单组 */
.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-main, #1a1a1a);
  margin-bottom: 8px;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #eee);
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: var(--primary, #ff2442);
  box-shadow: 0 0 0 3px rgba(255, 36, 66, 0.1);
}

.form-textarea {
  resize: vertical;
  min-height: 64px;
  font-family: inherit;
  line-height: 1.6;
}

/* 输入框 + 一键清空按钮 */
.input-wrap {
  position: relative;
}

.input-wrap .form-input {
  box-sizing: border-box;
  padding-right: 34px;
}

.input-clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.2s, color 0.2s;
}

.input-clear:hover {
  background: #fecaca;
  color: #dc2626;
}

.textarea-wrap {
  position: relative;
}

.textarea-clear {
  top: 8px;
  transform: none;
  z-index: 1;
}

.form-select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #eee);
  border-radius: 8px;
  font-size: 14px;
  background: white;
  cursor: pointer;
}

.form-hint {
  display: block;
  font-size: 12px;
  color: var(--text-sub, #666);
  margin-top: 6px;
}

/* 底部 */
.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--border-color, #eee);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 按钮样式 */
.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--border-color, #eee);
  background: white;
  color: var(--text-main, #1a1a1a);
  transition: all 0.2s;
}

.btn:hover {
  background: #f5f5f5;
}

.btn-primary {
  background: var(--primary, #ff2442);
  border-color: var(--primary, #ff2442);
  color: white;
}

.btn-primary:hover {
  background: var(--primary-hover, #e61e3a);
}

.btn-secondary {
  background: #f0f0f0;
  border-color: #ddd;
  color: #333;
}

.btn-secondary:hover {
  background: #e5e5e5;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 加载动画 */
.spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 6px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
