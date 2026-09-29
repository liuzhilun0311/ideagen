export type TextApiProtocol = 'responses' | 'chat_completions'

export function resolveTextProtocol(config: {
  api_protocol?: TextApiProtocol
  endpoint_type?: string
}): TextApiProtocol {
  if (config.api_protocol) return config.api_protocol
  return config.endpoint_type?.trim().replace(/\/+$/, '').endsWith('/responses')
    ? 'responses'
    : 'chat_completions'
}

export function defaultTextEndpoint(protocol: TextApiProtocol): string {
  return protocol === 'responses' ? '/v1/responses' : '/v1/chat/completions'
}

export function isCustomTextEndpoint(endpoint: string): boolean {
  const path = endpoint.trim().replace(/^\/?/, '/').replace(/\/+$/, '')
  return !!path && ![
    '/v1/responses', '/responses', '/v1/chat/completions', '/chat/completions'
  ].includes(path)
}

export function endpointForTextProtocol(endpoint: string, protocol: TextApiProtocol): string {
  return isCustomTextEndpoint(endpoint) ? endpoint : defaultTextEndpoint(protocol)
}
