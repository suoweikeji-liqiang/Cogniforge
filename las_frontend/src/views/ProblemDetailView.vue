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
          <span v-if="totalSteps" class="progress-text">
            {{ t('problemDetail.progress') }}: {{ completedSteps }}/{{ totalSteps }}
          </span>
        </div>
      </div>

      <div class="problem-content">
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

        <section class="card responses-section">
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
            <p v-if="latestFeedback.correctness">
              <strong>{{ t('feedback.correctness') }}:</strong> {{ latestFeedback.correctness }}
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
          </div>

          <details v-if="responses.length" class="history-panel">
            <summary>{{ t('problemDetail.historyTitle', { count: responses.length }) }}</summary>
            <div class="responses-list">
              <div v-for="response in responses" :key="response.id" class="response-item">
                <div class="user-response">
                  <strong>{{ t('problemDetail.myProgressRecord') }}:</strong>
                  <p>{{ response.user_response }}</p>
                </div>
                <div v-if="response.structured_feedback" class="history-feedback">
                  <p v-if="response.structured_feedback.correctness">
                    <strong>{{ t('feedback.correctness') }}:</strong> {{ response.structured_feedback.correctness }}
                  </p>
                  <p v-if="response.structured_feedback.suggestions?.length">
                    <strong>{{ t('feedback.suggestions') }}:</strong> {{ response.structured_feedback.suggestions.join(' / ') }}
                  </p>
                  <p v-if="response.structured_feedback.next_question">
                    <strong>{{ t('feedback.nextQuestion') }}:</strong> {{ response.structured_feedback.next_question }}
                  </p>
                </div>
              </div>
            </div>
          </details>
          <p v-else class="empty">{{ t('problemDetail.noProgressRecords') }}</p>
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
const loading = ref(true)
const submitting = ref(false)
const updatingPath = ref(false)
const hintLoading = ref(false)
const responseText = ref('')
const autoAdvanceMessage = ref('')
const canUndoAutoAdvance = ref(false)
const undoTargetStep = ref<number | null>(null)
const stepHint = ref<any | null>(null)

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

const fetchLearningPath = async () => {
  const pathRes = await api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null }))
  learningPath.value = pathRes.data
}

const fetchProblem = async () => {
  try {
    const [problemRes, pathRes, responsesRes] = await Promise.all([
      api.get(`/problems/${route.params.id}`),
      api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null })),
      api.get(`/problems/${route.params.id}/responses`).catch(() => ({ data: [] })),
    ])

    problem.value = problemRes.data
    learningPath.value = pathRes.data
    responses.value = responsesRes.data
  } catch (e) {
    console.error('Failed to fetch problem:', e)
  } finally {
    loading.value = false
  }
}

const submitResponse = async () => {
  submitting.value = true

  try {
    const response = await api.post(`/problems/${route.params.id}/responses`, {
      problem_id: route.params.id,
      user_response: responseText.value,
    })
    responses.value.push(response.data)
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

.problem-content {
  display: grid;
  gap: 1.5rem;
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
