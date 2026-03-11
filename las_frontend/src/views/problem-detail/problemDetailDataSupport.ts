import { streamSocraticQuestion } from '@/views/problem-detail/socraticQuestionStream'

type RefLike<T> = {
  value: T
}

type ApiClient = {
  get: (url: string, config?: any) => Promise<{ data: any }>
}

type WorkspaceSnapshot = {
  reviewSchedules?: any[]
  notes?: any[]
  resources?: any[]
}

type ProblemDetailDataDeps = {
  api: ApiClient
  problemId: string
  ensureFreshToken: () => Promise<string | null>
  refreshToken: () => Promise<string | null>
  getToken: () => string | null
  problem: RefLike<any>
  learningMode: RefLike<'socratic' | 'exploration'>
  loading: RefLike<boolean>
  responses: RefLike<any[]>
  learningPath: RefLike<any>
  allLearningPaths: RefLike<any[]>
  qaHistory: RefLike<any[]>
  conceptCandidates: RefLike<any[]>
  pathCandidates: RefLike<any[]>
  socraticQuestion: RefLike<any | null>
  fetchingSocraticQuestion: RefLike<boolean>
  streamingSocraticQuestion: RefLike<string>
  candidateLoading: RefLike<boolean>
  pathCandidateLoading: RefLike<boolean>
  hydrateWorkspaceSnapshot: (snapshot: WorkspaceSnapshot) => void
}

export const createProblemDetailDataSupport = ({
  api,
  problemId,
  ensureFreshToken,
  refreshToken,
  getToken,
  problem,
  learningMode,
  loading,
  responses,
  learningPath,
  allLearningPaths,
  qaHistory,
  conceptCandidates,
  pathCandidates,
  socraticQuestion,
  fetchingSocraticQuestion,
  streamingSocraticQuestion,
  candidateLoading,
  pathCandidateLoading,
  hydrateWorkspaceSnapshot,
}: ProblemDetailDataDeps) => {
  const normalizeExplorationTurn = (turn: any) => ({
    turn_id: turn.turn_id || turn.id || null,
    learning_mode: turn.learning_mode || 'exploration',
    mode_metadata: turn.mode_metadata || {},
    question: turn.question ?? turn.user_text ?? '',
    answer: turn.answer ?? turn.assistant_text ?? '',
    answer_mode: turn.answer_mode ?? turn.mode_metadata?.answer_mode ?? 'direct',
    answer_type: turn.answer_type ?? turn.mode_metadata?.answer_type ?? 'concept_explanation',
    answered_concepts: turn.answered_concepts ?? turn.mode_metadata?.answered_concepts ?? [],
    related_concepts: turn.related_concepts ?? turn.mode_metadata?.related_concepts ?? [],
    derived_candidates: turn.derived_candidates ?? turn.mode_metadata?.derived_candidates ?? [],
    derived_path_candidates: turn.derived_path_candidates ?? turn.mode_metadata?.derived_path_candidates ?? [],
    next_learning_actions: turn.next_learning_actions ?? turn.mode_metadata?.next_learning_actions ?? [],
    path_suggestions: turn.path_suggestions ?? turn.mode_metadata?.path_suggestions ?? [],
    return_to_main_path_hint: turn.return_to_main_path_hint ?? turn.mode_metadata?.return_to_main_path_hint ?? true,
    step_index: Number(turn.step_index ?? turn.mode_metadata?.step_index ?? 0),
    step_concept: turn.step_concept ?? turn.mode_metadata?.step_concept ?? problem.value?.title ?? '',
    suggested_next_focus: turn.suggested_next_focus ?? turn.mode_metadata?.suggested_next_focus ?? null,
    accepted_concepts: turn.accepted_concepts ?? turn.mode_metadata?.accepted_concepts ?? [],
    pending_concepts: turn.pending_concepts ?? turn.mode_metadata?.pending_concepts ?? [],
    trace_id: turn.trace_id,
    llm_calls: turn.llm_calls,
    llm_latency_ms: turn.llm_latency_ms,
    fallback_reason: turn.fallback_reason,
    created_at: turn.created_at,
  })

  const fetchExplorationTurns = async () => {
    try {
      const response = await api.get(`/problems/${problemId}/turns`, {
        params: { learning_mode: 'exploration' },
      })
      qaHistory.value = (response.data || []).map(normalizeExplorationTurn)
    } catch (e) {
      console.error('Failed to fetch exploration turns:', e)
      qaHistory.value = []
    }
  }

  const fetchSocraticQuestion = async () => {
    fetchingSocraticQuestion.value = true
    streamingSocraticQuestion.value = ''
    socraticQuestion.value = null
    try {
      let usedStream = false
      const token = await ensureFreshToken() || getToken()

      if (token) {
        try {
          let finalPayload: Record<string, unknown> | null = null
          let streamError: string | null = null

          await streamSocraticQuestion({
            problemId,
            token,
            refreshToken,
            onEvent: (event) => {
              if (event.event === 'token') {
                streamingSocraticQuestion.value += event.data
                return
              }
              if (event.event === 'final') {
                finalPayload = event.data
                return
              }
              if (event.event === 'error') {
                streamError = event.data?.message?.trim() || 'stream-error'
              }
            },
          })

          if (streamError) {
            throw new Error(streamError)
          }
          if (!finalPayload) {
            throw new Error('stream-finished-without-final-payload')
          }
          socraticQuestion.value = finalPayload
          usedStream = true
        } catch (e) {
          console.error('Failed to stream socratic question, falling back to standard request:', e)
          streamingSocraticQuestion.value = ''
        }
      }

      if (!usedStream) {
        const response = await api.get(`/problems/${problemId}/socratic-question`)
        socraticQuestion.value = response.data || null
      }
    } catch (e) {
      console.error('Failed to fetch socratic question:', e)
      socraticQuestion.value = null
    } finally {
      streamingSocraticQuestion.value = ''
      fetchingSocraticQuestion.value = false
    }
  }

  const fetchConceptCandidates = async () => {
    candidateLoading.value = true
    try {
      const response = await api.get(`/problems/${problemId}/concept-candidates`)
      conceptCandidates.value = response.data || []
    } catch (e) {
      console.error('Failed to fetch concept candidates:', e)
      conceptCandidates.value = []
    } finally {
      candidateLoading.value = false
    }
  }

  const fetchPathCandidates = async () => {
    pathCandidateLoading.value = true
    try {
      const response = await api.get(`/problems/${problemId}/path-candidates`)
      pathCandidates.value = response.data || []
    } catch (e) {
      console.error('Failed to fetch path candidates:', e)
      pathCandidates.value = []
    } finally {
      pathCandidateLoading.value = false
    }
  }

  const fetchLearningPath = async () => {
    const response = await api.get(`/problems/${problemId}/learning-path`).catch(() => ({ data: null }))
    learningPath.value = response.data
  }

  const fetchLearningPaths = async () => {
    const response = await api.get(`/problems/${problemId}/learning-paths`).catch(() => ({ data: [] }))
    allLearningPaths.value = response.data || []
  }

  const fetchProblem = async () => {
    try {
      const [
        problemRes,
        pathRes,
        pathListRes,
        responsesRes,
        candidatesRes,
        pathCandidatesRes,
        turnsRes,
        schedulesRes,
        notesRes,
        resourcesRes,
      ] = await Promise.all([
        api.get(`/problems/${problemId}`),
        api.get(`/problems/${problemId}/learning-path`).catch(() => ({ data: null })),
        api.get(`/problems/${problemId}/learning-paths`).catch(() => ({ data: [] })),
        api.get(`/problems/${problemId}/responses`).catch(() => ({ data: [] })),
        api.get(`/problems/${problemId}/concept-candidates`).catch(() => ({ data: [] })),
        api.get(`/problems/${problemId}/path-candidates`).catch(() => ({ data: [] })),
        api.get(`/problems/${problemId}/turns`, {
          params: { learning_mode: 'exploration' },
        }).catch(() => ({ data: [] })),
        api.get('/srs/schedules').catch(() => ({ data: [] })),
        api.get('/notes/', {
          params: { problem_id: problemId },
        }).catch(() => ({ data: [] })),
        api.get('/resources/', {
          params: { problem_id: problemId },
        }).catch(() => ({ data: [] })),
      ])

      problem.value = problemRes.data
      learningMode.value = problemRes.data?.learning_mode || 'socratic'
      learningPath.value = pathRes.data
      allLearningPaths.value = pathListRes.data || []
      responses.value = responsesRes.data
      conceptCandidates.value = candidatesRes.data || []
      pathCandidates.value = pathCandidatesRes.data || []
      qaHistory.value = (turnsRes.data || []).map(normalizeExplorationTurn)
      hydrateWorkspaceSnapshot({
        reviewSchedules: schedulesRes.data || [],
        notes: notesRes.data || [],
        resources: resourcesRes.data || [],
      })

      if (learningMode.value === 'socratic') {
        await fetchSocraticQuestion()
      } else {
        socraticQuestion.value = null
      }
    } catch (e) {
      console.error('Failed to fetch problem:', e)
    } finally {
      loading.value = false
    }
  }

  return {
    fetchExplorationTurns,
    fetchSocraticQuestion,
    fetchConceptCandidates,
    fetchPathCandidates,
    fetchLearningPath,
    fetchLearningPaths,
    fetchProblem,
  }
}
