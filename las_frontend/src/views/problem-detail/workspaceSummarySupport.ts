import { computed } from 'vue'
import {
  buildReinforcementActionTemplate,
  buildReinforcementStarterContext,
  deriveReinforcementErrorHint,
  extractEvidenceCue,
  normalizeInlineText,
  uniqueContextConcepts,
} from '@/views/problem-detail/reinforcementSupport'

type RefLike<T> = {
  value: T
}

type RouteLike = {
  params: Record<string, unknown>
  query: Record<string, unknown>
}

type TranslateFn = (key: string, params?: Record<string, unknown>) => string

type WorkspaceSummaryDeps = {
  t: TranslateFn
  route: RouteLike
  problem: RefLike<any>
  learningPath: RefLike<any>
  allLearningPaths: RefLike<any[]>
  learningMode: RefLike<'socratic' | 'exploration'>
  totalSteps: RefLike<number>
  currentStepNumber: RefLike<number>
  currentStep: RefLike<any>
  latestQA: RefLike<any>
  latestResponse: RefLike<any>
  latestFeedback: RefLike<any>
  latestPathArtifacts: RefLike<any[]>
  latestDerivedConceptCount: RefLike<number>
  activeConceptTurnId: RefLike<string | null>
  socraticQuestion: RefLike<any | null>
  qaHistory: RefLike<any[]>
  conceptCandidates: RefLike<any[]>
  pathCandidates: RefLike<any[]>
  scheduledReviews: RefLike<any[]>
}

export const createProblemDetailWorkspaceSummarySupport = ({
  t,
  route,
  problem,
  learningPath,
  allLearningPaths,
  learningMode,
  totalSteps,
  currentStepNumber,
  currentStep,
  latestQA,
  latestResponse,
  latestFeedback,
  latestPathArtifacts,
  latestDerivedConceptCount,
  activeConceptTurnId,
  socraticQuestion,
  qaHistory,
  conceptCandidates,
  pathCandidates,
  scheduledReviews,
}: WorkspaceSummaryDeps) => {
  const formatConfidence = (value: number | string | undefined | null) => {
    const parsed = Number(value ?? 0)
    if (!Number.isFinite(parsed)) return '0%'
    const percent = Math.round(Math.max(0, Math.min(1, parsed)) * 100)
    return `${percent}%`
  }

  const formatDateTime = (dateValue: string | undefined | null) => {
    if (!dateValue) return '-'
    return new Date(dateValue).toLocaleString()
  }

  const formatRecallState = (state: string | undefined | null) => {
    if (state === 'fragile') return t('problemDetail.recallStateFragile')
    if (state === 'rebuilding') return t('problemDetail.recallStateRebuilding')
    if (state === 'reinforcing') return t('problemDetail.recallStateReinforcing')
    if (state === 'stable') return t('problemDetail.recallStateStable')
    return t('problemDetail.recallStateScheduled')
  }

  const formatRecommendedAction = (action: string | undefined | null) => {
    if (action === 'revisit_workspace') return t('problemDetail.reviewActionRevisitWorkspace')
    if (action === 'reinforce_soon') return t('problemDetail.reviewActionReinforceSoon')
    if (action === 'keep_spacing') return t('problemDetail.reviewActionKeepSpacing')
    if (action === 'extend_or_compare') return t('problemDetail.reviewActionExtendOrCompare')
    return t('problemDetail.reviewActionCompleteFirstRecall')
  }

  const formatLearningMode = (mode: string | undefined | null) => {
    return mode === 'exploration'
      ? t('problemDetail.modeExploration')
      : t('problemDetail.modeSocratic')
  }

  const formatLearningPathKind = (kind: string | undefined | null) => {
    if (kind === 'prerequisite') return t('problemDetail.pathKindPrerequisite')
    if (kind === 'comparison') return t('problemDetail.pathKindComparison')
    if (kind === 'branch') return t('problemDetail.pathKindBranch')
    return t('problemDetail.pathKindMain')
  }

  const formatCandidateStatus = (status: string | undefined | null) => {
    if (status === 'accepted') return t('problemDetail.conceptStatusAccepted')
    if (status === 'rejected') return t('problemDetail.conceptStatusRejected')
    if (status === 'reverted') return t('problemDetail.conceptStatusReverted')
    if (status === 'postponed') return t('problemDetail.conceptStatusPostponed')
    if (status === 'merged') return t('problemDetail.conceptStatusMerged')
    return t('problemDetail.conceptStatusPending')
  }

  const formatCandidateSource = (source: string | undefined | null) => {
    if (source === 'problem_inline_qa' || source === 'ask') return t('problemDetail.derivedConceptSourceAsk')
    if (source === 'problem_response' || source === 'response') return t('problemDetail.derivedConceptSourceResponse')
    return source || t('problemDetail.derivedConceptSourceUnknown')
  }

  const formatQuestionKind = (kind: string | undefined | null) => {
    return kind === 'checkpoint'
      ? t('problemDetail.questionKindCheckpoint')
      : t('problemDetail.questionKindProbe')
  }

  const formatAnswerType = (answerType: string | undefined | null) => {
    if (answerType === 'boundary_clarification') return t('problemDetail.answerTypeBoundaryClarification')
    if (answerType === 'misconception_correction') return t('problemDetail.answerTypeMisconceptionCorrection')
    if (answerType === 'comparison') return t('problemDetail.answerTypeComparison')
    if (answerType === 'prerequisite_explanation') return t('problemDetail.answerTypePrerequisiteExplanation')
    if (answerType === 'worked_example') return t('problemDetail.answerTypeWorkedExample')
    return t('problemDetail.answerTypeConceptExplanation')
  }

  const workspacePathSummary = computed(() => {
    if (!learningPath.value) return t('problemDetail.noLearningPath')
    const label = `${formatLearningPathKind(learningPath.value.kind)} · ${learningPath.value.title || t('problemDetail.unnamedPath')}`
    if (!totalSteps.value) return label
    return `${label} · ${t('problemDetail.stepIndicator', { current: currentStepNumber.value, total: totalSteps.value })}`
  })

  const workspaceTurnSummary = computed(() => {
    if (!latestResponse.value && !latestQA.value) {
      return t('problemDetail.workspaceTurnEmpty')
    }
    if (!latestDerivedConceptCount.value && !latestPathArtifacts.value.length && latestFeedback.value?.mastery_score !== undefined) {
      return t('problemDetail.workspaceTurnMastery', { score: latestFeedback.value.mastery_score })
    }
    if (!latestDerivedConceptCount.value && !latestPathArtifacts.value.length) {
      return t('problemDetail.workspaceTurnEmpty')
    }
    return t('problemDetail.workspaceTurnSummary', {
      concepts: latestDerivedConceptCount.value,
      paths: latestPathArtifacts.value.length,
    })
  })

  const conceptMergeTargets = computed(() => {
    const values = [
      ...(problem.value?.associated_concepts || []),
      ...conceptCandidates.value
        .filter((candidate) => ['accepted', 'merged'].includes(candidate.status))
        .map((candidate) => candidate.merged_into_concept || candidate.concept_text),
    ]
    const seen = new Set<string>()
    return values.filter((item) => {
      const key = String(item || '').trim().toLowerCase()
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
  })

  const scheduledReviewsByModelCardId = computed(() => {
    return Object.fromEntries(
      scheduledReviews.value.map((schedule: any) => [String(schedule.model_card_id), schedule]),
    )
  })

  const routeFocusModelCardId = computed(() => String(route.query.focus_model_card || ''))
  const routeFocusCandidateId = computed(() => String(route.query.focus_candidate || ''))
  const routeFocusTurnId = computed(() => String(route.query.focus_turn || ''))

  const problemReviewEntries = computed(() => {
    const problemId = String(route.params.id || '')
    return [...scheduledReviews.value]
      .filter((schedule: any) => String(schedule.origin?.problem_id || '') === problemId)
      .sort((left: any, right: any) => String(left.next_review_at || '').localeCompare(String(right.next_review_at || '')))
  })

  const currentTurnReviewEntries = computed(() => {
    if (!activeConceptTurnId.value) return []
    return problemReviewEntries.value.filter(
      (schedule: any) => String(schedule.origin?.source_turn_id || '') === String(activeConceptTurnId.value),
    )
  })

  const reinforcementReviewEntries = computed(() => {
    return [...problemReviewEntries.value]
      .filter((schedule: any) => Boolean(schedule.needs_reinforcement))
      .sort((left: any, right: any) => {
        const leftDate = String(left.last_reviewed_at || left.next_review_at || '')
        const rightDate = String(right.last_reviewed_at || right.next_review_at || '')
        return rightDate.localeCompare(leftDate)
      })
  })

  const activeReinforcementEntry = computed(() => {
    const routeFocusedEntry = reinforcementReviewEntries.value.find((schedule: any) => {
      if (routeFocusModelCardId.value && String(schedule.model_card_id || '') === routeFocusModelCardId.value) return true
      if (routeFocusCandidateId.value && String(schedule.reinforcement_target?.concept_candidate_id || schedule.origin?.concept_candidate_id || '') === routeFocusCandidateId.value) return true
      if (routeFocusTurnId.value && String(schedule.reinforcement_target?.source_turn_id || schedule.origin?.source_turn_id || '') === routeFocusTurnId.value) return true
      return false
    })
    if (routeFocusedEntry) return routeFocusedEntry
    return currentTurnReviewEntries.value.find((schedule: any) => Boolean(schedule.needs_reinforcement))
      || reinforcementReviewEntries.value[0]
      || null
  })

  const activeReinforcementTarget = computed(() => activeReinforcementEntry.value?.reinforcement_target || null)
  const reinforcementFocusCandidateId = computed(() => {
    const value = routeFocusCandidateId.value || String(activeReinforcementTarget.value?.concept_candidate_id || '')
    return value || null
  })
  const reinforcementFocusTurnId = computed(() => {
    const value = routeFocusTurnId.value || String(activeReinforcementTarget.value?.source_turn_id || '')
    return value || null
  })
  const reinforcementTargetPathId = computed(() => String(activeReinforcementTarget.value?.resume_path_id || ''))
  const canSwitchToReinforcementPath = computed(() => {
    return Boolean(
      reinforcementTargetPathId.value
        && String(learningPath.value?.id || '') !== reinforcementTargetPathId.value
        && allLearningPaths.value.some((path: any) => String(path.id) === reinforcementTargetPathId.value),
    )
  })

  const latestProblemReviewEntry = computed(() => problemReviewEntries.value[0] || null)
  const latestReviewedProblemEntry = computed(() => {
    return [...problemReviewEntries.value]
      .filter((schedule: any) => Boolean(schedule.last_reviewed_at))
      .sort((left: any, right: any) => String(right.last_reviewed_at || '').localeCompare(String(left.last_reviewed_at || '')))[0] || null
  })
  const recallPriorityReviewEntry = computed(() => {
    const reviewedEntries = [...problemReviewEntries.value]
      .filter((schedule: any) => Boolean(schedule.last_reviewed_at))
      .sort((left: any, right: any) => String(right.last_reviewed_at || '').localeCompare(String(left.last_reviewed_at || '')))
    return reviewedEntries.find((schedule: any) => ['fragile', 'rebuilding'].includes(schedule.recall_state))
      || reviewedEntries[0]
      || latestProblemReviewEntry.value
  })

  const pendingPathFollowUpCount = computed(() => {
    return pathCandidates.value.filter((candidate) => ['planned', 'bookmarked'].includes(candidate.status)).length
  })

  const workspaceReviewSummary = computed(() => {
    if (!problemReviewEntries.value.length) {
      return t('problemDetail.workspaceReviewEmpty')
    }
    if (recallPriorityReviewEntry.value?.recall_state === 'fragile') {
      return t('problemDetail.workspaceReviewFragile', { count: problemReviewEntries.value.length })
    }
    if (recallPriorityReviewEntry.value?.recall_state === 'rebuilding') {
      return t('problemDetail.workspaceReviewRebuilding', { count: problemReviewEntries.value.length })
    }
    if (latestReviewedProblemEntry.value?.recall_state === 'stable') {
      return t('problemDetail.workspaceReviewStable', { count: problemReviewEntries.value.length })
    }
    if (currentTurnReviewEntries.value.length) {
      return t('problemDetail.workspaceReviewCurrentTurn', { count: currentTurnReviewEntries.value.length })
    }
    return t('problemDetail.workspaceReviewScheduled', { count: problemReviewEntries.value.length })
  })

  const workspaceReviewDescription = computed(() => {
    const latest = recallPriorityReviewEntry.value
    if (!latest) {
      if (pendingPathFollowUpCount.value) {
        return t('problemDetail.workspaceReviewPathsPending', { count: pendingPathFollowUpCount.value })
      }
      return t('problemDetail.workspaceReviewEmptyHint')
    }

    const conceptLabel = latest.origin?.concept_text || latest.title || t('problemDetail.derivedConceptsTitle')
    if (latest.last_reviewed_at) {
      return t('problemDetail.workspaceReviewOutcome', {
        concept: conceptLabel,
        state: formatRecallState(latest.recall_state),
        action: formatRecommendedAction(latest.recommended_action),
        date: formatDateTime(latest.last_reviewed_at),
      })
    }
    return t('problemDetail.workspaceReviewNextRecall', {
      concept: conceptLabel,
      date: formatDateTime(latest.next_review_at),
    })
  })

  const workspaceNextAction = computed(() => {
    const recallEntry = recallPriorityReviewEntry.value
    const recallConceptLabel = recallEntry?.origin?.concept_text || recallEntry?.title || t('problemDetail.derivedConceptsTitle')
    if (recallEntry?.recommended_action === 'revisit_workspace') {
      return t('problemDetail.workspaceNextReviewRevisit', { concept: recallConceptLabel })
    }
    if (recallEntry?.recommended_action === 'reinforce_soon') {
      return t('problemDetail.workspaceNextReviewReinforce', { concept: recallConceptLabel })
    }
    if (recallEntry?.recommended_action === 'extend_or_compare' && pendingPathFollowUpCount.value) {
      return t('problemDetail.workspaceNextReviewExtend', { concept: recallConceptLabel })
    }
    if (learningMode.value === 'exploration') {
      return latestQA.value?.next_learning_actions?.[0]
        || latestQA.value?.suggested_next_focus
        || t('problemDetail.workspaceNextExplorationDefault')
    }
    return latestResponse.value?.follow_up?.question
      || socraticQuestion.value?.question
      || t('problemDetail.workspaceNextSocraticDefault')
  })

  const focusedReinforcementCandidate = computed(() => {
    if (reinforcementFocusCandidateId.value) {
      const exactCandidate = conceptCandidates.value.find(
        (candidate: any) => String(candidate.id || '') === String(reinforcementFocusCandidateId.value),
      )
      if (exactCandidate) return exactCandidate
    }

    if (reinforcementFocusTurnId.value) {
      const turnMatches = conceptCandidates.value.filter(
        (candidate: any) => String(candidate.source_turn_id || '') === String(reinforcementFocusTurnId.value),
      )
      if (turnMatches.length === 1) return turnMatches[0]

      const targetConcept = String(activeReinforcementTarget.value?.concept_text || '').trim().toLowerCase()
      const conceptMatch = turnMatches.find(
        (candidate: any) => String(candidate.concept_text || '').trim().toLowerCase() === targetConcept,
      )
      if (conceptMatch) return conceptMatch
      if (turnMatches.length) return turnMatches[0]
    }

    return null
  })

  const focusedReinforcementTurn = computed(() => {
    if (!reinforcementFocusTurnId.value) return null
    return qaHistory.value.find((turn: any) => String(turn.turn_id || '') === String(reinforcementFocusTurnId.value)) || null
  })

  const reinforcementFocusTitle = computed(() => {
    return focusedReinforcementCandidate.value?.concept_text
      || activeReinforcementTarget.value?.concept_text
      || t('problemDetail.derivedConceptsTitle')
  })

  const reinforcementFocusDescription = computed(() => {
    if (focusedReinforcementCandidate.value) {
      return t('problemDetail.reinforcementFocusCandidate', {
        status: formatCandidateStatus(focusedReinforcementCandidate.value.status),
        source: formatCandidateSource(focusedReinforcementCandidate.value.source),
      })
    }
    if (focusedReinforcementTurn.value?.answer_type) {
      return t('problemDetail.reinforcementFocusTurn', {
        answerType: formatAnswerType(focusedReinforcementTurn.value.answer_type),
      })
    }
    return t('problemDetail.reinforcementFocusFallback')
  })

  const reinforcementFocusTurnPreview = computed(() => {
    if (focusedReinforcementCandidate.value?.source_turn_preview) {
      return focusedReinforcementCandidate.value.source_turn_preview
    }
    if (activeReinforcementTarget.value?.source_turn_preview) {
      return activeReinforcementTarget.value.source_turn_preview
    }
    if (!focusedReinforcementTurn.value) return ''
    const question = String(focusedReinforcementTurn.value.question || '').trim()
    const answer = String(focusedReinforcementTurn.value.answer || '').trim()
    if (question && answer) return `${question.slice(0, 110)} -> ${answer.slice(0, 110)}`
    return question || answer
  })

  const reinforcementStarterContext = computed(() => {
    const concept = reinforcementFocusTitle.value
    const contextConcepts = uniqueContextConcepts([
      ...(focusedReinforcementTurn.value?.answered_concepts || []),
      ...(focusedReinforcementTurn.value?.related_concepts || []),
      focusedReinforcementTurn.value?.suggested_next_focus,
      focusedReinforcementTurn.value?.step_concept,
      activeReinforcementTarget.value?.resume_step_concept,
      currentStep.value?.concept,
      problem.value?.title,
    ], [concept])
    return buildReinforcementStarterContext({
      question: normalizeInlineText(focusedReinforcementTurn.value?.question || ''),
      answer: normalizeInlineText(focusedReinforcementTurn.value?.answer || ''),
      answerType: String(focusedReinforcementTurn.value?.answer_type || '').trim(),
      turnPreview: reinforcementFocusTurnPreview.value,
      contextConcepts,
    })
  })

  const reinforcementErrorHint = computed(() => {
    if (!focusedReinforcementTurn.value) return null
    return deriveReinforcementErrorHint({
      answerType: String(focusedReinforcementTurn.value.answer_type || '').trim(),
      question: normalizeInlineText(focusedReinforcementTurn.value.question || ''),
      answer: normalizeInlineText(focusedReinforcementTurn.value.answer || ''),
      questionCue: reinforcementStarterContext.value.questionCue,
      comparisonCue: reinforcementStarterContext.value.comparisonCue,
      t,
    })
  })

  const reinforcementEvidenceCue = computed(() => {
    const evidenceSnippet = String(
      focusedReinforcementCandidate.value?.evidence_snippet
        || activeReinforcementEntry.value?.origin?.evidence_snippet
        || '',
    ).trim()
    if (!evidenceSnippet) return ''

    const concept = reinforcementFocusTitle.value
    const anchor = String(
      activeReinforcementTarget.value?.resume_step_concept
        || currentStep.value?.concept
        || problem.value?.title
        || concept,
    ).trim()

    return extractEvidenceCue({
      evidenceSnippet,
      concept,
      sourceCue: reinforcementStarterContext.value.primaryCue,
      sourceClue: reinforcementStarterContext.value.answerCue,
      likelyConfusion: reinforcementErrorHint.value?.text || '',
      anchor,
    })
  })

  const reinforcementActionTemplate = computed(() => {
    const concept = reinforcementFocusTitle.value
    const anchor = String(
      activeReinforcementTarget.value?.resume_step_concept
        || currentStep.value?.concept
        || problem.value?.title
        || concept,
    ).trim()
    const originMode = String(activeReinforcementEntry.value?.origin?.learning_mode || learningMode.value || 'socratic').trim()
    const sourceCue = reinforcementStarterContext.value.primaryCue
    return buildReinforcementActionTemplate({
      activeReinforcementEntry: activeReinforcementEntry.value,
      activeReinforcementTarget: activeReinforcementTarget.value,
      focusedTurnAnswerType: String(focusedReinforcementTurn.value?.answer_type || '').trim(),
      originMode,
      concept,
      anchor,
      comparisonCue: reinforcementStarterContext.value.comparisonCue,
      sourceCue,
      sourceClue: reinforcementStarterContext.value.answerCue,
      likelyConfusion: reinforcementErrorHint.value?.text || '',
      evidenceCue: reinforcementEvidenceCue.value,
      t,
    })
  })

  const formatReinforcementResume = (target: any) => {
    const rawStepIndex = Number(target?.resume_step_index)
    const hasStepIndex = Number.isFinite(rawStepIndex)
    const stepNumber = hasStepIndex ? rawStepIndex + 1 : null
    const stepConcept = String(target?.resume_step_concept || '').trim()

    if (stepNumber !== null && stepConcept) {
      return t('problemDetail.reinforcementResumeStepConcept', {
        step: stepNumber,
        concept: stepConcept,
      })
    }
    if (stepNumber !== null) {
      return t('problemDetail.reinforcementResumeStepOnly', { step: stepNumber })
    }
    if (stepConcept) {
      return t('problemDetail.reinforcementResumeConcept', { concept: stepConcept })
    }
    return t('problemDetail.reinforcementResumeCurrentWorkspace')
  }

  const hasReinforcementPath = (target: any) => {
    return Boolean(target?.resume_path_id || target?.resume_path_kind || target?.resume_path_title)
  }

  const formatReinforcementPath = (target: any) => {
    const title = String(target?.resume_path_title || '').trim()
    const kind = String(target?.resume_path_kind || '').trim()
    const kindLabel = kind ? formatLearningPathKind(kind) : ''
    if (kindLabel && title) return `${kindLabel} · ${title}`
    if (title) return title
    if (kindLabel) return kindLabel
    return t('problemDetail.reinforcementResumeCurrentWorkspace')
  }

  const formatReinforcementSummary = (entry: any) => {
    const target = entry?.reinforcement_target || {}
    const conceptLabel = target.concept_text || entry?.origin?.concept_text || entry?.title || t('problemDetail.derivedConceptsTitle')
    return t('problemDetail.reinforcementSummary', {
      concept: conceptLabel,
      state: formatRecallState(entry?.recall_state),
      action: formatRecommendedAction(entry?.recommended_action),
    })
  }

  return {
    workspacePathSummary,
    workspaceTurnSummary,
    workspaceNextAction,
    workspaceReviewSummary,
    workspaceReviewDescription,
    conceptMergeTargets,
    scheduledReviewsByModelCardId,
    activeReinforcementEntry,
    activeReinforcementTarget,
    reinforcementFocusCandidateId,
    reinforcementFocusTurnId,
    reinforcementTargetPathId,
    canSwitchToReinforcementPath,
    reinforcementFocusTitle,
    reinforcementFocusDescription,
    reinforcementFocusTurnPreview,
    reinforcementActionTemplate,
    formatConfidence,
    formatRecommendedAction,
    formatReinforcementResume,
    hasReinforcementPath,
    formatReinforcementPath,
    formatReinforcementSummary,
    formatLearningMode,
    formatLearningPathKind,
    formatQuestionKind,
    formatAnswerType,
  }
}
