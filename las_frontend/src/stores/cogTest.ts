import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

export interface Message {
  role: 'guide' | 'challenger' | 'user'
  content: string
  streaming?: boolean
}

export type SessionStatus = 'idle' | 'connecting' | 'streaming' | 'waiting' | 'stopped' | 'completed'

export interface SessionSummary {
  id: string
  concept: string
  status: string
  created_at: string
  score?: number | null
}

const getSSEBaseUrl = () => {
  const nativeUrl = localStorage.getItem('api_server_url')
  if (nativeUrl) return nativeUrl
  return '/api'
}

let eventSource: EventSource | null = null

export const useCogTestStore = defineStore('cogTest', () => {
  const sessionId = ref<string | null>(null)
  const concept = ref<string>('')
  const status = ref<SessionStatus>('idle')
  const messages = ref<Message[]>([])
  const currentRound = ref(1)
  const maxRounds = ref(3)
  const error = ref<string | null>(null)
  const sessions = ref<SessionSummary[]>([])

  function _closeEventSource() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  function _openStream() {
    const authStore = useAuthStore()
    const token = authStore.token
    const url = `${getSSEBaseUrl()}/cog-test/sessions/${sessionId.value}/stream?token=${token}`

    eventSource = new EventSource(url)

    eventSource.addEventListener('session_start', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      maxRounds.value = data.max_rounds
      status.value = 'streaming'
    })

    eventSource.addEventListener('turn_start', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      messages.value.push({ role: data.role, content: '', streaming: true })
      currentRound.value = data.round
    })

    eventSource.addEventListener('token', (e: MessageEvent) => {
      const last = messages.value[messages.value.length - 1]
      if (last) {
        last.content += e.data
      }
    })

    eventSource.addEventListener('turn_complete', () => {
      const last = messages.value[messages.value.length - 1]
      if (last) {
        last.streaming = false
      }
      status.value = 'waiting'
    })

    eventSource.addEventListener('round_complete', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      currentRound.value = data.round
    })

    eventSource.addEventListener('session_complete', () => {
      status.value = 'completed'
      _closeEventSource()
    })

    eventSource.addEventListener('error', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      error.value = data.message
      status.value = 'stopped'
      _closeEventSource()
    })

    eventSource.onerror = () => {
      if (status.value !== 'completed' && status.value !== 'stopped') {
        status.value = 'stopped'
        error.value = 'Connection lost'
        _closeEventSource()
      }
    }
  }

  async function startSession(conceptName: string, modelCardId?: string) {
    const response = await api.post('/cog-test/sessions', {
      concept: conceptName,
      max_rounds: 3,
      model_card_id: modelCardId || null,
    })
    sessionId.value = response.data.session_id
    concept.value = conceptName
    status.value = 'connecting'
    messages.value = []
    error.value = null
    currentRound.value = 1
    _openStream()
  }

  async function submitUserTurn(text: string) {
    if (!sessionId.value) return
    messages.value.push({ role: 'user', content: text })
    status.value = 'streaming'
    await api.post(`/cog-test/sessions/${sessionId.value}/turns`, { text })
  }

  async function stopSession() {
    if (!sessionId.value) return
    await api.post(`/cog-test/sessions/${sessionId.value}/stop`)
    _closeEventSource()
    status.value = 'stopped'
  }

  async function fetchSessions() {
    const response = await api.get('/cog-test/sessions')
    sessions.value = response.data
  }

  async function exportReport(sid: string, conceptName: string) {
    const response = await api.get(`/cog-test/sessions/${sid}/report`, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(
      new Blob([response.data], { type: 'text/markdown' })
    )
    const a = document.createElement('a')
    a.href = url
    a.download = `cog-report-${conceptName.slice(0, 30).replace(/\s+/g, '-')}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  function resetSession() {
    _closeEventSource()
    sessionId.value = null
    concept.value = ''
    status.value = 'idle'
    messages.value = []
    currentRound.value = 1
    maxRounds.value = 3
    error.value = null
  }

  return {
    sessionId,
    concept,
    status,
    messages,
    currentRound,
    maxRounds,
    error,
    sessions,
    startSession,
    submitUserTurn,
    stopSession,
    fetchSessions,
    exportReport,
    resetSession,
  }
})
