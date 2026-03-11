import { streamExplorationAsk } from '@/views/problem-detail/explorationStream'
import { streamSocraticResponse } from '@/views/problem-detail/socraticResponseStream'

type LearningMode = 'socratic' | 'exploration'

type RefLike<T> = {
  value: T
}

type ApiClient = {
  get: (url: string, config?: any) => Promise<{ data: any }>
  post: (url: string, data?: any, config?: any) => Promise<{ data: any }>
  put: (url: string, data?: any, config?: any) => Promise<{ data: any }>
}

type TranslateFn = (key: string, params?: Record<string, unknown>) => string

type LearningActionDeps = {
  api: ApiClient
  problemId: string
  t: TranslateFn
  ensureFreshToken: () => Promise<string | null>
  refreshToken: () => Promise<string | null>
  getToken: () => string | null
  problem: RefLike<any>
  learningMode: RefLike<LearningMode>
  switchingMode: RefLike<boolean>
  submitting: RefLike<boolean>
  hintLoading: RefLike<boolean>
  askingQuestion: RefLike<boolean>
  responses: RefLike<any[]>
  responseText: RefLike<string>
  learningQuestion: RefLike<string>
  answerMode: RefLike<'direct' | 'guided'>
  socraticQuestion: RefLike<any | null>
  stepHint: RefLike<any | null>
  autoAdvanceMessage: RefLike<string>
  canUndoAutoAdvance: RefLike<boolean>
  undoTargetStep: RefLike<number | null>
  streamingSocraticStatus: RefLike<string>
  streamingSocraticPreview: RefLike<string>
  streamingExplorationAnswer: RefLike<string>
  latestExplorationTurnId: RefLike<string | null>
  currentStep: RefLike<any | null>
  fetchConceptCandidates: () => Promise<void>
  fetchPathCandidates: () => Promise<void>
  fetchExplorationTurns: () => Promise<void>
  fetchLearningPath: () => Promise<void>
  fetchSocraticQuestion: () => Promise<void>
}

const normalizeTurnId = (value: unknown) => {
  const normalized = String(value || '').trim()
  return normalized || null
}

export const createProblemDetailLearningActions = ({
  api,
  problemId,
  t,
  ensureFreshToken,
  refreshToken,
  getToken,
  problem,
  learningMode,
  switchingMode,
  submitting,
  hintLoading,
  askingQuestion,
  responses,
  responseText,
  learningQuestion,
  answerMode,
  socraticQuestion,
  stepHint,
  autoAdvanceMessage,
  canUndoAutoAdvance,
  undoTargetStep,
  streamingSocraticStatus,
  streamingSocraticPreview,
  streamingExplorationAnswer,
  latestExplorationTurnId,
  currentStep,
  fetchConceptCandidates,
  fetchPathCandidates,
  fetchExplorationTurns,
  fetchLearningPath,
  fetchSocraticQuestion,
}: LearningActionDeps) => {
  const syncProblemSnapshot = async () => {
    try {
      const response = await api.get(`/problems/${problemId}`)
      problem.value = response.data
      learningMode.value = response.data?.learning_mode || learningMode.value
    } catch {
      return null
    }
    return problem.value
  }

  const buildLocalGuidedTemplate = () => {
    const concept = currentStep.value?.concept || problem.value?.title || ''
    return [
      t('problemDetail.guidedLine1', { concept }),
      t('problemDetail.guidedLine2'),
      t('problemDetail.guidedLine3'),
    ].join('\n')
  }

  const formatSocraticStreamStatus = (phase: string | undefined | null) => {
    if (phase === 'extracting_artifacts') return t('problemDetail.socraticStreamExtracting')
    if (phase === 'saving_turn') return t('problemDetail.socraticStreamSaving')
    return t('problemDetail.socraticStreamEvaluating')
  }

  const formatSocraticPreview = (preview: { mastery_score?: number; correctness?: string; confidence?: number }) => {
    const score = Number(preview.mastery_score ?? 0)
    const confidence = Math.round(Math.max(0, Math.min(1, Number(preview.confidence ?? 0))) * 100)
    const correctness = String(preview.correctness || '').trim() || t('common.loading')
    return t('problemDetail.socraticStreamPreview', {
      score: Number.isFinite(score) ? score : 0,
      correctness,
      confidence,
    })
  }

  const refreshExplorationWorkspace = async () => {
    await Promise.all([
      fetchConceptCandidates(),
      fetchPathCandidates(),
      fetchExplorationTurns(),
      syncProblemSnapshot(),
    ])
  }

  const setLearningMode = async (mode: LearningMode) => {
    if (switchingMode.value || learningMode.value === mode) return

    const previousMode = learningMode.value
    learningMode.value = mode
    if (problem.value) {
      problem.value.learning_mode = mode
    }

    switchingMode.value = true
    try {
      await api.put(`/problems/${problemId}`, { learning_mode: mode })
      if (mode === 'socratic') {
        await fetchSocraticQuestion()
      }
    } catch (e) {
      console.error('Failed to switch learning mode:', e)
      learningMode.value = previousMode
      if (problem.value) {
        problem.value.learning_mode = previousMode
      }
    } finally {
      switchingMode.value = false
    }
  }

  const submitResponse = async () => {
    submitting.value = true
    streamingSocraticStatus.value = ''
    streamingSocraticPreview.value = ''

    try {
      const payload = {
        problem_id: problemId,
        user_response: responseText.value,
        learning_mode: learningMode.value,
        question_kind: socraticQuestion.value?.question_kind,
        socratic_question: socraticQuestion.value?.question,
      }

      let responseData: any = null
      let usedStream = false
      const token = await ensureFreshToken() || getToken()

      if (token) {
        try {
          let finalPayload: Record<string, unknown> | null = null
          let streamError: string | null = null

          await streamSocraticResponse({
            problemId,
            token,
            refreshToken,
            payload: {
              ...payload,
              learning_mode: 'socratic',
            },
            onEvent: (event) => {
              if (event.event === 'status') {
                streamingSocraticStatus.value = formatSocraticStreamStatus(event.data?.phase)
                return
              }
              if (event.event === 'preview') {
                streamingSocraticPreview.value = formatSocraticPreview(event.data || {})
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
          responseData = finalPayload
          usedStream = true
        } catch (e) {
          console.error('Failed to stream socratic response, falling back to standard request:', e)
          streamingSocraticStatus.value = ''
          streamingSocraticPreview.value = ''
        }
      }

      if (!usedStream) {
        const response = await api.post(`/problems/${problemId}/responses`, payload)
        responseData = response.data
      }

      responses.value.push(responseData)
      await Promise.all([
        fetchConceptCandidates(),
        fetchPathCandidates(),
        syncProblemSnapshot(),
      ])
      responseText.value = ''
      if (responseData?.auto_advanced) {
        await fetchLearningPath()
        autoAdvanceMessage.value = t('problemDetail.autoAdvanced')
        canUndoAutoAdvance.value = true
        const suggestedUndo = Number(responseData?.new_current_step ?? 0) - 1
        undoTargetStep.value = Number.isFinite(suggestedUndo) ? Math.max(0, suggestedUndo) : null
        if (problem.value && problem.value.status === 'new') {
          problem.value.status = 'in-progress'
        }
      } else {
        autoAdvanceMessage.value = ''
        canUndoAutoAdvance.value = false
        undoTargetStep.value = null
      }

      if (problem.value?.status === 'new' && !responseData?.auto_advanced) {
        problem.value.status = 'in-progress'
      }
      await fetchSocraticQuestion()
    } catch (e) {
      console.error('Failed to submit response:', e)
    } finally {
      streamingSocraticStatus.value = ''
      streamingSocraticPreview.value = ''
      submitting.value = false
    }
  }

  const prefillGuidedTemplate = async () => {
    hintLoading.value = true
    try {
      const response = await api.get(`/problems/${problemId}/learning-path/hint`)
      stepHint.value = response.data?.structured_hint || null
      const starter = response.data?.structured_hint?.starter?.trim()
      if (starter) {
        responseText.value = `${starter}\n`
      } else {
        responseText.value = response.data?.hint?.trim() || buildLocalGuidedTemplate()
      }
    } catch (e) {
      console.error('Failed to fetch learning hint:', e)
      stepHint.value = null
      responseText.value = buildLocalGuidedTemplate()
    } finally {
      hintLoading.value = false
    }
  }

  const askLearningQuestion = async () => {
    const question = learningQuestion.value.trim()
    if (!question || askingQuestion.value) return

    askingQuestion.value = true
    streamingExplorationAnswer.value = ''
    try {
      let usedStream = false
      const token = await ensureFreshToken() || getToken()

      if (token) {
        try {
          let finalPayload: Record<string, unknown> | null = null
          let streamError: string | null = null

          await streamExplorationAsk({
            problemId,
            token,
            refreshToken,
            payload: {
              question,
              learning_mode: 'exploration',
              answer_mode: answerMode.value,
            },
            onEvent: (event) => {
              if (event.event === 'token') {
                streamingExplorationAnswer.value += event.data
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
          latestExplorationTurnId.value = normalizeTurnId((finalPayload as any)?.turn_id)
          usedStream = true
        } catch (e) {
          console.error('Failed to stream learning question, falling back to standard request:', e)
          streamingExplorationAnswer.value = ''
        }
      }

      if (!usedStream) {
        const response = await api.post(`/problems/${problemId}/ask`, {
          question,
          learning_mode: learningMode.value,
          answer_mode: answerMode.value,
        })
        latestExplorationTurnId.value = normalizeTurnId(response.data?.turn_id)
      }

      await refreshExplorationWorkspace()
      learningQuestion.value = ''
    } catch (e) {
      console.error('Failed to ask learning question:', e)
    } finally {
      streamingExplorationAnswer.value = ''
      askingQuestion.value = false
    }
  }

  return {
    syncProblemSnapshot,
    refreshExplorationWorkspace,
    setLearningMode,
    submitResponse,
    prefillGuidedTemplate,
    askLearningQuestion,
  }
}
