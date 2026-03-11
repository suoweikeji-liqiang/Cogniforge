import { consumeSseResponse, fetchStreamWithAuthRetry } from '@/views/problem-detail/streamingSupport'

export type SocraticQuestionStreamEvent =
  | { event: 'token'; data: string }
  | { event: 'final'; data: Record<string, unknown> }
  | { event: 'done'; data: string }
  | { event: 'error'; data: { message?: string } }

const parseEventBlock = (
  rawBlock: string,
  onEvent: (event: SocraticQuestionStreamEvent) => void,
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

  if (eventName === 'token') {
    onEvent({ event: 'token', data })
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

export const streamSocraticQuestion = async ({
  problemId,
  token,
  refreshToken,
  onEvent,
}: {
  problemId: string
  token: string
  refreshToken?: (() => Promise<string | null>) | null
  onEvent: (event: SocraticQuestionStreamEvent) => void
}) => {
  const response = await fetchStreamWithAuthRetry({
    path: `/problems/${problemId}/socratic-question/stream`,
    method: 'GET',
    token,
    refreshToken,
  })

  await consumeSseResponse({
    response,
    onBlock: (rawBlock) => parseEventBlock(rawBlock, onEvent),
  })
}
