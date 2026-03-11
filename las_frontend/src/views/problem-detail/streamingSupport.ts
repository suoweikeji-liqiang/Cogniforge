export const getProblemDetailApiBaseUrl = () => {
  const nativeUrl = localStorage.getItem('api_server_url')
  if (nativeUrl) return nativeUrl
  return '/api'
}

const buildStreamingError = async (response: Response) => {
  let detail = `Streaming request failed (${response.status})`
  try {
    const errorPayload = await response.json()
    if (typeof errorPayload?.detail === 'string' && errorPayload.detail.trim()) {
      detail = errorPayload.detail.trim()
    }
  } catch {
    // Leave the generic HTTP detail in place.
  }
  return new Error(detail)
}

export const fetchStreamWithAuthRetry = async ({
  path,
  method,
  token,
  refreshToken,
  body,
  contentType,
}: {
  path: string
  method: 'GET' | 'POST'
  token: string
  refreshToken?: (() => Promise<string | null>) | null
  body?: string
  contentType?: string
}) => {
  const send = async (activeToken: string) => {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${activeToken}`,
      Accept: 'text/event-stream',
    }
    if (contentType) {
      headers['Content-Type'] = contentType
    }

    return fetch(`${getProblemDetailApiBaseUrl()}${path}`, {
      method,
      headers,
      body,
    })
  }

  let response = await send(token)
  if (response.status === 401 && refreshToken) {
    const refreshedToken = await refreshToken()
    if (refreshedToken) {
      response = await send(refreshedToken)
    }
  }

  if (!response.ok) {
    throw await buildStreamingError(response)
  }

  if (!response.body) {
    throw new Error('Streaming response body unavailable.')
  }

  return response
}

export const consumeSseResponse = async ({
  response,
  onBlock,
}: {
  response: Response
  onBlock: (rawBlock: string) => void
}) => {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('Streaming response body unavailable.')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r/g, '')

    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const rawBlock = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      onBlock(rawBlock)
      boundary = buffer.indexOf('\n\n')
    }

    if (done) break
  }

  const trailingBlock = buffer.trim()
  if (trailingBlock) {
    onBlock(trailingBlock)
  }
}
