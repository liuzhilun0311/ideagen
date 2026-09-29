import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getConfig, saveProvider, testConnection, updateConfig } from '../../src/api'
import { useProviderForm, type Provider } from '../../src/composables/useProviderForm'
import { endpointForTextProtocol, isCustomTextEndpoint, resolveTextProtocol, type TextApiProtocol } from '../../src/utils/textProtocol'

vi.mock('../../src/api', () => ({
  getConfig: vi.fn(),
  saveProvider: vi.fn(),
  testConnection: vi.fn(),
  updateConfig: vi.fn(),
}))

const provider = (overrides: Partial<Provider> = {}): Provider => ({
  type: 'openai_compatible',
  model: 'arbitrary/model-release',
  base_url: 'https://relay.invalid/custom-prefix',
  api_key_masked: '********',
  ...overrides,
})

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(getConfig).mockResolvedValue({
    success: true,
    config: {
      text_generation: { active_provider: '', providers: {} },
      image_generation: { active_provider: '', providers: {} },
    },
  })
  vi.mocked(saveProvider).mockResolvedValue({ success: true })
  vi.mocked(updateConfig).mockResolvedValue({ success: true })
  vi.mocked(testConnection).mockResolvedValue({ success: true })
})

describe('text provider protocol form flows', () => {
  it.each(['text', 'image'] as const)('updates %s provider labels while preserving the stable selection key', async kind => {
    const form = useProviderForm()
    const existing = provider({ provider_label: 'Old label', enabled: false })
    const config = kind === 'text' ? form.textConfig : form.imageConfig
    config.value.providers.stable = existing
    if (kind === 'text') form.openEditTextModal('stable', existing)
    else form.openEditImageModal('stable', existing)
    const fields = kind === 'text' ? form.textForm : form.imageForm
    expect(fields.value.name).toBe('Old label')
    fields.value.name = 'New label'
    fields.value.model = 'new-model'
    fields.value.display_name = 'stale display'
    await (kind === 'text' ? form.saveTextProvider() : form.saveImageProvider())
    expect(saveProvider).toHaveBeenCalledWith(kind, 'stable', expect.objectContaining({
      provider_label: 'New label', display_name: 'New label:new-model', enabled: false,
    }))
    expect(updateConfig).not.toHaveBeenCalled()
  })

  it.each(['text', 'image'] as const)('retains %s form edits when saving fails', async kind => {
    vi.mocked(saveProvider).mockRejectedValue(new Error('offline'))
    const form = useProviderForm()
    if (kind === 'text') form.openEditTextModal('stable', provider())
    else form.openEditImageModal('stable', provider())
    await (kind === 'text' ? form.saveTextProvider() : form.saveImageProvider())
    expect((kind === 'text' ? form.showTextModal : form.showImageModal).value).toBe(true)
    expect(form.feedback.value?.type).toBe('error')
    expect(form.saving.value).toBe(false)
  })
  it('shows image model-list verification as a warning in both entry points', async () => {
    vi.mocked(testConnection).mockResolvedValue({
      success: true, warning: true, message: '尚未验证图片生成',
    })
    const form = useProviderForm()
    const imageProvider = provider({ type: 'image_api' })
    form.openEditImageModal('image', imageProvider)
    await form.testImageConnection()
    expect(form.feedback.value).toEqual({ type: 'warning', message: '尚未验证图片生成' })
    form.clearFeedback()
    await form.testImageProviderInList('image', imageProvider)
    expect(form.feedback.value).toEqual({ type: 'warning', message: '尚未验证图片生成' })
  })
  it('starts and resets new forms with Chat Completions', () => {
    const form = useProviderForm()
    form.openEditTextModal('existing', provider({ api_protocol: 'responses' }))
    form.openAddTextModal()
    expect(form.textForm.value).toMatchObject({
      api_protocol: 'chat_completions',
      endpoint_type: '/v1/chat/completions',
      api_key: '',
      _has_api_key: false,
    })
  })

  it.each([
    [undefined, 'chat_completions'],
    ['/v1/chat/completions', 'chat_completions'],
    ['/custom/path', 'chat_completions'],
    ['/v1/responses', 'responses'],
    ['/relay/responses/', 'responses'],
    ['/responses-extra', 'chat_completions'],
  ] as const)('infers legacy endpoint %s on load, edit and list test', async (endpoint, protocol) => {
    vi.mocked(getConfig).mockResolvedValue({
      success: true,
      config: {
        text_generation: { active_provider: 'legacy', providers: { legacy: provider({ endpoint_type: endpoint }) } },
        image_generation: { active_provider: '', providers: {} },
      },
    })
    const form = useProviderForm()
    await form.loadConfig()
    const loaded = form.textConfig.value.providers.legacy
    expect(loaded.api_protocol).toBe(protocol)
    form.openEditTextModal('legacy', loaded)
    expect(form.textForm.value.api_protocol).toBe(protocol)
    await form.testTextProviderInList('legacy', provider({ endpoint_type: endpoint }))
    expect(testConnection).toHaveBeenCalledWith(expect.objectContaining({
      api_protocol: protocol, provider_name: 'legacy', api_key: undefined,
    }))
  })

  it.each(['responses', 'chat_completions'] as const)('honors explicit %s over endpoint inference', protocol => {
    const form = useProviderForm()
    const endpoint = protocol === 'responses' ? '/v1/chat/completions' : '/v1/responses'
    form.openEditTextModal('explicit', provider({ api_protocol: protocol, endpoint_type: endpoint }))
    expect(form.textForm.value.api_protocol).toBe(protocol)
    expect(form.textForm.value.endpoint_type).toBe(endpoint)
    expect(resolveTextProtocol({ api_protocol: protocol, endpoint_type: endpoint })).toBe(protocol)
  })

  it.each(['', '/v1/chat/completions', '/chat/completions'])('switches standard or empty endpoint %s both ways', endpoint => {
    const responsesEndpoint = endpointForTextProtocol(endpoint, 'responses')
    expect(responsesEndpoint).toBe('/v1/responses')
    expect(endpointForTextProtocol(responsesEndpoint, 'chat_completions')).toBe('/v1/chat/completions')
  })

  it('preserves an endpoint manually edited after switching the modal protocol', async () => {
    const form = useProviderForm()
    form.openEditTextModal('relay', provider())
    form.updateTextForm({ ...form.textForm.value, api_protocol: 'responses', endpoint_type: '/responses' })
    await form.testTextConnection()
    await form.saveTextProvider()
    expect(testConnection).toHaveBeenCalledWith(expect.objectContaining({ endpoint_type: '/responses' }))
    expect(saveProvider).toHaveBeenCalledWith('text', 'relay', expect.objectContaining({ endpoint_type: '/responses' }))
  })

  it.each(['/relay/responses', '/custom/chat/completions', 'custom/endpoint'])('preserves and identifies custom path %s', endpoint => {
    const form = useProviderForm()
    form.openEditTextModal('custom', provider({ endpoint_type: endpoint }))
    for (const protocol of ['responses', 'chat_completions'] as TextApiProtocol[]) {
      form.updateTextForm({ ...form.textForm.value, api_protocol: protocol })
      expect(form.textForm.value.endpoint_type).toBe(endpoint)
      expect(endpointForTextProtocol(endpoint, protocol)).toBe(endpoint)
      expect(isCustomTextEndpoint(endpoint)).toBe(true)
    }
  })

  it('tests and saves edited Responses config without submitting the masked key', async () => {
    const form = useProviderForm()
    form.openEditTextModal('relay', provider())
    form.updateTextForm({ ...form.textForm.value, api_protocol: 'responses', endpoint_type: '/v1/responses' })
    await form.testTextConnection()
    expect(testConnection).toHaveBeenCalledWith({
      type: 'openai_compatible',
      provider_name: 'relay',
      api_key: undefined,
      base_url: 'https://relay.invalid/custom-prefix',
      model: 'arbitrary/model-release',
      endpoint_type: '/v1/responses',
      api_protocol: 'responses',
    })
    await form.saveTextProvider()
    expect(saveProvider).toHaveBeenCalledWith('text', 'relay', {
      provider_label: 'relay',
      enabled: true,
      type: 'openai_compatible',
      display_name: 'relay:arbitrary/model-release',
      model: 'arbitrary/model-release',
      base_url: 'https://relay.invalid/custom-prefix',
      endpoint_type: '/v1/responses',
      api_protocol: 'responses',
      remark: '',
    })
    expect(getConfig).toHaveBeenCalledOnce()
    expect(form.showTextModal.value).toBe(false)
  })

  it('saves and reloads a new provider with synthetic credentials through mocked APIs only', async () => {
    const form = useProviderForm()
    form.openAddTextModal()
    form.updateTextForm({
      ...form.textForm.value,
      name: 'new',
      api_key: 'synthetic-test-only',
      api_protocol: 'responses',
      endpoint_type: '/v1/responses',
      model: 'opaque:model-id',
      base_url: 'https://example.invalid/proxy',
    })
    vi.mocked(saveProvider).mockImplementation(async (_kind, name, data) => {
      const { api_key: _discarded, ...saved } = data
      vi.mocked(getConfig).mockResolvedValue({
        success: true,
        config: {
          text_generation: { active_provider: name, providers: { [name]: { ...saved, api_key_masked: '********' } } },
          image_generation: { active_provider: '', providers: {} },
        },
      })
      return { success: true }
    })
    await form.testTextConnection()
    expect(testConnection).toHaveBeenCalledWith(expect.objectContaining({
      api_key: 'synthetic-test-only', api_protocol: 'responses', provider_name: undefined,
    }))
    await form.saveTextProvider()
    expect(saveProvider).toHaveBeenCalledWith('text', 'new', expect.objectContaining({
      api_key: 'synthetic-test-only', api_protocol: 'responses', endpoint_type: '/v1/responses',
    }))
    form.openEditTextModal('new', form.textConfig.value.providers.new)
    expect(form.textForm.value).toMatchObject({
      api_protocol: 'responses', endpoint_type: '/v1/responses',
      model: 'opaque:model-id', base_url: 'https://example.invalid/proxy',
      api_key: '', api_key_masked: '********', _has_api_key: true,
    })
  })

  it('carries explicit protocol and custom path into list tests and activation persistence', async () => {
    const saved = provider({ api_protocol: 'responses', endpoint_type: '/relay/generate' })
    const form = useProviderForm()
    form.textConfig.value.providers.relay = saved
    await form.testTextProviderInList('relay', saved)
    expect(testConnection).toHaveBeenCalledWith(expect.objectContaining({
      api_protocol: 'responses', endpoint_type: '/relay/generate', api_key: undefined,
    }))
    await form.activateTextProvider('relay')
    expect(updateConfig).toHaveBeenCalledWith(expect.objectContaining({
      text_generation: expect.objectContaining({
        providers: { relay: { ...saved, enabled: false } },
      }),
    }))
  })

  it('does not add text protocols to Gemini or image payloads', async () => {
    const form = useProviderForm()
    form.openEditTextModal('gemini', provider({ type: 'google_gemini' }))
    await form.testTextConnection()
    await form.saveTextProvider()
    expect(vi.mocked(testConnection).mock.calls[0][0]).not.toHaveProperty('api_protocol')
    expect(vi.mocked(saveProvider).mock.calls[0][2]).not.toHaveProperty('api_protocol')
    form.openEditImageModal('image', provider({ type: 'image_api' }))
    await form.testImageConnection()
    await form.saveImageProvider()
    expect(vi.mocked(testConnection).mock.calls[1][0]).not.toHaveProperty('api_protocol')
    expect(vi.mocked(saveProvider).mock.calls[1][2]).not.toHaveProperty('api_protocol')
  })
})
