import { ref } from 'vue'
import { getConfig, updateConfig, testConnection, saveProvider, type Config } from '../api'
import { normalizeApiError, type AppError } from '../utils/errors'
import { defaultTextEndpoint, resolveTextProtocol, type TextApiProtocol } from '../utils/textProtocol'

/**
 * 服务商表单管理 Composable
 *
 * 提供服务商配置的完整管理功能：
 * - 加载/保存配置
 * - 添加/编辑/删除服务商
 * - 测试连接
 * - 激活服务商
 */

// 服务商数据类型
export interface Provider {
  type: string
  model: string
  display_name?: string
  base_url?: string
  api_key?: string
  api_key_masked?: string
  endpoint_type?: string
  api_protocol?: TextApiProtocol
  high_concurrency?: boolean
  short_prompt?: boolean
  [key: string]: any
}

// 服务商配置类型
export interface ProviderConfig {
  active_provider: string
  providers: Record<string, Provider>
}

// 文本服务商表单类型
export interface TextProviderForm {
  name: string
  display_name: string
  type: string
  api_key: string
  api_key_masked: string
  base_url: string
  model: string
  endpoint_type: string
  api_protocol: TextApiProtocol
  remark: string
  _has_api_key: boolean
}

// 图片服务商表单类型
export interface ImageProviderForm {
  name: string
  display_name: string
  type: string
  api_key: string
  api_key_masked: string
  base_url: string
  model: string
  high_concurrency: boolean
  short_prompt: boolean
  endpoint_type: string
  remark: string
  _has_api_key: boolean
}

// 文本服务商类型选项
export const textTypeOptions = [
  { value: 'google_gemini', label: 'Google Gemini' },
  { value: 'openai_compatible', label: 'OpenAI 兼容接口' }
]

// 图片服务商类型选项
export const imageTypeOptions = [
  { value: 'google_genai', label: 'Google GenAI' },
  { value: 'image_api', label: 'OpenAI 兼容接口' }
]

/**
 * 服务商表单管理 Hook
 */
export function useProviderForm() {
  // 加载状态
  const loading = ref(true)
  const saving = ref(false)
  const testingText = ref(false)
  const testingImage = ref(false)
  const feedback = ref<{
    type: 'success' | 'warning' | 'error'
    message?: string
    error?: AppError
  } | null>(null)

  // 配置数据
  const textConfig = ref<ProviderConfig>({
    active_provider: '',
    providers: {}
  })

  const imageConfig = ref<ProviderConfig>({
    active_provider: '',
    providers: {}
  })

  // 文本服务商弹窗状态
  const showTextModal = ref(false)
  const editingTextProvider = ref<string | null>(null)
  const textForm = ref<TextProviderForm>(createEmptyTextForm())

  // 图片服务商弹窗状态
  const showImageModal = ref(false)
  const editingImageProvider = ref<string | null>(null)
  const imageForm = ref<ImageProviderForm>(createEmptyImageForm())

  /**
   * 创建空的文本服务商表单
   */
  function createEmptyTextForm(): TextProviderForm {
    return {
      name: '',
      display_name: '',
      type: 'openai_compatible',
      api_key: '',
      api_key_masked: '',
      base_url: '',
      model: '',
      endpoint_type: '/v1/chat/completions',
      api_protocol: 'chat_completions',
      remark: '',
      _has_api_key: false
    }
  }

  /**
   * 创建空的图片服务商表单
   */
  function createEmptyImageForm(): ImageProviderForm {
    return {
      name: '',
      display_name: '',
      type: 'image_api',
      api_key: '',
      api_key_masked: '',
      base_url: '',
      model: '',
      high_concurrency: false,
      short_prompt: false,
      endpoint_type: '/v1/images/generations',
      remark: '',
      _has_api_key: false
    }
  }

  /**
   * 加载配置
   */
  let configLoadRevision = 0
  function invalidateConfigLoad() {
    ++configLoadRevision
    loading.value = false
  }
  async function loadConfig() {
    const request = ++configLoadRevision
    loading.value = true
    try {
      const result = await getConfig()
      if (request !== configLoadRevision) return false
      if (result.success && result.config) {
        textConfig.value = {
          active_provider: result.config.text_generation.active_provider,
          providers: Object.fromEntries(
            Object.entries(result.config.text_generation.providers).map(([name, provider]) => [
              name,
              provider.type === 'openai_compatible'
                ? { ...provider, api_protocol: resolveTextProtocol(provider) }
                : provider
            ])
          )
        }
        imageConfig.value = result.config.image_generation
        return true
      } else {
        setError(result.error || result.error_message || '加载配置失败', '加载配置失败')
      }
    } catch (e) {
      if (request === configLoadRevision) setError(e, '加载配置失败')
    } finally {
      if (request === configLoadRevision) loading.value = false
    }
    return false
  }

  /**
   * 自动保存配置
   */
  async function autoSaveConfig() {
    try {
      const config: Partial<Config> = {
        text_generation: {
          active_provider: textConfig.value.active_provider,
          providers: textConfig.value.providers
        },
        image_generation: imageConfig.value
      }

      const result = await updateConfig(config)
      if (result.success) {
        // 重新加载配置以获取最新的脱敏 API Key
        await loadConfig()
        setSuccess(result.message || '配置已保存')
      }
    } catch (e) {
      console.error('自动保存失败:', e)
      setError(e, '保存配置失败')
    }
  }

  function setSuccess(message: string) {
    feedback.value = { type: 'success', message }
  }

  function setConnectionFeedback(result: { message?: string; warning?: boolean }, fallback: string) {
    feedback.value = {
      type: result.warning ? 'warning' : 'success',
      message: result.message || fallback,
    }
  }

  function setError(error: unknown, fallbackTitle = '操作失败') {
    feedback.value = {
      type: 'error',
      error: normalizeApiError(error, fallbackTitle)
    }
  }

  function clearFeedback() {
    feedback.value = null
  }

  // ==================== 文本服务商操作 ====================

  /**
   * 切换文本服务商启用状态（多选：绿色开=创作中心可选，灰色关=不可选）
   * 同时维护默认模型：开启时若当前无默认则设为默认；关闭默认时改选其他已启用
   */
  async function activateTextProvider(name: string) {
    const providers = textConfig.value.providers
    const cur = providers[name] || {}
    const nowEnabled = cur.enabled === false ? true : false
    providers[name] = { ...cur, enabled: nowEnabled }

    if (nowEnabled) {
      const curActive = textConfig.value.active_provider
      if (!curActive || (providers[curActive] && providers[curActive].enabled === false)) {
        textConfig.value.active_provider = name
      }
    } else if (textConfig.value.active_provider === name) {
      const first = Object.keys(providers).find(k => k !== name && providers[k]?.enabled !== false)
      textConfig.value.active_provider = first || ''
    }
    await autoSaveConfig()
  }

  /**
   * 打开添加文本服务商弹窗
   */
  function openAddTextModal() {
    editingTextProvider.value = null
    textForm.value = createEmptyTextForm()
    showTextModal.value = true
  }

  /**
   * 打开编辑文本服务商弹窗
   */
  function openEditTextModal(name: string, provider: Provider) {
    editingTextProvider.value = name
    textForm.value = {
      name: provider.provider_label || name,
      display_name: provider.display_name || '',
      type: provider.type || 'openai_compatible',
      api_key: '',
      api_key_masked: provider.api_key_masked || '',
      base_url: provider.base_url || '',
      model: provider.model || '',
      endpoint_type: provider.endpoint_type || defaultTextEndpoint(resolveTextProtocol(provider)),
      api_protocol: resolveTextProtocol(provider),
      remark: provider.remark || '',
      _has_api_key: !!provider.api_key_masked
    }
    showTextModal.value = true
  }

  /**
   * 关闭文本服务商弹窗
   */
  function closeTextModal() {
    showTextModal.value = false
    editingTextProvider.value = null
  }

  /**
   * 保存文本服务商（只保存这一个，不影响其他服务商）
   */
  async function saveTextProvider() {
    if (saving.value) return
    const originalName = editingTextProvider.value
    const name = (originalName || textForm.value.name).trim()

    if (!name || !textForm.value.name.trim()) {
      setError('请填写服务商', '配置不完整')
      return
    }

    // 名称由弹窗自动生成（服务商:模型），此处以防遗漏兜底计算
    const modelT = textForm.value.model.trim()
    const label = textForm.value.name.trim()
    const displayName = modelT ? `${label}:${modelT}` : label

    // 名称（display_name）在本类（文本）中不能重复；旧配置无 display_name 时以其标识兜底
    const dup = Object.entries(textConfig.value.providers).find(
      ([k, p]) => k !== originalName && (p.display_name || k) === displayName
    )
    if (dup) {
      setError(`名称 "${displayName}" 已存在，请更换`, '配置不完整')
      return
    }

    if (!textForm.value.type) {
      setError('请选择服务商类型', '配置不完整')
      return
    }

    // 新增时必须填写 API Key
    if (!editingTextProvider.value && !textForm.value.api_key) {
      setError('请填写 API Key', '配置不完整')
      return
    }

    const providerData: any = {
      type: textForm.value.type,
      provider_label: label,
      enabled: originalName ? textConfig.value.providers[originalName]?.enabled !== false : true,
      display_name: displayName,
      model: textForm.value.model,
      remark: (textForm.value.remark || '').trim()
    }

    // 如果填写了新的 API Key，使用新的；留空则由后端保留原有
    if (textForm.value.api_key) {
      providerData.api_key = textForm.value.api_key
    }

    if (textForm.value.base_url) {
      providerData.base_url = textForm.value.base_url
    }

    // 如果是 OpenAI 兼容接口，保存 endpoint_type
    if (textForm.value.type === 'openai_compatible') {
      providerData.endpoint_type = textForm.value.endpoint_type
      providerData.api_protocol = textForm.value.api_protocol
    }

    if (await saveSingleProvider('text', name, providerData)) closeTextModal()
  }

  /**
   * 删除文本服务商
   */
  async function deleteTextProvider(name: string) {
    if (confirm(`确定要删除服务商 "${name}" 吗？`)) {
      delete textConfig.value.providers[name]
      if (textConfig.value.active_provider === name) {
        textConfig.value.active_provider = ''
      }
      await autoSaveConfig()
    }
  }

  /**
   * 测试文本服务商连接（弹窗中）
   */
  async function testTextConnection() {
    testingText.value = true
    try {
      const result = await testConnection({
        type: textForm.value.type,
        provider_name: editingTextProvider.value || undefined,
        api_key: textForm.value.api_key || undefined,
        base_url: textForm.value.base_url,
        endpoint_type: textForm.value.endpoint_type,
        ...(textForm.value.type === 'openai_compatible'
          ? { api_protocol: textForm.value.api_protocol }
          : {}),
        model: textForm.value.model
      })
      if (result.success) {
        setConnectionFeedback(result, '连接成功')
      }
    } catch (e: any) {
      setError(e, '连接失败')
    } finally {
      testingText.value = false
    }
  }

  /**
   * 测试列表中的文本服务商
   */
  async function testTextProviderInList(name: string, provider: Provider) {
    try {
      const result = await testConnection({
        type: provider.type,
        provider_name: name,
        api_key: undefined,
        base_url: provider.base_url,
        endpoint_type: provider.endpoint_type,
        ...(provider.type === 'openai_compatible'
          ? { api_protocol: resolveTextProtocol(provider) }
          : {}),
        model: provider.model
      })
      if (result.success) {
        setConnectionFeedback(result, `${name} 连接成功`)
      }
    } catch (e: any) {
      setError(e, `${name} 连接失败`)
    }
  }

  // ==================== 图片服务商操作 ====================

  /**
   * 切换图片服务商启用状态（多选：绿色开=创作中心可选，灰色关=不可选）
   * 同时维护默认模型：开启时若当前无默认则设为默认；关闭默认时改选其他已启用
   */
  async function activateImageProvider(name: string) {
    const providers = imageConfig.value.providers
    const cur = providers[name] || {}
    const nowEnabled = cur.enabled === false ? true : false
    providers[name] = { ...cur, enabled: nowEnabled }

    if (nowEnabled) {
      const curActive = imageConfig.value.active_provider
      if (!curActive || (providers[curActive] && providers[curActive].enabled === false)) {
        imageConfig.value.active_provider = name
      }
    } else if (imageConfig.value.active_provider === name) {
      const first = Object.keys(providers).find(k => k !== name && providers[k]?.enabled !== false)
      imageConfig.value.active_provider = first || ''
    }
    await autoSaveConfig()
  }

  /**
   * 打开添加图片服务商弹窗
   */
  function openAddImageModal() {
    editingImageProvider.value = null
    imageForm.value = createEmptyImageForm()
    showImageModal.value = true
  }

  /**
   * 打开编辑图片服务商弹窗
   */
  function openEditImageModal(name: string, provider: Provider) {
    editingImageProvider.value = name
    imageForm.value = {
      name: provider.provider_label || name,
      display_name: provider.display_name || '',
      type: provider.type || '',
      api_key: '',
      api_key_masked: provider.api_key_masked || '',
      base_url: provider.base_url || '',
      model: provider.model || '',
      high_concurrency: provider.high_concurrency || false,
      short_prompt: provider.short_prompt || false,
      endpoint_type: provider.endpoint_type || '/v1/images/generations',
      remark: provider.remark || '',
      _has_api_key: !!provider.api_key_masked
    }
    showImageModal.value = true
  }

  /**
   * 关闭图片服务商弹窗
   */
  function closeImageModal() {
    showImageModal.value = false
    editingImageProvider.value = null
  }

  /**
   * 保存图片服务商（只保存这一个，不影响其他服务商）
   */
  async function saveImageProvider() {
    if (saving.value) return
    const originalName = editingImageProvider.value
    const name = (originalName || imageForm.value.name).trim()

    if (!name || !imageForm.value.name.trim()) {
      setError('请填写服务商', '配置不完整')
      return
    }

    // 名称由弹窗自动生成（服务商:模型），此处以防遗漏兜底计算
    const modelT = imageForm.value.model.trim()
    const label = imageForm.value.name.trim()
    const displayName = modelT ? `${label}:${modelT}` : label

    // 名称（display_name）在本类（图片）中不能重复；旧配置无 display_name 时以其标识兜底
    const dup = Object.entries(imageConfig.value.providers).find(
      ([k, p]) => k !== originalName && (p.display_name || k) === displayName
    )
    if (dup) {
      setError(`名称 "${displayName}" 已存在，请更换`, '配置不完整')
      return
    }

    if (!imageForm.value.type) {
      setError('请填写服务商类型', '配置不完整')
      return
    }

    // 新增时必须填写 API Key
    if (!editingImageProvider.value && !imageForm.value.api_key) {
      setError('请填写 API Key', '配置不完整')
      return
    }

    const providerData: any = {
      type: imageForm.value.type,
      provider_label: label,
      enabled: originalName ? imageConfig.value.providers[originalName]?.enabled !== false : true,
      display_name: displayName,
      model: imageForm.value.model,
      high_concurrency: imageForm.value.high_concurrency,
      short_prompt: imageForm.value.short_prompt,
      remark: (imageForm.value.remark || '').trim()
    }

    // 如果是 OpenAI 兼容接口，保存 endpoint_type
    if (imageForm.value.type === 'image_api') {
      providerData.endpoint_type = imageForm.value.endpoint_type
    }

    // 如果填写了新的 API Key，使用新的；留空则由后端保留原有
    if (imageForm.value.api_key) {
      providerData.api_key = imageForm.value.api_key
    }

    if (imageForm.value.base_url) {
      providerData.base_url = imageForm.value.base_url
    }

    if (await saveSingleProvider('image', name, providerData)) closeImageModal()
  }

  /**
   * 调用单条保存接口并刷新配置
   */
  async function saveSingleProvider(kind: 'text' | 'image', name: string, data: any) {
    saving.value = true
    try {
      const res = await saveProvider(kind, name, data)
      if (res.success) {
        if (!await loadConfig()) return false
        setSuccess(res.message || '服务商已保存')
        return true
      } else {
        setError(res.error || res.error_message || '保存失败', '保存失败')
      }
    } catch (e) {
      setError(e, '保存失败')
    } finally { saving.value = false }
    return false
  }

  /**
   * 删除图片服务商
   */
  async function deleteImageProvider(name: string) {
    if (confirm(`确定要删除服务商 "${name}" 吗？`)) {
      delete imageConfig.value.providers[name]
      if (imageConfig.value.active_provider === name) {
        imageConfig.value.active_provider = ''
      }
      await autoSaveConfig()
    }
  }

  /**
   * 测试图片服务商连接（弹窗中）
   */
  async function testImageConnection() {
    testingImage.value = true
    try {
      const result = await testConnection({
        type: imageForm.value.type,
        provider_name: editingImageProvider.value || undefined,
        api_key: imageForm.value.api_key || undefined,
        base_url: imageForm.value.base_url,
        endpoint_type: imageForm.value.endpoint_type,
        model: imageForm.value.model
      })
      if (result.success) {
        setConnectionFeedback(result, '连接成功')
      }
    } catch (e: any) {
      setError(e, '连接失败')
    } finally {
      testingImage.value = false
    }
  }

  /**
   * 测试列表中的图片服务商
   */
  async function testImageProviderInList(name: string, provider: Provider) {
    try {
      const result = await testConnection({
        type: provider.type,
        provider_name: name,
        api_key: undefined,
        base_url: provider.base_url,
        endpoint_type: provider.endpoint_type,
        model: provider.model
      })
      if (result.success) {
        setConnectionFeedback(result, `${name} 连接成功`)
      }
    } catch (e: any) {
      setError(e, `${name} 连接失败`)
    }
  }

  /**
   * 更新文本表单数据
   */
  function updateTextForm(data: TextProviderForm) {
    textForm.value = { ...data }
  }

  /**
   * 更新图片表单数据
   */
  function updateImageForm(data: ImageProviderForm) {
    imageForm.value = data
  }

  return {
    // 状态
    loading,
    saving,
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
  }
}
