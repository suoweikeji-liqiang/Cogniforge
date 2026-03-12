type RefLike<T> = {
  value: T
}

type ApiClient = {
  put: (url: string, data?: any, config?: any) => Promise<{ data: any }>
  post: (url: string, data?: any, config?: any) => Promise<{ data: any }>
}

type TranslateFn = (key: string, params?: Record<string, unknown>) => string

type ProblemDetailPathActionDeps = {
  api: ApiClient
  problemId: string
  t: TranslateFn
  learningPath: RefLike<any>
  learningMode: RefLike<'socratic' | 'exploration'>
  updatingPath: RefLike<boolean>
  problem: RefLike<any>
  totalSteps: RefLike<number>
  autoAdvanceMessage: RefLike<string>
  canUndoAutoAdvance: RefLike<boolean>
  undoTargetStep: RefLike<number | null>
  clearCurrentInteractionContext: (mode?: 'socratic' | 'exploration') => void
  onActionError: (message: string) => void
  clearActionError: () => void
  fetchLearningPath: () => Promise<void>
  fetchLearningPaths: () => Promise<void>
  fetchSocraticQuestion: () => Promise<void>
}

export const createProblemDetailPathActions = ({
  api,
  problemId,
  t,
  learningPath,
  learningMode,
  updatingPath,
  problem,
  totalSteps,
  autoAdvanceMessage,
  canUndoAutoAdvance,
  undoTargetStep,
  clearCurrentInteractionContext,
  onActionError,
  clearActionError,
  fetchLearningPath,
  fetchLearningPaths,
  fetchSocraticQuestion,
}: ProblemDetailPathActionDeps) => {
  const refreshPathViews = async () => {
    await Promise.all([
      fetchLearningPaths(),
      learningMode.value === 'socratic' ? fetchSocraticQuestion() : Promise.resolve(),
    ])
  }

  const updateProblemStatusForStep = (nextStep: number) => {
    if (!problem.value) return

    if (totalSteps.value > 0 && nextStep >= totalSteps.value) {
      problem.value.status = 'completed'
    } else if (nextStep > 0) {
      problem.value.status = 'in-progress'
    } else {
      problem.value.status = 'new'
    }
  }

  const updateCurrentStep = async (nextStep: number) => {
    if (!learningPath.value) return

    clearActionError()
    updatingPath.value = true
    try {
      const response = await api.put(`/problems/${problemId}/learning-path`, {
        current_step: nextStep,
      })
      learningPath.value = response.data
      clearCurrentInteractionContext(learningMode.value)
      await refreshPathViews()
      updateProblemStatusForStep(nextStep)
    } catch (e) {
      console.error('Failed to update learning path:', e)
      onActionError(t('problemDetail.actionErrorStepChange'))
    } finally {
      updatingPath.value = false
    }
  }

  const undoAutoAdvance = async () => {
    if (!learningPath.value) return

    const fallbackTarget = Math.max((learningPath.value.current_step || 1) - 1, 0)
    const targetStep = undoTargetStep.value ?? fallbackTarget
    await updateCurrentStep(targetStep)
    autoAdvanceMessage.value = t('problemDetail.autoAdvanceUndone')
    canUndoAutoAdvance.value = false
    undoTargetStep.value = null
  }

  const activateLearningPathById = async (pathId: string) => {
    if (updatingPath.value) return

    clearActionError()
    updatingPath.value = true
    try {
      const response = await api.post(`/problems/${problemId}/learning-paths/${pathId}/activate`)
      learningPath.value = response.data
      clearCurrentInteractionContext(learningMode.value)
      await refreshPathViews()
    } catch (e) {
      console.error('Failed to activate learning path:', e)
      onActionError(t('problemDetail.actionErrorPathSwitch'))
    } finally {
      updatingPath.value = false
    }
  }

  const returnToParentPath = async () => {
    if (updatingPath.value || !learningPath.value?.parent_path_id) return

    clearActionError()
    updatingPath.value = true
    try {
      const response = await api.post(`/problems/${problemId}/learning-path/return`)
      learningPath.value = response.data
      clearCurrentInteractionContext(learningMode.value)
      await refreshPathViews()
      await fetchLearningPath()
    } catch (e) {
      console.error('Failed to return to parent learning path:', e)
      onActionError(t('problemDetail.actionErrorReturnPath'))
    } finally {
      updatingPath.value = false
    }
  }

  return {
    updateCurrentStep,
    undoAutoAdvance,
    activateLearningPathById,
    returnToParentPath,
  }
}
