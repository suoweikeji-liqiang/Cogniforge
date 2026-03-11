<template>
  <div class="problems-page">
    <div class="page-header">
      <div>
        <h1>{{ t('problems.title') }}</h1>
        <p class="page-subtitle">{{ t('problems.subtitle') }}</p>
      </div>
      <button class="btn btn-primary" @click="showCreateModal = true">
        {{ t('problems.newProblem') }}
      </button>
    </div>

    <div class="filters-bar">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        data-testid="problems-search-input"
        :placeholder="t('problems.searchProblems')"
      />
    </div>
    
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    
    <template v-else-if="problems.length">
      <div class="problems-grid" data-testid="problems-grid">
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
          <span v-if="problem.learning_mode" class="mode-badge">
            {{ problem.learning_mode === 'exploration' ? t('problemDetail.modeExploration') : t('problemDetail.modeSocratic') }}
          </span>
          <span class="concepts" v-if="problem.associated_concepts?.length">
            {{ problem.associated_concepts.length }} {{ t('problems.concepts') }}
          </span>
        </div>
        <div class="problem-cta">{{ t('problems.openWorkspace') }} →</div>
      </router-link>
      </div>
      <div v-if="hasMoreProblems" class="load-more-row">
        <button
          type="button"
          class="btn btn-secondary"
          :disabled="loadingMore"
          data-testid="problems-load-more"
          @click="loadMoreProblems"
        >
          {{ loadingMore ? t('common.loading') : t('common.loadMore') }}
        </button>
      </div>
    </template>
    
    <p v-else class="empty">{{ emptyProblemsMessage }}</p>
    
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api from '@/api'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
const PAGE_SIZE = 12

const problems = ref<any[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const hasMoreProblems = ref(false)
const showCreateModal = ref(false)
const creating = ref(false)
const error = ref('')
const searchQuery = ref('')
const trimmedSearchQuery = computed(() => searchQuery.value.trim())
const emptyProblemsMessage = computed(() => (
  trimmedSearchQuery.value ? t('problems.noProblems') : t('problems.createFirst')
))
let latestFetchId = 0
let searchDebounceId: number | null = null

const newProblem = ref({
  title: '',
  description: '',
  concepts: '',
})

const fetchProblems = async ({ append = false }: { append?: boolean } = {}) => {
  const fetchId = ++latestFetchId
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
  }

  try {
    const response = await api.get('/problems/', {
      params: {
        q: trimmedSearchQuery.value || undefined,
        limit: PAGE_SIZE,
        offset: append ? problems.value.length : 0,
      },
    })
    if (fetchId !== latestFetchId) return
    const nextProblems = response.data || []
    problems.value = append ? [...problems.value, ...nextProblems] : nextProblems
    hasMoreProblems.value = nextProblems.length === PAGE_SIZE
  } catch (e) {
    if (fetchId !== latestFetchId) return
    console.error('Failed to fetch problems:', e)
    if (!append) {
      problems.value = []
    }
    hasMoreProblems.value = false
  } finally {
    if (fetchId !== latestFetchId) return
    loading.value = false
    loadingMore.value = false
  }
}

const queueProblemSearch = () => {
  if (searchDebounceId !== null) {
    window.clearTimeout(searchDebounceId)
  }
  searchDebounceId = window.setTimeout(() => {
    searchDebounceId = null
    fetchProblems()
  }, 250)
}

const loadMoreProblems = async () => {
  if (loading.value || loadingMore.value || !hasMoreProblems.value) return
  await fetchProblems({ append: true })
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
    }, {
      timeout: 15000,
    })
    
    showCreateModal.value = false
    router.push(`/problems/${response.data.id}`)
  } catch (e: any) {
    if (e.code === 'ECONNABORTED') {
      error.value = t('problems.createTimeout')
    } else {
      error.value = e.response?.data?.detail || t('problems.createFailed')
    }
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  fetchProblems()
})

onBeforeUnmount(() => {
  if (searchDebounceId !== null) {
    window.clearTimeout(searchDebounceId)
  }
})

watch(trimmedSearchQuery, () => {
  queueProblemSearch()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.page-subtitle {
  margin-top: 0.35rem;
  color: var(--text-muted);
  max-width: 48rem;
}

.filters-bar {
  margin-bottom: 1.5rem;
}

.search-input {
  width: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  padding: 0.75rem 1rem;
}

.problems-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.load-more-row {
  display: flex;
  justify-content: center;
  margin-top: 1.25rem;
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
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
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

.mode-badge {
  font-size: 0.72rem;
  padding: 0.16rem 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  background: rgba(96, 165, 250, 0.1);
  color: #bfdbfe;
}

.problem-cta {
  color: var(--primary);
  font-size: 0.85rem;
  font-weight: 600;
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
