<template>
  <div class="problem-detail">
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
              @click="setLearningMode('socratic')"
            >
              {{ t('problemDetail.modeSocratic') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              :class="{ active: learningMode === 'exploration' }"
              :disabled="switchingMode || submitting || askingQuestion"
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

          <form @submit.prevent="submitResponse" class="response-form">
            <div class="form-group">
              <label>{{ t('problemDetail.progressInputLabel') }}</label>
              <textarea
                v-model="responseText"
                rows="5"
                :placeholder="t('problemDetail.progressInputPlaceholder')"
                required
              ></textarea>
            </div>
            <div class="response-actions">
              <button type="button" class="btn btn-secondary" :disabled="hintLoading || submitting" @click="prefillGuidedTemplate">
                {{ hintLoading ? t('common.loading') : t('problemDetail.needPrompt') }}
              </button>
              <button type="submit" class="btn btn-primary" :disabled="submitting">
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

          <div v-if="latestFeedback" class="system-feedback">
            <h3>{{ t('problemDetail.latestFeedbackTitle') }}</h3>
            <p class="mode-line">
              <strong>{{ t('problemDetail.currentMode') }}:</strong> {{ formatLearningMode(latestResponse?.learning_mode) }}
            </p>
            <p v-if="latestFeedback.correctness">
              <strong>{{ t('feedback.correctness') }}:</strong> {{ latestFeedback.correctness }}
            </p>
            <p v-if="latestFeedback.mastery_score !== undefined">
              <strong>{{ t('problemDetail.masteryScore') }}:</strong> {{ latestFeedback.mastery_score }}
              · <strong>{{ t('problemDetail.confidence') }}:</strong> {{ formatConfidence(latestFeedback.confidence) }}
              · <strong>{{ t('problemDetail.passStage') }}:</strong>
              {{ latestFeedback.pass_stage ? t('problemDetail.passStageYes') : t('problemDetail.passStageNo') }}
            </p>
            <p v-if="latestFeedback.misconceptions?.length">
              <strong>{{ t('feedback.misconceptions') }}:</strong> {{ latestFeedback.misconceptions.join(' / ') }}
            </p>
            <p v-if="latestFeedback.suggestions?.length">
              <strong>{{ t('feedback.suggestions') }}:</strong> {{ latestFeedback.suggestions.join(' / ') }}
            </p>
            <p v-if="latestFeedback.next_question">
              <strong>{{ t('feedback.nextQuestion') }}:</strong> {{ latestFeedback.next_question }}
            </p>
            <p v-if="latestFeedback.decision_reason">
              <strong>{{ t('problemDetail.decisionReason') }}:</strong> {{ latestFeedback.decision_reason }}
            </p>
            <p v-if="latestResponse?.accepted_concepts?.length" class="new-concepts-line">
              <strong>{{ t('problemDetail.newConceptsTitle') }}:</strong>
              {{ latestResponse.accepted_concepts.join(' / ') }}
            </p>
            <p v-if="latestResponse?.pending_concepts?.length" class="pending-concepts-line">
              <strong>{{ t('problemDetail.pendingConceptsTitle') }}:</strong>
              {{ latestResponse.pending_concepts.join(' / ') }}
            </p>
            <p v-if="latestResponse?.trace_id || latestResponse?.llm_calls !== undefined" class="ops-meta-line">
              <strong>{{ t('problemDetail.traceId') }}:</strong> {{ latestResponse?.trace_id || '-' }}
              · <strong>{{ t('problemDetail.llmCalls') }}:</strong> {{ latestResponse?.llm_calls ?? '-' }}
              · <strong>{{ t('problemDetail.llmLatencyMs') }}:</strong> {{ latestResponse?.llm_latency_ms ?? '-' }}
            </p>
            <p v-if="latestResponse?.fallback_reason" class="ops-fallback-line">
              <strong>{{ t('problemDetail.fallbackReason') }}:</strong> {{ latestResponse.fallback_reason }}
            </p>
          </div>

          <details v-if="responses.length" class="history-panel">
            <summary>{{ t('problemDetail.historyTitle', { count: responses.length }) }}</summary>
            <div class="responses-list">
              <div v-for="response in responses" :key="response.id" class="response-item">
                <div class="user-response">
                  <p class="mode-line">
                    <strong>{{ t('problemDetail.currentMode') }}:</strong> {{ formatLearningMode(response.learning_mode) }}
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
        </section>

        <section class="card concept-governance-section">
          <h2>{{ t('problemDetail.conceptGovernanceTitle') }}</h2>
          <p class="section-subtitle">{{ t('problemDetail.conceptGovernanceSubtitle') }}</p>

          <div v-if="candidateLoading" class="loading">{{ t('common.loading') }}</div>
          <p v-else-if="!conceptCandidates.length" class="empty">{{ t('problemDetail.noConceptCandidates') }}</p>
          <div v-else class="candidate-list">
            <div
              v-for="candidate in conceptCandidates"
              :key="candidate.id"
              class="candidate-item"
              :class="`candidate-${candidate.status}`"
            >
              <div class="candidate-head">
                <strong>{{ candidate.concept_text }}</strong>
                <span class="candidate-status">{{ candidate.status }}</span>
                <span class="candidate-confidence">{{ formatConfidence(candidate.confidence) }}</span>
                <span class="candidate-source">{{ candidate.source }}</span>
              </div>
              <p v-if="candidate.evidence_snippet" class="candidate-evidence">{{ candidate.evidence_snippet }}</p>
              <div class="candidate-actions">
                <button
                  v-if="candidate.status === 'pending'"
                  type="button"
                  class="btn btn-primary"
                  :disabled="candidateSubmittingId === candidate.id"
                  @click="acceptCandidate(candidate.id)"
                >
                  {{ t('problemDetail.acceptCandidate') }}
                </button>
                <button
                  v-if="candidate.status === 'pending'"
                  type="button"
                  class="btn btn-secondary"
                  :disabled="candidateSubmittingId === candidate.id"
                  @click="rejectCandidate(candidate.id)"
                >
                  {{ t('problemDetail.rejectCandidate') }}
                </button>
                <button
                  v-if="candidate.status === 'accepted'"
                  type="button"
                  class="btn btn-secondary"
                  :disabled="candidateSubmittingId === candidate.id"
                  @click="rollbackConcept(candidate.id, candidate.concept_text)"
                >
                  {{ t('problemDetail.rollbackConcept') }}
                </button>
              </div>
            </div>
          </div>
        </section>

        <section v-if="learningMode === 'exploration'" class="card qa-section">
          <h2>{{ t('problemDetail.askTitle') }}</h2>
          <p class="section-subtitle">{{ t('problemDetail.askSubtitle') }}</p>

          <div class="ask-mode-toggle">
            <button
              type="button"
              class="btn btn-secondary"
              :class="{ active: answerMode === 'direct' }"
              :disabled="askingQuestion"
              @click="answerMode = 'direct'"
            >
              {{ t('problemDetail.askModeDirect') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              :class="{ active: answerMode === 'guided' }"
              :disabled="askingQuestion"
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
                required
              ></textarea>
            </div>
            <button type="submit" class="btn btn-primary" :disabled="askingQuestion || !learningQuestion.trim()">
              {{ askingQuestion ? t('common.loading') : t('problemDetail.askSubmit') }}
            </button>
          </form>

          <div v-if="latestQA" class="qa-latest">
            <h3>{{ t('problemDetail.latestAnswerTitle') }}</h3>
            <p class="mode-line">
              <strong>{{ t('problemDetail.currentMode') }}:</strong> {{ formatLearningMode(latestQA.learning_mode) }}
            </p>
            <p class="qa-meta">{{ t('problemDetail.stepIndicator', { current: latestQA.step_index + 1, total: totalSteps || latestQA.step_index + 1 }) }} · {{ latestQA.step_concept }}</p>
            <div class="qa-block">
              <strong>{{ t('problemDetail.questionLabel') }}</strong>
              <p>{{ latestQA.question }}</p>
            </div>
            <div class="qa-block">
              <strong>{{ t('problemDetail.answerLabel') }}</strong>
              <p>{{ latestQA.answer }}</p>
            </div>
            <p v-if="latestQA.suggested_next_focus" class="qa-focus-line">
              <strong>{{ t('problemDetail.suggestedNextFocus') }}:</strong> {{ latestQA.suggested_next_focus }}
            </p>
            <p v-if="latestQA.accepted_concepts?.length" class="new-concepts-line">
              <strong>{{ t('problemDetail.newConceptsTitle') }}:</strong> {{ latestQA.accepted_concepts.join(' / ') }}
            </p>
            <p v-if="latestQA.pending_concepts?.length" class="pending-concepts-line">
              <strong>{{ t('problemDetail.pendingConceptsTitle') }}:</strong> {{ latestQA.pending_concepts.join(' / ') }}
            </p>
            <p v-if="latestQA.trace_id || latestQA.llm_calls !== undefined" class="ops-meta-line">
              <strong>{{ t('problemDetail.traceId') }}:</strong> {{ latestQA.trace_id || '-' }}
              · <strong>{{ t('problemDetail.llmCalls') }}:</strong> {{ latestQA.llm_calls ?? '-' }}
              · <strong>{{ t('problemDetail.llmLatencyMs') }}:</strong> {{ latestQA.llm_latency_ms ?? '-' }}
            </p>
            <p v-if="latestQA.fallback_reason" class="ops-fallback-line">
              <strong>{{ t('problemDetail.fallbackReason') }}:</strong> {{ latestQA.fallback_reason }}
            </p>
          </div>

          <details v-if="qaHistory.length" class="history-panel">
            <summary>{{ t('problemDetail.qaHistoryTitle', { count: qaHistory.length }) }}</summary>
            <div class="responses-list">
              <div v-for="(item, index) in qaHistory" :key="`${index}-${item.question}`" class="response-item">
                <p class="mode-line">
                  <strong>{{ t('problemDetail.currentMode') }}:</strong> {{ formatLearningMode(item.learning_mode) }}
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
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const route = useRoute()

const problem = ref<any>(null)
const learningPath = ref<any>(null)
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
const learningQuestion = ref('')
const askingQuestion = ref(false)
const answerMode = ref<'direct' | 'guided'>('direct')
const qaHistory = ref<any[]>([])
const conceptCandidates = ref<any[]>([])
const candidateLoading = ref(false)
const candidateSubmittingId = ref<string | null>(null)
const latestQA = computed(() => qaHistory.value[0] || null)

const totalSteps = computed(() => learningPath.value?.path_data?.length || 0)
const completedSteps = computed(() => learningPath.value?.current_step || 0)
const isPathCompleted = computed(() => totalSteps.value > 0 && completedSteps.value >= totalSteps.value)
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

const normalizeExplorationTurn = (turn: any) => ({
  turn_id: turn.turn_id || turn.id || null,
  learning_mode: turn.learning_mode || 'exploration',
  mode_metadata: turn.mode_metadata || {},
  question: turn.question ?? turn.user_text ?? '',
  answer: turn.answer ?? turn.assistant_text ?? '',
  answer_mode: turn.answer_mode ?? turn.mode_metadata?.answer_mode ?? 'direct',
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

const fetchLearningPath = async () => {
  const pathRes = await api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null }))
  learningPath.value = pathRes.data
}

const fetchProblem = async () => {
  try {
    const [problemRes, pathRes, responsesRes, candidatesRes, turnsRes] = await Promise.all([
      api.get(`/problems/${route.params.id}`),
      api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null })),
      api.get(`/problems/${route.params.id}/responses`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/concept-candidates`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/turns`, {
        params: { learning_mode: 'exploration' },
      }).catch(() => ({ data: [] })),
    ])

    problem.value = problemRes.data
    learningMode.value = problemRes.data?.learning_mode || 'socratic'
    learningPath.value = pathRes.data
    responses.value = responsesRes.data
    conceptCandidates.value = candidatesRes.data || []
    qaHistory.value = (turnsRes.data || []).map(normalizeExplorationTurn)
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
    })
    responses.value.push(response.data)
    await Promise.all([
      fetchConceptCandidates(),
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

const rollbackConcept = async (candidateId: string, conceptText: string) => {
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
