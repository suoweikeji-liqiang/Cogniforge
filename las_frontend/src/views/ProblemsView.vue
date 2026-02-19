<template>
  <div class="problems-page">
    <div class="page-header">
      <h1>{{ t('problems.title') }}</h1>
      <button class="btn btn-primary" @click="showCreateModal = true">
        {{ t('problems.newProblem') }}
      </button>
    </div>
    
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    
    <div v-else-if="problems.length" class="problems-grid">
      <router-link 
        v-for="problem in problems" 
        :key="problem.id" 
        :to="`/problems/${problem.id}`"
        class="problem-card"
      >
        <h3>{{ problem.title }}</h3>
        <p>{{ problem.description || t('problems.noProblems') }}</p>
        <div class="problem-meta">
          <span class="status" :class="problem.status">{{ problem.status }}</span>
          <span class="concepts" v-if="problem.associated_concepts?.length">
            {{ problem.associated_concepts.length }} {{ t('problems.concepts') }}
          </span>
        </div>
      </router-link>
    </div>
    
    <p v-else class="empty">{{ t('problems.createFirst') }}</p>
    
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <h2>{{ t('problems.newProblem') }}</h2>
        <form @submit.prevent="createProblem">
          <div class="form-group">
            <label>{{ t('problemDetail.title') }}</label>
            <input v-model="newProblem.title" type="text" required />
          </div>
          <div class="form-group">
            <label>{{ t('problems.description') }}</label>
            <textarea v-model="newProblem.description" rows="4"></textarea>
          </div>
          <div class="form-group">
            <label>{{ t('problems.concepts') }}</label>
            <input v-model="newProblem.concepts" type="text" placeholder="e.g., control theory, PID, systems" />
          </div>
          <p v-if="error" class="error">{{ error }}</p>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="showCreateModal = false">
              {{ t('common.cancel') }}
            </button>
            <button type="submit" class="btn btn-primary" :disabled="creating">
              {{ creating ? t('common.loading') : t('common.add') }}
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
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()

const problems = ref<any[]>([])
const loading = ref(true)
const showCreateModal = ref(false)
const creating = ref(false)
const error = ref('')

const newProblem = ref({
  title: '',
  description: '',
  concepts: '',
})

const fetchProblems = async () => {
  try {
    const response = await api.get('/problems/')
    problems.value = response.data
  } catch (e) {
    console.error('Failed to fetch problems:', e)
  } finally {
    loading.value = false
  }
}

const createProblem = async () => {
  error.value = ''
  creating.value = true
  
  try {
    const concepts = newProblem.value.concepts
      ? newProblem.value.concepts.split(',').map(c => c.trim()).filter(Boolean)
      : []
    
    const response = await api.post('/problems/', {
      title: newProblem.value.title,
      description: newProblem.value.description,
      associated_concepts: concepts,
    })
    
    showCreateModal.value = false
    router.push(`/problems/${response.data.id}`)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to create problem'
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  fetchProblems()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.problems-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.problem-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  text-decoration: none;
  color: var(--text);
  transition: all 0.2s;
}

.problem-card:hover {
  border-color: var(--primary);
}

.problem-card h3 {
  margin-bottom: 0.5rem;
}

.problem-card p {
  color: var(--text-muted);
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.problem-meta {
  display: flex;
  gap: 1rem;
  align-items: center;
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

.concepts {
  font-size: 0.75rem;
  color: var(--text-muted);
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
  max-width: 500px;
}

.modal h2 {
  margin-bottom: 1.5rem;
}

.modal-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
