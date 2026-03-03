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
          <span v-if="learningPath?.path_data?.length" class="progress-text">
            {{ t('problemDetail.progress') }}: {{ completedSteps }}/{{ totalSteps }}
          </span>
        </div>
      </div>
      
      <div class="problem-content">
        <div class="learning-path-section card">
          <h2>{{ t('problemDetail.learningPath') }}</h2>
          <div v-if="learningPath?.path_data?.length" class="path-steps">
            <div 
              v-for="(step, index) in learningPath.path_data" 
              :key="index"
              class="path-step"
              :class="{
                active: index === activeStepIndex,
                completed: index < completedSteps,
              }"
            >
              <div class="step-number">{{ index + 1 }}</div>
              <div class="step-content">
                <h3>{{ step.concept }}</h3>
                <p>{{ step.description }}</p>
                <ul v-if="step.resources?.length" class="resources">
                  <li v-for="resource in step.resources" :key="resource">
                    {{ resource }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
          <div v-if="learningPath?.path_data?.length" class="path-actions">
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
          <p v-else class="empty">{{ t('problemDetail.noResponses') }}</p>
        </div>
        
        <div class="responses-section card">
          <h2>{{ t('problemDetail.responses') }}</h2>
          
          <form @submit.prevent="submitResponse" class="response-form">
            <div class="form-group">
              <label>{{ t('problemDetail.yourResponse') }}</label>
              <textarea 
                v-model="responseText" 
                rows="4" 
                :placeholder="t('problemDetail.yourResponse')"
                required
              ></textarea>
            </div>
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              {{ submitting ? t('common.loading') : t('problemDetail.submitResponse') }}
            </button>
          </form>
          
          <div v-if="responses.length" class="responses-list">
            <div v-for="response in responses" :key="response.id" class="response-item">
              <div class="user-response">
                <strong>{{ t('problemDetail.yourResponse') }}:</strong>
                <p>{{ response.user_response }}</p>
              </div>
              <div v-if="response.system_feedback" class="system-feedback">
                <strong>{{ t('problemDetail.systemFeedback') }}:</strong>
                <div class="feedback-structured">
                  <p v-if="response.structured_feedback?.correctness">
                    <strong>{{ t('feedback.correctness') }}:</strong> {{ response.structured_feedback.correctness }}
                  </p>
                  <p v-if="response.structured_feedback?.misconceptions?.length">
                    <strong>{{ t('feedback.misconceptions') }}:</strong> {{ response.structured_feedback.misconceptions.join(' / ') }}
                  </p>
                  <p v-if="response.structured_feedback?.suggestions?.length">
                    <strong>{{ t('feedback.suggestions') }}:</strong> {{ response.structured_feedback.suggestions.join(' / ') }}
                  </p>
                  <p v-if="response.structured_feedback?.next_question">
                    <strong>{{ t('feedback.nextQuestion') }}:</strong> {{ response.structured_feedback.next_question }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
const responseText = ref('')

const totalSteps = computed(() => learningPath.value?.path_data?.length || 0)
const completedSteps = computed(() => learningPath.value?.current_step || 0)
const isPathCompleted = computed(() => totalSteps.value > 0 && completedSteps.value >= totalSteps.value)
const activeStepIndex = computed(() => {
  if (!totalSteps.value || isPathCompleted.value) {
    return -1
  }
  return completedSteps.value
})

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

onMounted(() => {
  fetchProblem()
})
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
  gap: 2rem;
}

.card h2 {
  margin-bottom: 1rem;
}

.path-steps {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.path-step {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  background: var(--bg-dark);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.path-step.active {
  border-color: var(--primary);
}

.path-step.completed {
  border-color: rgba(74, 222, 128, 0.45);
}

.step-number {
  width: 32px;
  height: 32px;
  background: var(--primary);
  color: var(--bg-dark);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.step-content h3 {
  margin-bottom: 0.5rem;
}

.step-content p {
  color: var(--text-muted);
  font-size: 0.875rem;
}

.resources {
  margin-top: 0.5rem;
  padding-left: 1.5rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.path-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: 1rem;
}

.response-form {
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border);
}

.responses-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.response-item {
  padding: 1rem;
  background: var(--bg-dark);
  border-radius: 8px;
}

.user-response {
  margin-bottom: 1rem;
}

.system-feedback {
  padding: 1rem;
  background: rgba(74, 222, 128, 0.1);
  border-left: 3px solid var(--primary);
  border-radius: 4px;
}

.feedback-structured p + p {
  margin-top: 0.5rem;
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

.completed-badge {
  color: var(--primary);
  font-size: 0.875rem;
  font-weight: 600;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
