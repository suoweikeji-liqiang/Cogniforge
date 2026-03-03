<template>
  <div class="practice-page">
    <h1>{{ t('practice.title') }}</h1>
    
    <div class="practice-content">
      <div class="tasks-section">
        <h2>{{ t('practice.title') }}</h2>
        <div v-if="tasks.length" class="tasks-grid">
          <div v-for="task in tasks" :key="task.id" class="task-card card">
            <h3>{{ task.title }}</h3>
            <p>{{ task.description || t('problems.noProblems') }}</p>
            <button @click="startTask(task)" class="btn btn-primary">
              {{ t('practice.submitSolution') }}
            </button>
          </div>
        </div>
        <p v-else class="empty">{{ t('practice.noTasks') }}</p>
      </div>
      
      <div class="submissions-section">
        <h2>{{ t('practice.submitted') }}</h2>
        <div v-if="submissions.length" class="submissions-list">
          <div v-for="sub in submissions" :key="sub.id" class="submission-item card">
            <h4>{{ truncate(sub.solution, 100) }}</h4>
            <div v-if="sub.structured_feedback" class="feedback-block">
              <p v-if="sub.structured_feedback.correctness"><strong>{{ t('feedback.correctness') }}:</strong> {{ sub.structured_feedback.correctness }}</p>
              <p v-if="sub.structured_feedback.suggestions?.length"><strong>{{ t('feedback.suggestions') }}:</strong> {{ sub.structured_feedback.suggestions.join(' / ') }}</p>
            </div>
          </div>
        </div>
        <p v-else class="empty">{{ t('practice.noTasks') }}</p>
      </div>
    </div>
    
    <div v-if="activeTask" class="modal-overlay" @click.self="activeTask = null">
      <div class="modal">
        <h2>{{ activeTask.title }}</h2>
        <p>{{ activeTask.description }}</p>
        
        <form @submit.prevent="submitSolution">
          <div class="form-group">
            <label>{{ t('practice.yourSolution') }}</label>
            <textarea v-model="solution" rows="6" required></textarea>
          </div>
          <div v-if="currentStructuredFeedback" class="feedback-result">
            <p v-if="currentStructuredFeedback.correctness"><strong>{{ t('feedback.correctness') }}:</strong> {{ currentStructuredFeedback.correctness }}</p>
            <p v-if="currentStructuredFeedback.misconceptions?.length"><strong>{{ t('feedback.misconceptions') }}:</strong> {{ currentStructuredFeedback.misconceptions.join(' / ') }}</p>
            <p v-if="currentStructuredFeedback.suggestions?.length"><strong>{{ t('feedback.suggestions') }}:</strong> {{ currentStructuredFeedback.suggestions.join(' / ') }}</p>
            <p v-if="currentStructuredFeedback.next_question"><strong>{{ t('feedback.nextQuestion') }}:</strong> {{ currentStructuredFeedback.next_question }}</p>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="activeTask = null">
              {{ t('common.close') }}
            </button>
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              {{ submitting ? t('common.loading') : t('practice.submitSolution') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const tasks = ref<any[]>([])
const submissions = ref<any[]>([])
const activeTask = ref<any>(null)
const solution = ref('')
const currentStructuredFeedback = ref<any>(null)
const submitting = ref(false)

const truncate = (text: string, max: number) => text.length > max ? `${text.slice(0, max)}...` : text

const fetchData = async () => {
  try {
    const [tasksRes, subsRes] = await Promise.all([
      api.get('/practice/tasks'),
      api.get('/practice/submissions'),
    ])
    tasks.value = tasksRes.data
    submissions.value = subsRes.data
  } catch (e) {
    console.error('Failed to fetch practice data:', e)
  }
}

const startTask = (task: any) => {
  activeTask.value = task
  solution.value = ''
  currentStructuredFeedback.value = null
}

const submitSolution = async () => {
  if (!activeTask.value) return
  
  submitting.value = true
  
  try {
    const response = await api.post('/practice/submissions', {
      practice_task_id: activeTask.value.id,
      solution: solution.value,
    })
    
    currentStructuredFeedback.value = response.data.structured_feedback
    submissions.value.unshift(response.data)
  } catch (e) {
    console.error('Failed to submit solution:', e)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.practice-page h1 {
  margin-bottom: 2rem;
}

.practice-content {
  display: grid;
  gap: 2rem;
}

.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.task-card {
  display: flex;
  flex-direction: column;
}

.task-card h3 {
  margin-bottom: 0.5rem;
}

.task-card p {
  color: var(--text-muted);
  font-size: 0.875rem;
  margin-bottom: 1rem;
  flex-grow: 1;
}

.submissions-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.submission-item h4 {
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
}

.feedback-block {
  font-size: 0.875rem;
  color: var(--primary);
}

.feedback-block p + p {
  margin-top: 0.35rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
}

.modal {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 2rem;
  width: 100%;
  max-width: 600px;
}

.modal h2 {
  margin-bottom: 1rem;
}

.modal p {
  color: var(--text-muted);
  margin-bottom: 1.5rem;
}

.modal-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 1rem;
}

.feedback-result {
  margin-top: 1rem;
  padding: 1rem;
  background: rgba(74, 222, 128, 0.1);
  border-radius: 8px;
}

.empty {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}
</style>
