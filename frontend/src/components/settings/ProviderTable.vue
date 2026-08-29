<template>
  <!-- 服务商列表表格 -->
  <div class="provider-table">
    <div class="table-header">
      <div class="col-status">状态</div>
      <div class="col-name">名称</div>
      <div class="col-provider">服务商</div>
      <div class="col-model">模型</div>
      <div class="col-apikey">API Key</div>
      <div class="col-actions">操作</div>
    </div>
    <div
      v-for="(provider, name) in providers"
      :key="name"
      class="table-row-wrap"
      :class="{ active: activeProvider === name }"
    >
      <div class="table-row">
        <div class="col-status">
          <button
            class="toggle-switch"
            :class="{ on: provider.enabled !== false }"
            @click="$emit('activate', name)"
            :title="provider.enabled !== false ? '点击停用（创作中心不可选）' : '点击激活（创作中心可选）'"
          >
            <span class="toggle-knob"></span>
          </button>
        </div>
        <div class="col-name">
          <span class="provider-name">{{ provider.display_name || name }}</span>
        </div>
        <div class="col-provider">
          <span class="provider-code">{{ name }}</span>
        </div>
        <div class="col-model">
          <span class="model-name">{{ provider.model }}</span>
        </div>
        <div class="col-apikey">
          <span class="apikey-masked" :class="{ empty: !provider.api_key_masked }" :title="provider.api_key_masked || ''">
            {{ provider.api_key_masked ? formatMasked(provider.api_key_masked) : '未配置' }}
          </span>
        </div>
        <div class="col-actions">
          <button class="btn-icon" @click="$emit('test', name, provider)" title="测试连接">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
            </svg>
          </button>
          <button class="btn-icon" @click="$emit('edit', name, provider)" title="编辑">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
          </button>
          <button
            v-if="canConfigureUsers"
            class="btn-icon users"
            @click="$emit('users', name, provider)"
            title="配置用户"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
          </button>
          <button
            class="btn-icon danger"
            @click="$emit('delete', name)"
            title="删除"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      </div>
      <!-- 备注预览 -->
      <div v-if="provider.remark" class="row-remark">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
        <span class="remark-text" :title="provider.remark">{{ provider.remark }}</span>
      </div>
      <!-- 管理员：查看该服务商的可用用户名单 -->
      <div v-if="canConfigureUsers" class="row-users">
        <span class="allowed-label">可用用户：</span>
        <span v-if="!provider.allowed_users || provider.allowed_users.length === 0" class="allowed-empty">未共享（仅管理员）</span>
        <span v-for="u in provider.allowed_users" :key="u" class="allowed-chip">{{ u }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 服务商列表表格组件
 *
 * 功能：
 * - 展示服务商列表
 * - 激活/编辑/删除/测试操作
 * - 管理员可配置每个服务商可使用的用户名单
 */

// 服务商类型定义
interface ProviderItem {
  type: string
  model: string
  display_name?: string
  enabled?: boolean
  base_url?: string
  api_key?: string
  api_key_masked?: string
  allowed_users?: string[]
  remark?: string
}

// 定义 Props
const props = defineProps<{
  providers: Record<string, ProviderItem>
  activeProvider: string
  canConfigureUsers?: boolean
}>()

// 定义 Emits
defineEmits<{
  (e: 'activate', name: string): void
  (e: 'edit', name: string, provider: ProviderItem): void
  (e: 'delete', name: string): void
  (e: 'test', name: string, provider: ProviderItem): void
  (e: 'users', name: string, provider: ProviderItem): void
}>()

// 脱敏精简显示：前 4 位 + 6 个星号 + 末 4 位，够短可放入一行
function formatMasked(key: string): string {
  const k = (key || '').trim()
  if (!k) return ''
  if (k.length <= 12) return k
  const head = k.slice(0, 4)
  const tail = k.slice(-4)
  return `${head}${'*'.repeat(6)}${tail}`
}
</script>

<style scoped>
/* 表格容器 */
.provider-table {
  border: 1px solid var(--border-color, #eee);
  border-radius: 8px;
  overflow: hidden;
}

/* 表头 */
.table-header {
  display: grid;
  grid-template-columns: 100px 1.3fr 0.6fr 1fr 0.45fr 120px;
  gap: 12px;
  padding: 12px 16px;
  background: #f9fafb;
  border-bottom: 1px solid var(--border-color, #eee);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sub, #666);
  text-transform: uppercase;
}

/* 表格行（外层：含边框/悬停/激活态，以及可选的用户名单条） */
.table-row-wrap {
  border-bottom: 1px solid var(--border-color, #eee);
  transition: background-color 0.2s;
}

.table-row-wrap:last-child {
  border-bottom: none;
}

.table-row-wrap:hover {
  background: #f9fafb;
}

.table-row-wrap.active {
  background: rgba(255, 36, 66, 0.02);
}

/* 表格行（内层：网格布局） */
.table-row {
  display: grid;
  grid-template-columns: 100px 1.3fr 0.6fr 1fr 0.45fr 120px;
  gap: 12px;
  padding: 14px 16px;
  align-items: center;
}

/* 状态列：开关 + 文字水平排列 */
.col-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 管理员：服务商可用用户名单 */
.row-users {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 0 16px 10px 16px;
  font-size: 12px;
}

/* 备注预览 */
.row-remark {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 0 16px 8px 16px;
  font-size: 12px;
  color: #8a6d3b;
}

.row-remark svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.remark-text {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  white-space: pre-line;
  word-break: break-word;
}

.allowed-label {
  color: #666;
}

.allowed-chip {
  padding: 2px 10px;
  border-radius: 12px;
  background: #e8f5e9;
  color: #2e7d32;
  font-weight: 600;
}

.allowed-empty {
  color: #999;
}

/* 激活开关：灰色关 / 绿色开 */
.toggle-switch {
  width: 40px;
  height: 22px;
  border-radius: 11px;
  background: #d1d5db;
  border: none;
  cursor: pointer;
  position: relative;
  padding: 0;
  transition: background 0.2s;
  flex-shrink: 0;
}

.toggle-switch:hover {
  background: #b8bdc4;
}

.toggle-switch.on {
  background: #22c55e;
}

.toggle-switch.on:hover {
  background: #16a34a;
}

.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.toggle-switch.on .toggle-knob {
  transform: translateX(18px);
}

/* 名称（自动生成：服务商:模型），与其他列字体、大小一致 */
.provider-name {
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: var(--text-sub, #666);
  word-break: break-all;
}

/* 服务商（唯一标识） */
.provider-code {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  color: var(--text-sub, #666);
  word-break: break-all;
}

/* 模型名称 */
.model-name {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  color: var(--text-sub, #666);
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
}

/* API Key 显示 */
.apikey-masked {
  display: block;
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.apikey-masked.empty {
  color: #f59e0b;
}

/* 操作列 */
.col-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

/* 图标按钮 */
.btn-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #eee);
  background: white;
  color: var(--text-sub, #666);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.btn-icon:hover {
  border-color: var(--primary, #ff2442);
  color: var(--primary, #ff2442);
  background: rgba(255, 36, 66, 0.05);
}

.btn-icon.danger:hover {
  border-color: #ef4444;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.05);
}

.btn-icon.users:hover {
  border-color: #22c55e;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.08);
}

/* 响应式 */
@media (max-width: 768px) {
  .table-header,
  .table-row {
    grid-template-columns: 70px 1fr 100px;
  }

  .col-model,
  .col-apikey {
    display: none;
  }
}
</style>
