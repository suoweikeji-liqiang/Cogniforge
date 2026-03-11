export type SocraticResponseStreamPayload = {
  problem_id: string
  user_response: string
  learning_mode: 'socratic'
  question_kind?: string | null
  socratic_question?: string | null
}

export type SocraticResponseStreamEvent =
  | { event: 'status'; data: { phase?: string } }
  | { event: 'preview'; data: { mastery_score?: number; confidence?: number; correctness?: string; phase?: string } }
  | { event: 'final'; data: Record<string, unknown> }
  | { event: 'done'; data: string }
  | { event: 'error'; data: { message?: string } }

const getApiBaseUrl = () => {
  const nativeUrl = localStorage.getItem('api_server_url')
  if (nativeUrl) return nativeUrl
  return '/api'
}

const parseEventBlock = (
  rawBlock: string,
  onEvent: (event: SocraticResponseStreamEvent) => void,
) => {
  const lines = rawBlock
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean)

  if (!lines.length) return

  let eventName = 'message'
  const dataLines: string[] = []

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  const data = dataLines.join('\n')
  if (!data && eventName !== 'done') return

  if (eventName === 'status') {
    onEvent({ event: 'status', data: JSON.parse(data) })
    return
  }
  if (eventName === 'preview') {
    onEvent({ event: 'preview', data: JSON.parse(data) })
    return
  }
  if (eventName === 'final') {
    onEvent({ event: 'final', data: JSON.parse(data) })
    return
  }
  if (eventName === 'error') {
    onEvent({ event: 'error', data: JSON.parse(data) })
    return
  }
  if (eventName === 'done') {
    onEvent({ event: 'done', data })
  }
}

export const streamSocraticResponse = async ({
  problemId,
  token,
  payload,
  onEvent,
}: {
  problemId: string
  token: string
  payload: SocraticResponseStreamPayload
  onEvent: (event: SocraticResponseStreamEvent) => void
}) => {
  const response = await fetch(`${getApiBaseUrl()}/problems/${problemId}/responses/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let detail = `Streaming request failed (${response.status})`
    try {
      const errorPayload = await response.json()
      if (typeof errorPayload?.detail === 'string' && errorPayload.detail.trim()) {
        detail = errorPayload.detail.trim()
      }
    } catch {
      // Leave the generic HTTP detail in place.
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('Streaming response body unavailable.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r/g, '')

    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const rawBlock = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      parseEventBlock(rawBlock, onEvent)
      boundary = buffer.indexOf('\n\n')
    }

    if (done) break
  }

  const trailingBlock = buffer.trim()
  if (trailingBlock) {
    parseEventBlock(trailingBlock, onEvent)
  }
}
