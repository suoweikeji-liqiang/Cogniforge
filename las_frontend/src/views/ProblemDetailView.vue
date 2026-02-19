<template>
  <div class="problem-detail">
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    
    <template v-else-if="problem">
      <div class="problem-header">
        <router-link to="/problems" class="back-link">&larr; {{ t('common.back') }}</router-link>
        <h1>{{ problem.title }}</h1>
        <p>{{ problem.description }}</p>
      </div>
      
      <div class="problem-content">
        <div class="learning-path-section card">
          <h2>{{ t('problemDetail.learningPath') }}</h2>
          <div v-if="learningPath?.path_data?.length" class="path-steps">
            <div 
              v-for="(step, index) in learningPath.path_data" 
              :key="index"
              class="path-step"
              :class="{ active: index === learningPath.current_step }"
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
                <p>{{ response.system_feedback }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
const responseText = ref('')

const fetchProblem = async () => {
  try {
    const [problemRes, pathRes] = await Promise.all([
      api.get(`/problems/${route.params.id}`),
      api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null })),
    ])
    
    problem.value = problemRes.data
    learningPath.value = pathRes.data
    
    if (problem.value.responses) {
      responses.value = problem.value.responses
    }
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

.loading {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
