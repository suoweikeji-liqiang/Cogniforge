<template>
  <div class="problem-detail" data-testid="problem-detail-workspace">
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <template v-else-if="problem">
      <div class="problem-header">
        <router-link to="/problems" class="back-link">&larr; {{ t('common.back') }}</router-link>
        <h1>{{ problem.title }}</h1>
        <p>{{ problem.description }}</p>
        <div class="problem-meta">
          <span class="status" :class="problem.status">{{ problem.status }}</span>
          <span class="mode-badge">{{ t('problemDetail.currentMode') }}: {{ formatLearningMode(learningMode) }}</span>
          <span v-if="totalSteps" class="progress-text">
            {{ t('problemDetail.progress') }}: {{ completedSteps }}/{{ totalSteps }}
          </span>
        </div>
      </div>

      <div class="problem-content">
        <section class="card mode-switch-section">
          <h2>{{ t('problemDetail.modeSwitchTitle') }}</h2>
          <p class="section-subtitle">
            {{ learningMode === 'socratic' ? t('problemDetail.modeSocraticHint') : t('problemDetail.modeExplorationHint') }}
          </p>
          <div class="workspace-mode-toggle">
            <button
              type="button"
              class="btn btn-secondary"
              :class="{ active: learningMode === 'socratic' }"
              :disabled="switchingMode || submitting || askingQuestion"
              data-testid="mode-switch-socratic"
              @click="setLearningMode('socratic')"
            >
              {{ t('problemDetail.modeSocratic') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              :class="{ active: learningMode === 'exploration' }"
              :disabled="switchingMode || submitting || askingQuestion"
              data-testid="mode-switch-exploration"
              @click="setLearningMode('exploration')"
            >
              {{ t('problemDetail.modeExploration') }}
            </button>
          </div>
        </section>

        <section class="card current-step-section">
          <h2>{{ t('problemDetail.currentStepTitle') }}</h2>
          <div v-if="totalSteps" class="progress-overview">
            <span>{{ t('problemDetail.stepIndicator', { current: currentStepNumber, total: totalSteps }) }}</span>
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: `${progressPercent}%` }"></div>
            </div>
          </div>

          <div v-if="learningPath" class="path-structure-panel" data-testid="current-learning-path">
            <div class="path-structure-head">
              <span class="mode-badge">{{ t('problemDetail.currentPath') }}: {{ formatLearningPathKind(learningPath.kind) }}</span>
              <span class="candidate-status">{{ learningPath.title || t('problemDetail.unnamedPath') }}</span>
              <span
                v-if="learningPath.parent_path_id && learningPath.return_step_id !== null && learningPath.return_step_id !== undefined"
                class="candidate-source"
              >
                {{ t('problemDetail.returnStepLabel', { step: learningPath.return_step_id + 1 }) }}
              </span>
            </div>
            <p v-if="learningPath.branch_reason" class="section-subtitle">{{ learningPath.branch_reason }}</p>
            <div v-if="allLearningPaths.length > 1" class="path-nav-list">
              <button
                v-for="path in allLearningPaths"
                :key="path.id"
                type="button"
                class="btn btn-secondary path-nav-button"
                :class="{ active: path.is_active }"
                :disabled="updatingPath"
                data-testid="learning-path-button"
                @click="activateLearningPathById(path.id)"
              >
                {{ formatLearningPathKind(path.kind) }} · {{ path.title || t('problemDetail.unnamedPath') }}
              </button>
            </div>
            <button
              v-if="canReturnToParent"
              type="button"
              class="btn btn-secondary"
              :disabled="updatingPath"
              data-testid="return-to-parent-path"
              @click="returnToParentPath"
            >
              {{ t('problemDetail.returnToParentPath') }}
            </button>
          </div>

          <div v-if="currentStep" class="step-card">
            <div class="step-number">{{ currentStepNumber }}</div>
            <div class="step-content">
              <h3>{{ currentStep.concept }}</h3>
              <p>{{ currentStep.description }}</p>
              <ul v-if="currentStep.resources?.length" class="resources">
                <li v-for="resource in currentStep.resources" :key="resource">{{ resource }}</li>
              </ul>
            </div>
          </div>
          <div v-else-if="isPathCompleted && totalSteps" class="completion-banner">
            {{ t('problemDetail.completedAll') }}
          </div>
          <p v-else class="empty">{{ t('problemDetail.noLearningPath') }}</p>

          <div v-if="totalSteps" class="path-actions">
            <button
              type="button"
              class="btn btn-secondary"
              :disabled="updatingPath || completedSteps === 0"
              @click="updateCurrentStep(completedSteps - 1)"
            >
              {{ t('problemDetail.previousStep') }}
            </button>
            <button
              v-if="!isPathCompleted"
              type="button"
              class="btn btn-primary"
              :disabled="updatingPath"
              data-testid="mark-step-done"
              @click="updateCurrentStep(completedSteps + 1)"
            >
              {{ t('problemDetail.markStepDone') }}
            </button>
            <span v-else class="completed-badge">{{ t('problemDetail.completed') }}</span>
          </div>

          <details v-if="completedStepList.length" class="completed-panel">
            <summary>{{ t('problemDetail.completedStepsTitle', { count: completedStepList.length }) }}</summary>
            <div class="completed-list">
              <div v-for="(step, index) in completedStepList" :key="`${step.concept}-${index}`" class="completed-item">
                <span class="completed-index">{{ index + 1 }}</span>
                <div>
                  <strong>{{ step.concept }}</strong>
                  <p>{{ step.description }}</p>
                </div>
              </div>
            </div>
          </details>
        </section>

        <section v-if="learningMode === 'socratic'" class="card responses-section">
          <h2>{{ t('problemDetail.progressSectionTitle') }}</h2>
          <p class="section-subtitle" v-if="currentStep">{{ t('problemDetail.progressForStep', { concept: currentStep.concept }) }}</p>
          <div class="workspace-stage">
            <div class="workspace-main-column">

              <div v-if="socraticQuestion" class="socratic-question-panel" data-testid="socratic-question-panel">
                <div class="question-head">
                  <strong>{{ t('problemDetail.currentQuestionTitle') }}</strong>
                  <span class="question-kind-badge">{{ formatQuestionKind(socraticQuestion.question_kind) }}</span>
                </div>
                <p class="question-copy">{{ socraticQuestion.question }}</p>
              </div>

              <form @submit.prevent="submitResponse" class="response-form">
                <div class="form-group">
                  <label>{{ t('problemDetail.progressInputLabel') }}</label>
                  <textarea
                    v-model="responseText"
                    rows="5"
                    :placeholder="t('problemDetail.progressInputPlaceholder')"
                    data-testid="socratic-response-input"
                    required
                  ></textarea>
                </div>
                <div class="response-actions">
                  <button type="button" class="btn btn-secondary" :disabled="hintLoading || submitting" @click="prefillGuidedTemplate">
                    {{ hintLoading ? t('common.loading') : t('problemDetail.needPrompt') }}
                  </button>
                  <button type="submit" class="btn btn-primary" :disabled="submitting" data-testid="submit-socratic-response">
                    {{ submitting ? t('common.loading') : t('problemDetail.submitProgress') }}
                  </button>
                </div>
              </form>
              <p v-if="autoAdvanceMessage" class="auto-advance-notice">{{ autoAdvanceMessage }}</p>
              <div v-if="canUndoAutoAdvance" class="undo-auto-wrap">
                <button type="button" class="btn btn-secondary" :disabled="updatingPath" @click="undoAutoAdvance">
                  {{ t('problemDetail.undoAutoAdvance') }}
                </button>
              </div>

              <div v-if="stepHint" class="hint-panel">
                <h3>{{ t('problemDetail.hintTitle') }}</h3>
                <p v-if="stepHint.focus"><strong>{{ t('problemDetail.hintFocus') }}:</strong> {{ stepHint.focus }}</p>
                <ul v-if="stepHint.next_actions?.length">
                  <li v-for="(item, idx) in stepHint.next_actions" :key="`${idx}-${item}`">{{ item }}</li>
                </ul>
                <p v-if="stepHint.starter"><strong>{{ t('problemDetail.hintStarter') }}:</strong> {{ stepHint.starter }}</p>
              </div>

              <details v-if="responses.length" class="history-panel">
                <summary>{{ t('problemDetail.historyTitle', { count: responses.length }) }}</summary>
                <div class="responses-list">
                  <div v-for="response in responses" :key="response.id" class="response-item">
                    <div class="user-response">
                      <p class="mode-line">
                        <strong>{{ t('problemDetail.currentMode') }}:</strong> {{ formatLearningMode(response.learning_mode) }}
                      </p>
                      <p v-if="response.question_kind" class="mode-line">
                        <strong>{{ t('problemDetail.questionKind') }}:</strong> {{ formatQuestionKind(response.question_kind) }}
                      </p>
                      <p v-if="response.socratic_question" class="mode-line">
                        <strong>{{ t('problemDetail.questionLabel') }}:</strong> {{ response.socratic_question }}
                      </p>
                      <strong>{{ t('problemDetail.myProgressRecord') }}:</strong>
                      <p>{{ response.user_response }}</p>
                    </div>
                    <div v-if="response.structured_feedback" class="history-feedback">
                      <p v-if="response.structured_feedback.correctness">
                        <strong>{{ t('feedback.correctness') }}:</strong> {{ response.structured_feedback.correctness }}
                      </p>
                      <p v-if="response.structured_feedback.mastery_score !== undefined">
                        <strong>{{ t('problemDetail.masteryScore') }}:</strong> {{ response.structured_feedback.mastery_score }}
                        · <strong>{{ t('problemDetail.confidence') }}:</strong> {{ formatConfidence(response.structured_feedback.confidence) }}
                      </p>
                      <p v-if="response.structured_feedback.suggestions?.length">
                        <strong>{{ t('feedback.suggestions') }}:</strong> {{ response.structured_feedback.suggestions.join(' / ') }}
                      </p>
                      <p v-if="response.structured_feedback.next_question">
                        <strong>{{ t('feedback.nextQuestion') }}:</strong> {{ response.structured_feedback.next_question }}
                      </p>
                      <p v-if="response.accepted_concepts?.length">
                        <strong>{{ t('problemDetail.newConceptsTitle') }}:</strong> {{ response.accepted_concepts.join(' / ') }}
                      </p>
                      <p v-if="response.pending_concepts?.length">
                        <strong>{{ t('problemDetail.pendingConceptsTitle') }}:</strong> {{ response.pending_concepts.join(' / ') }}
                      </p>
                      <p v-if="response.trace_id || response.llm_calls !== undefined" class="ops-meta-line">
                        <strong>{{ t('problemDetail.traceId') }}:</strong> {{ response.trace_id || '-' }}
                        · <strong>{{ t('problemDetail.llmCalls') }}:</strong> {{ response.llm_calls ?? '-' }}
                        · <strong>{{ t('problemDetail.llmLatencyMs') }}:</strong> {{ response.llm_latency_ms ?? '-' }}
                      </p>
                    </div>
                  </div>
                </div>
              </details>
              <p v-else class="empty">{{ t('problemDetail.noProgressRecords') }}</p>
            </div>
            <div class="workspace-side-column workspace-side-stack">
              <ProblemTurnOutcomePanel
                :learning-mode="learningMode"
                :latest-response="latestResponse"
                :latest-feedback="latestFeedback"
                :latest-qa="latestQA"
              />
              <ProblemDerivedConceptsPanel
                :candidates="conceptCandidates"
                :loading="candidateLoading"
                :current-turn-id="activeConceptTurnId"
                :merge-targets="conceptMergeTargets"
                :action-pending-id="candidateSubmittingId"
                :handoff-pending-id="handoffSubmittingId"
                :scheduled-model-card-ids="scheduledModelCardIds"
                @accept="acceptCandidate"
                @reject="rejectCandidate"
                @postpone="postponeCandidate"
                @merge="mergeCandidate"
                @rollback="rollbackConcept"
                @promote="promoteCandidateToModelCard"
                @open-card="openModelCard"
                @schedule-review="scheduleCandidateReview"
              />
            </div>
          </div>
        </section>

        <section class="card concept-governance-section" data-testid="path-candidates-panel">
          <h2>{{ t('problemDetail.pathCandidatesTitle') }}</h2>
          <p class="section-subtitle">{{ t('problemDetail.pathCandidatesSubtitle') }}</p>

          <div v-if="pathCandidateLoading" class="loading">{{ t('common.loading') }}</div>
          <p v-else-if="!pathCandidates.length" class="empty">{{ t('problemDetail.noPathCandidates') }}</p>
          <div v-else class="candidate-list">
            <div
              v-for="candidate in pathCandidates"
              :key="candidate.id"
              class="candidate-item"
              :class="`candidate-${candidate.status}`"
              data-testid="path-candidate-card"
            >
              <div class="candidate-head">
                <strong>{{ candidate.title }}</strong>
                <span class="candidate-status">{{ formatPathCandidateStatus(candidate.status) }}</span>
                <span class="candidate-source">{{ formatLearningMode(candidate.learning_mode) }}</span>
                <span class="candidate-source">{{ formatPathSuggestionType(candidate.type) }}</span>
              </div>
              <p v-if="candidate.reason" class="candidate-evidence">{{ candidate.reason }}</p>
              <p class="mode-line">
                <strong>{{ t('problemDetail.pathCandidateRecommendedInsertion') }}:</strong>
                {{ formatInsertionBehavior(candidate.recommended_insertion) }}
              </p>
              <p v-if="candidate.selected_insertion" class="mode-line">
                <strong>{{ t('problemDetail.pathCandidateChosenInsertion') }}:</strong>
                {{ formatInsertionBehavior(candidate.selected_insertion) }}
              </p>
              <div v-if="candidate.status !== 'dismissed'" class="candidate-actions">
                <button
                  type="button"
                  class="btn btn-primary"
                  :disabled="pathCandidateSubmittingId === candidate.id"
                  data-testid="path-candidate-insert-main"
                  @click="decidePathCandidate(candidate.id, 'insert_before_current_main')"
                >
                  {{ t('problemDetail.pathCandidateInsertBeforeCurrent') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="pathCandidateSubmittingId === candidate.id"
                  data-testid="path-candidate-save-branch"
                  @click="decidePathCandidate(candidate.id, 'save_as_side_branch')"
                >
                  {{ t('problemDetail.pathCandidateSaveAsBranch') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="pathCandidateSubmittingId === candidate.id"
                  data-testid="path-candidate-bookmark"
                  @click="decidePathCandidate(candidate.id, 'bookmark_for_later')"
                >
                  {{ t('problemDetail.pathCandidateBookmark') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="pathCandidateSubmittingId === candidate.id"
                  data-testid="path-candidate-dismiss"
                  @click="decidePathCandidate(candidate.id, 'dismiss')"
                >
                  {{ t('problemDetail.pathCandidateDismiss') }}
                </button>
              </div>
            </div>
          </div>
        </section>

        <section v-if="learningMode === 'exploration'" class="card qa-section">
          <h2>{{ t('problemDetail.askTitle') }}</h2>
          <p class="section-subtitle">{{ t('problemDetail.askSubtitle') }}</p>
          <div class="workspace-stage">
            <div class="workspace-main-column">

              <div class="ask-mode-toggle">
                <button
                  type="button"
                  class="btn btn-secondary"
                  :class="{ active: answerMode === 'direct' }"
                  :disabled="askingQuestion"
                  data-testid="exploration-answer-mode-direct"
                  @click="answerMode = 'direct'"
                >
                  {{ t('problemDetail.askModeDirect') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :class="{ active: answerMode === 'guided' }"
                  :disabled="askingQuestion"
                  data-testid="exploration-answer-mode-guided"
                  @click="answerMode = 'guided'"
                >
                  {{ t('problemDetail.askModeGuided') }}
                </button>
              </div>

              <form @submit.prevent="askLearningQuestion" class="response-form">
                <div class="form-group">
                  <label>{{ t('problemDetail.askInputLabel') }}</label>
                  <textarea
                    v-model="learningQuestion"
                    rows="3"
                    :placeholder="t('problemDetail.askInputPlaceholder')"
                    data-testid="exploration-question-input"
                    required
                  ></textarea>
                </div>
                <button type="submit" class="btn btn-primary" :disabled="askingQuestion || !learningQuestion.trim()" data-testid="submit-exploration-question">
                  {{ askingQuestion ? t('common.loading') : t('problemDetail.askSubmit') }}
                </button>
              </form>

              <details v-if="qaHistory.length" class="history-panel">
                <summary>{{ t('problemDetail.qaHistoryTitle', { count: qaHistory.length }) }}</summary>
                <div class="responses-list">
                  <div v-for="(item, index) in qaHistory" :key="`${index}-${item.question}`" class="response-item">
                    <p class="mode-line">
                      <strong>{{ t('problemDetail.currentMode') }}:</strong> {{ formatLearningMode(item.learning_mode) }}
                    </p>
                    <p v-if="item.answer_type" class="mode-line">
                      <strong>{{ t('problemDetail.answerType') }}:</strong> {{ formatAnswerType(item.answer_type) }}
                    </p>
                    <div class="qa-block">
                      <strong>{{ t('problemDetail.questionLabel') }}</strong>
                      <p>{{ item.question }}</p>
                    </div>
                    <div class="qa-block">
                      <strong>{{ t('problemDetail.answerLabel') }}</strong>
                      <p>{{ item.answer }}</p>
                    </div>
                  </div>
                </div>
              </details>
            </div>
            <div class="workspace-side-column workspace-side-stack">
              <ProblemTurnOutcomePanel
                :learning-mode="learningMode"
                :latest-response="latestResponse"
                :latest-feedback="latestFeedback"
                :latest-qa="latestQA"
              />
              <ProblemDerivedConceptsPanel
                :candidates="conceptCandidates"
                :loading="candidateLoading"
                :current-turn-id="activeConceptTurnId"
                :merge-targets="conceptMergeTargets"
                :action-pending-id="candidateSubmittingId"
                :handoff-pending-id="handoffSubmittingId"
                :scheduled-model-card-ids="scheduledModelCardIds"
                @accept="acceptCandidate"
                @reject="rejectCandidate"
                @postpone="postponeCandidate"
                @merge="mergeCandidate"
                @rollback="rollbackConcept"
                @promote="promoteCandidateToModelCard"
                @open-card="openModelCard"
                @schedule-review="scheduleCandidateReview"
              />
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useI18n } from 'vue-i18n'
import ProblemTurnOutcomePanel from '@/components/problem-workspace/ProblemTurnOutcomePanel.vue'
import ProblemDerivedConceptsPanel from '@/components/problem-workspace/ProblemDerivedConceptsPanel.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const problem = ref<any>(null)
const learningPath = ref<any>(null)
const allLearningPaths = ref<any[]>([])
const responses = ref<any[]>([])
const learningMode = ref<'socratic' | 'exploration'>('socratic')
const loading = ref(true)
const submitting = ref(false)
const updatingPath = ref(false)
const switchingMode = ref(false)
const hintLoading = ref(false)
const responseText = ref('')
const autoAdvanceMessage = ref('')
const canUndoAutoAdvance = ref(false)
const undoTargetStep = ref<number | null>(null)
const stepHint = ref<any | null>(null)
const socraticQuestion = ref<any | null>(null)
const learningQuestion = ref('')
const askingQuestion = ref(false)
const answerMode = ref<'direct' | 'guided'>('direct')
const qaHistory = ref<any[]>([])
const conceptCandidates = ref<any[]>([])
const pathCandidates = ref<any[]>([])
const candidateLoading = ref(false)
const candidateSubmittingId = ref<string | null>(null)
const handoffSubmittingId = ref<string | null>(null)
const pathCandidateLoading = ref(false)
const pathCandidateSubmittingId = ref<string | null>(null)
const scheduledModelCardIds = ref<string[]>([])
const latestQA = computed(() => qaHistory.value[0] || null)

const totalSteps = computed(() => learningPath.value?.path_data?.length || 0)
const completedSteps = computed(() => learningPath.value?.current_step || 0)
const isPathCompleted = computed(() => totalSteps.value > 0 && completedSteps.value >= totalSteps.value)
const canReturnToParent = computed(() => Boolean(learningPath.value?.parent_path_id))
const currentStep = computed(() => {
  if (!learningPath.value?.path_data?.length || isPathCompleted.value) return null
  return learningPath.value.path_data[completedSteps.value] || null
})
const currentStepNumber = computed(() => {
  if (isPathCompleted.value) return totalSteps.value
  return Math.min(completedSteps.value + 1, totalSteps.value || 1)
})
const progressPercent = computed(() => {
  if (!totalSteps.value) return 0
  return Math.round((completedSteps.value / totalSteps.value) * 100)
})
const completedStepList = computed(() => (learningPath.value?.path_data || []).slice(0, completedSteps.value))
const latestResponse = computed(() => responses.value[responses.value.length - 1] || null)
const latestFeedback = computed(() => latestResponse.value?.structured_feedback || null)
const activeConceptTurnId = computed(() => {
  if (learningMode.value === 'exploration') {
    return latestQA.value?.turn_id || null
  }
  return latestResponse.value?.turn_id || null
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

const formatConfidence = (value: number | string | undefined | null) => {
  const parsed = Number(value ?? 0)
  if (!Number.isFinite(parsed)) return '0%'
  const percent = Math.round(Math.max(0, Math.min(1, parsed)) * 100)
  return `${percent}%`
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

const formatPathSuggestionType = (pathType: string | undefined | null) => {
  if (pathType === 'prerequisite') return t('problemDetail.pathSuggestionPrerequisite')
  if (pathType === 'comparison_path') return t('problemDetail.pathSuggestionComparisonPath')
  return t('problemDetail.pathSuggestionBranchDeepDive')
}

const formatPathCandidateStatus = (status: string | undefined | null) => {
  if (status === 'planned') return t('problemDetail.pathCandidateStatusPlanned')
  if (status === 'bookmarked') return t('problemDetail.pathCandidateStatusBookmarked')
  if (status === 'dismissed') return t('problemDetail.pathCandidateStatusDismissed')
  return t('problemDetail.pathCandidateStatusPending')
}

const formatInsertionBehavior = (action: string | undefined | null) => {
  if (action === 'insert_before_current_main') return t('problemDetail.insertionInsertBeforeCurrentMain')
  if (action === 'save_as_side_branch') return t('problemDetail.insertionSaveAsSideBranch')
  return t('problemDetail.insertionBookmarkForLater')
}

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
    const response = await api.get(`/problems/${route.params.id}/turns`, {
      params: { learning_mode: 'exploration' },
    })
    qaHistory.value = (response.data || []).map(normalizeExplorationTurn)
  } catch (e) {
    console.error('Failed to fetch exploration turns:', e)
    qaHistory.value = []
  }
}

const fetchSocraticQuestion = async () => {
  try {
    const response = await api.get(`/problems/${route.params.id}/socratic-question`)
    socraticQuestion.value = response.data || null
  } catch (e) {
    console.error('Failed to fetch socratic question:', e)
    socraticQuestion.value = null
  }
}

const fetchConceptCandidates = async () => {
  candidateLoading.value = true
  try {
    const response = await api.get(`/problems/${route.params.id}/concept-candidates`)
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
    const response = await api.get(`/problems/${route.params.id}/path-candidates`)
    pathCandidates.value = response.data || []
  } catch (e) {
    console.error('Failed to fetch path candidates:', e)
    pathCandidates.value = []
  } finally {
    pathCandidateLoading.value = false
  }
}

const fetchReviewSchedules = async () => {
  try {
    const response = await api.get('/srs/schedules')
    scheduledModelCardIds.value = (response.data || []).map((schedule: any) => String(schedule.model_card_id))
  } catch (e) {
    console.error('Failed to fetch review schedules:', e)
    scheduledModelCardIds.value = []
  }
}

const fetchLearningPath = async () => {
  const pathRes = await api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null }))
  learningPath.value = pathRes.data
}

const fetchLearningPaths = async () => {
  const response = await api.get(`/problems/${route.params.id}/learning-paths`).catch(() => ({ data: [] }))
  allLearningPaths.value = response.data || []
}

const fetchProblem = async () => {
  try {
    const [problemRes, pathRes, pathListRes, responsesRes, candidatesRes, pathCandidatesRes, turnsRes, socraticRes, schedulesRes] = await Promise.all([
      api.get(`/problems/${route.params.id}`),
      api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null })),
      api.get(`/problems/${route.params.id}/learning-paths`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/responses`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/concept-candidates`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/path-candidates`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/turns`, {
        params: { learning_mode: 'exploration' },
      }).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/socratic-question`).catch(() => ({ data: null })),
      api.get('/srs/schedules').catch(() => ({ data: [] })),
    ])

    problem.value = problemRes.data
    learningMode.value = problemRes.data?.learning_mode || 'socratic'
    learningPath.value = pathRes.data
    allLearningPaths.value = pathListRes.data || []
    responses.value = responsesRes.data
    conceptCandidates.value = candidatesRes.data || []
    pathCandidates.value = pathCandidatesRes.data || []
    qaHistory.value = (turnsRes.data || []).map(normalizeExplorationTurn)
    socraticQuestion.value = socraticRes.data || null
    scheduledModelCardIds.value = (schedulesRes.data || []).map((schedule: any) => String(schedule.model_card_id))
  } catch (e) {
    console.error('Failed to fetch problem:', e)
  } finally {
    loading.value = false
  }
}

const setLearningMode = async (mode: 'socratic' | 'exploration') => {
  if (switchingMode.value || learningMode.value === mode) return

  const previousMode = learningMode.value
  learningMode.value = mode
  if (problem.value) {
    problem.value.learning_mode = mode
  }

  switchingMode.value = true
  try {
    await api.put(`/problems/${route.params.id}`, { learning_mode: mode })
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

  try {
    const response = await api.post(`/problems/${route.params.id}/responses`, {
      problem_id: route.params.id,
      user_response: responseText.value,
      learning_mode: learningMode.value,
      question_kind: socraticQuestion.value?.question_kind,
      socratic_question: socraticQuestion.value?.question,
    })
    responses.value.push(response.data)
    await Promise.all([
      fetchConceptCandidates(),
      fetchPathCandidates(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
    responseText.value = ''
    if (response.data?.auto_advanced) {
      await fetchLearningPath()
      autoAdvanceMessage.value = t('problemDetail.autoAdvanced')
      canUndoAutoAdvance.value = true
      const suggestedUndo = Number(response.data?.new_current_step ?? 0) - 1
      undoTargetStep.value = Number.isFinite(suggestedUndo) ? Math.max(0, suggestedUndo) : null
      if (problem.value && problem.value.status === 'new') {
        problem.value.status = 'in-progress'
      }
    } else {
      autoAdvanceMessage.value = ''
      canUndoAutoAdvance.value = false
      undoTargetStep.value = null
    }

    if (problem.value?.status === 'new' && !response.data?.auto_advanced) {
      problem.value.status = 'in-progress'
    }
    await fetchSocraticQuestion()
  } catch (e) {
    console.error('Failed to submit response:', e)
  } finally {
    submitting.value = false
  }
}

const updateCurrentStep = async (nextStep: number) => {
  if (!learningPath.value) return

  updatingPath.value = true
  try {
    const response = await api.put(`/problems/${route.params.id}/learning-path`, {
      current_step: nextStep,
    })
    learningPath.value = response.data
    await fetchLearningPaths()
    if (learningMode.value === 'socratic') {
      await fetchSocraticQuestion()
    }

    if (problem.value) {
      if (totalSteps.value > 0 && nextStep >= totalSteps.value) {
        problem.value.status = 'completed'
      } else if (nextStep > 0) {
        problem.value.status = 'in-progress'
      } else {
        problem.value.status = 'new'
      }
    }
  } catch (e) {
    console.error('Failed to update learning path:', e)
  } finally {
    updatingPath.value = false
  }
}

const prefillGuidedTemplate = () => {
  const buildLocalGuidedTemplate = () => {
    const concept = currentStep.value?.concept || problem.value?.title || ''
    return [
      t('problemDetail.guidedLine1', { concept }),
      t('problemDetail.guidedLine2'),
      t('problemDetail.guidedLine3'),
    ].join('\n')
  }

  hintLoading.value = true
  api.get(`/problems/${route.params.id}/learning-path/hint`)
    .then((response) => {
      stepHint.value = response.data?.structured_hint || null
      const starter = response.data?.structured_hint?.starter?.trim()
      if (starter) {
        responseText.value = `${starter}\n`
      } else {
        responseText.value = response.data?.hint?.trim() || buildLocalGuidedTemplate()
      }
    })
    .catch((e) => {
      console.error('Failed to fetch learning hint:', e)
      stepHint.value = null
      responseText.value = buildLocalGuidedTemplate()
    })
    .finally(() => {
      hintLoading.value = false
    })
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

const askLearningQuestion = async () => {
  if (!learningQuestion.value.trim() || askingQuestion.value) return

  askingQuestion.value = true
  try {
    await api.post(`/problems/${route.params.id}/ask`, {
      question: learningQuestion.value.trim(),
      learning_mode: learningMode.value,
      answer_mode: answerMode.value,
    })
    await Promise.all([
      fetchConceptCandidates(),
      fetchPathCandidates(),
      fetchExplorationTurns(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
    learningQuestion.value = ''
  } catch (e) {
    console.error('Failed to ask learning question:', e)
  } finally {
    askingQuestion.value = false
  }
}

const acceptCandidate = async (candidateId: string) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/accept`)
    await Promise.all([
      fetchConceptCandidates(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
  } catch (e) {
    console.error('Failed to accept concept candidate:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const rejectCandidate = async (candidateId: string) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/reject`)
    await fetchConceptCandidates()
  } catch (e) {
    console.error('Failed to reject concept candidate:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const postponeCandidate = async (candidateId: string) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/postpone`)
    await fetchConceptCandidates()
  } catch (e) {
    console.error('Failed to postpone concept candidate:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const mergeCandidate = async ({ candidateId, targetConcept }: { candidateId: string; targetConcept: string }) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/merge`, {
      target_concept_text: targetConcept,
    })
    await Promise.all([
      fetchConceptCandidates(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
  } catch (e) {
    console.error('Failed to merge concept candidate:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const rollbackConcept = async ({ candidateId, conceptText }: { candidateId: string; conceptText: string }) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concepts/rollback`, {
      concept_text: conceptText,
      reason: 'Manual rollback from UI',
    })
    await Promise.all([
      fetchConceptCandidates(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
  } catch (e) {
    console.error('Failed to rollback concept:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const promoteCandidateToModelCard = async (candidateId: string) => {
  handoffSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/promote`)
    await fetchConceptCandidates()
  } catch (e) {
    console.error('Failed to promote concept candidate to model card:', e)
  } finally {
    handoffSubmittingId.value = null
  }
}

const openModelCard = (modelCardId: string) => {
  if (!modelCardId) return
  router.push(`/model-cards/${modelCardId}`)
}

const scheduleCandidateReview = async (candidateId: string) => {
  handoffSubmittingId.value = candidateId
  try {
    const response = await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/schedule-review`)
    const modelCardId = String(response.data?.model_card?.id || '')
    if (modelCardId && !scheduledModelCardIds.value.includes(modelCardId)) {
      scheduledModelCardIds.value = [...scheduledModelCardIds.value, modelCardId]
    } else if (!modelCardId) {
      await fetchReviewSchedules()
    }
    await fetchConceptCandidates()
  } catch (e) {
    console.error('Failed to schedule concept candidate review:', e)
  } finally {
    handoffSubmittingId.value = null
  }
}

const decidePathCandidate = async (candidateId: string, action: string) => {
  pathCandidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/path-candidates/${candidateId}/decide`, { action })
    await Promise.all([
      fetchPathCandidates(),
      fetchLearningPath(),
      fetchLearningPaths(),
    ])
  } catch (e) {
    console.error('Failed to decide path candidate:', e)
  } finally {
    pathCandidateSubmittingId.value = null
  }
}

const activateLearningPathById = async (pathId: string) => {
  if (updatingPath.value) return

  updatingPath.value = true
  try {
    const response = await api.post(`/problems/${route.params.id}/learning-paths/${pathId}/activate`)
    learningPath.value = response.data
    await Promise.all([
      fetchLearningPaths(),
      learningMode.value === 'socratic' ? fetchSocraticQuestion() : Promise.resolve(),
    ])
  } catch (e) {
    console.error('Failed to activate learning path:', e)
  } finally {
    updatingPath.value = false
  }
}

const returnToParentPath = async () => {
  if (updatingPath.value || !canReturnToParent.value) return

  updatingPath.value = true
  try {
    const response = await api.post(`/problems/${route.params.id}/learning-path/return`)
    learningPath.value = response.data
    await Promise.all([
      fetchLearningPaths(),
      learningMode.value === 'socratic' ? fetchSocraticQuestion() : Promise.resolve(),
    ])
  } catch (e) {
    console.error('Failed to return to parent learning path:', e)
  } finally {
    updatingPath.value = false
  }
}

onMounted(fetchProblem)
</script>

<style scoped>
.problem-detail {
  max-width: 900px;
  margin: 0 auto;
}

.back-link {
  display: inline-block;
  margin-bottom: 1rem;
  color: var(--text-muted);
  text-decoration: none;
}

.back-link:hover {
  color: var(--primary);
}

.problem-header {
  margin-bottom: 2rem;
}

.problem-header h1 {
  margin-bottom: 0.5rem;
}

.problem-header p {
  color: var(--text-muted);
}

.problem-meta {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}

.mode-badge {
  font-size: 0.78rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  background: rgba(96, 165, 250, 0.1);
  color: #bfdbfe;
}

.problem-content {
  display: grid;
  gap: 1.5rem;
}

.workspace-mode-toggle {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.workspace-stage {
  display: grid;
  gap: 1rem;
}

.workspace-main-column {
  min-width: 0;
}

.workspace-side-column {
  min-width: 0;
}

.workspace-side-stack {
  display: grid;
  gap: 1rem;
}

.workspace-mode-toggle .btn.active {
  border-color: var(--primary);
  color: var(--primary);
}

.card h2 {
  margin-bottom: 0.75rem;
}

.progress-overview {
  display: grid;
  gap: 0.5rem;
  margin-bottom: 1rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.progress-track {
  height: 8px;
  border-radius: 999px;
  background: var(--bg-dark);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #22c55e, var(--primary));
  transition: width 0.2s ease;
}

.step-card {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--border);
  background: var(--bg-dark);
  border-radius: 10px;
}

.step-number {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--primary);
  color: var(--bg-dark);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.step-content h3 {
  margin-bottom: 0.5rem;
}

.step-content p {
  color: var(--text-muted);
  font-size: 0.92rem;
}

.resources {
  margin-top: 0.5rem;
  padding-left: 1.2rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.completion-banner {
  padding: 0.85rem 1rem;
  border-radius: 8px;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  color: #86efac;
}

.path-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: 1rem;
}

.completed-badge {
  color: var(--primary);
  font-size: 0.875rem;
  font-weight: 600;
}

.path-structure-panel {
  margin-bottom: 1rem;
  padding: 0.85rem 1rem;
  border-radius: 10px;
  border: 1px solid rgba(96, 165, 250, 0.2);
  background: rgba(96, 165, 250, 0.06);
}

.path-structure-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.path-nav-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.6rem 0 0.75rem;
}

.path-nav-button.active {
  border-color: var(--primary);
  color: var(--primary);
}

.completed-panel {
  margin-top: 1rem;
}

.completed-panel summary {
  cursor: pointer;
  color: var(--text-muted);
}

.completed-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.completed-item {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(34, 197, 94, 0.08);
}

.completed-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.35);
  color: #dcfce7;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
}

.section-subtitle {
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.response-form {
  margin-bottom: 1rem;
}

.socratic-question-panel {
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: 10px;
  background: rgba(96, 165, 250, 0.08);
}

.question-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.45rem;
}

.question-kind-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.6rem;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  color: #bfdbfe;
  font-size: 0.75rem;
  font-weight: 600;
}

.question-copy {
  margin: 0;
  color: var(--text);
  white-space: pre-wrap;
}

.response-actions {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
}

.auto-advance-notice {
  margin: 0.5rem 0 0.8rem;
  color: #86efac;
  font-size: 0.9rem;
}

.undo-auto-wrap {
  margin-bottom: 0.75rem;
}

.hint-panel {
  margin: 0.6rem 0 1rem;
  padding: 0.8rem;
  border: 1px solid var(--border);
  border-left: 3px solid #60a5fa;
  border-radius: 8px;
  background: rgba(96, 165, 250, 0.08);
}

.hint-panel h3 {
  margin-bottom: 0.5rem;
  font-size: 1rem;
}

.hint-panel ul {
  padding-left: 1.1rem;
  margin: 0.4rem 0;
}

.hint-panel li + li {
  margin-top: 0.2rem;
}

.qa-section {
  margin-top: 0.25rem;
}

.ask-mode-toggle {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.ask-mode-toggle .btn.active {
  border-color: var(--primary);
  color: var(--primary);
}

.qa-latest {
  margin-top: 0.8rem;
  padding: 0.85rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-dark);
}

.qa-latest h3 {
  margin-bottom: 0.35rem;
  font-size: 1rem;
}

.qa-meta {
  color: var(--text-muted);
  font-size: 0.82rem;
  margin-bottom: 0.6rem;
}

.qa-block + .qa-block {
  margin-top: 0.55rem;
}

.qa-actions-block {
  margin-top: 0.75rem;
}

.qa-actions-block ul {
  margin: 0.35rem 0 0;
  padding-left: 1.1rem;
}

.qa-actions-block li + li {
  margin-top: 0.25rem;
}

.path-suggestion-list {
  display: grid;
  gap: 0.55rem;
  margin-top: 0.45rem;
}

.path-suggestion-item {
  padding: 0.7rem 0.8rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(96, 165, 250, 0.06);
}

.path-suggestion-head {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
  margin-bottom: 0.25rem;
}

.qa-block p {
  margin-top: 0.25rem;
  white-space: pre-wrap;
}

.qa-focus-line {
  margin-top: 0.55rem;
  color: var(--text-muted);
}

.mode-line {
  margin-bottom: 0.45rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.system-feedback {
  margin-top: 0.5rem;
  padding: 0.9rem;
  border-radius: 8px;
  background: rgba(74, 222, 128, 0.12);
  border-left: 3px solid var(--primary);
}

.system-feedback h3 {
  margin-bottom: 0.5rem;
  font-size: 1rem;
}

.history-panel {
  margin-top: 1rem;
}

.history-panel summary {
  cursor: pointer;
  color: var(--text-muted);
}

.responses-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.response-item {
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-dark);
}

.user-response p {
  margin-top: 0.35rem;
}

.history-feedback {
  margin-top: 0.5rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.new-concepts-line {
  margin-top: 0.45rem;
  color: #86efac;
}

.pending-concepts-line {
  margin-top: 0.35rem;
  color: #facc15;
}

.ops-meta-line {
  margin-top: 0.35rem;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.ops-fallback-line {
  margin-top: 0.25rem;
  color: #fda4af;
  font-size: 0.82rem;
}

.concept-governance-section {
  margin-top: 0.25rem;
}

.candidate-list {
  display: grid;
  gap: 0.75rem;
}

.candidate-item {
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-dark);
}

.candidate-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.candidate-status {
  font-size: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  color: var(--text-muted);
}

.candidate-confidence,
.candidate-source {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.candidate-evidence {
  margin-top: 0.45rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  white-space: pre-wrap;
}

.candidate-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.6rem;
}

.candidate-pending {
  border-color: rgba(250, 204, 21, 0.35);
}

.candidate-accepted {
  border-color: rgba(34, 197, 94, 0.35);
}

.candidate-planned {
  border-color: rgba(34, 197, 94, 0.35);
}

.candidate-bookmarked {
  border-color: rgba(96, 165, 250, 0.35);
}

.candidate-dismissed {
  border-color: rgba(148, 163, 184, 0.28);
  opacity: 0.8;
}

@media (min-width: 980px) {
  .workspace-stage {
    grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.85fr);
    align-items: start;
  }
}

.status {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  text-transform: capitalize;
}

.status.new {
  background: #3b82f6;
  color: white;
}

.status.in-progress {
  background: #f59e0b;
  color: black;
}

.status.completed {
  background: var(--primary);
  color: var(--bg-dark);
}

.progress-text {
  color: var(--text-muted);
  font-size: 0.875rem;
}

.empty,
.loading {
  color: var(--text-muted);
  padding: 1rem 0;
}
</style>
