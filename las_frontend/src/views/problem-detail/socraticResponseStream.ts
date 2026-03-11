import { consumeSseResponse, fetchStreamWithAuthRetry } from '@/views/problem-detail/streamingSupport'

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
  refreshToken,
  payload,
  onEvent,
}: {
  problemId: string
  token: string
  refreshToken?: (() => Promise<string | null>) | null
  payload: SocraticResponseStreamPayload
  onEvent: (event: SocraticResponseStreamEvent) => void
}) => {
  const response = await fetchStreamWithAuthRetry({
    path: `/problems/${problemId}/responses/stream`,
    method: 'POST',
    token,
    refreshToken,
    body: JSON.stringify(payload),
    contentType: 'application/json',
  })

  await consumeSseResponse({
    response,
    onBlock: (rawBlock) => parseEventBlock(rawBlock, onEvent),
  })
}
