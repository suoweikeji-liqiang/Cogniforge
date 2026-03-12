<template>
  <div class="problems-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">{{ t('nav.problems') }}</p>
        <h1>{{ t('problems.title') }}</h1>
        <p class="page-subtitle">{{ t('problems.subtitle') }}</p>
      </div>
      <button class="btn btn-primary" @click="showCreateModal = true">
        {{ t('problems.newProblem') }}
      </button>
    </div>

    <div class="search-row">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        data-testid="problems-search-input"
        :placeholder="t('problems.searchProblems')"
      />
    </div>

    <details class="filters-panel" :open="hasSecondaryFilters" data-testid="problems-filters-panel">
      <summary>
        <span>{{ t('problems.filtersTitle') }}</span>
        <span v-if="activeFilterCount" class="filters-count">{{ activeFilterCount }}</span>
      </summary>
      <p class="filters-hint">{{ t('problems.filtersHint') }}</p>
      <div class="filters-bar">
        <select v-model="learningModeFilter" class="filter-select" data-testid="problems-mode-filter">
          <option value="all">{{ t('problems.filterAllModes') }}</option>
          <option value="socratic">{{ t('problems.filterModeSocratic') }}</option>
          <option value="exploration">{{ t('problems.filterModeExploration') }}</option>
        </select>
        <select v-model="statusFilter" class="filter-select" data-testid="problems-status-filter">
          <option value="all">{{ t('problems.filterAllStatuses') }}</option>
          <option value="new">{{ t('problems.filterStatusNew') }}</option>
          <option value="in-progress">{{ t('problems.filterStatusInProgress') }}</option>
          <option value="completed">{{ t('problems.filterStatusCompleted') }}</option>
        </select>
        <select v-model="sortBy" class="filter-select" data-testid="problems-sort-filter">
          <option value="updated_desc">{{ t('problems.sortRecentActivity') }}</option>
          <option value="created_desc">{{ t('problems.sortNewest') }}</option>
          <option value="created_asc">{{ t('problems.sortOldest') }}</option>
        </select>
        <button
          v-if="hasSecondaryFilters"
          type="button"
          class="btn btn-secondary filters-reset"
          @click="clearFilters"
        >
          {{ t('problems.clearFilters') }}
        </button>
      </div>
    </details>

    <PrimaryAsyncStateCard
      v-if="pageState === 'error'"
      kind="error"
      :title="t('problems.errorTitle')"
      :message="pageError || t('problems.errorMessage')"
      :retry-label="t('common.retry')"
      test-id="problems-error-state"
      retry-test-id="problems-error-retry"
      @retry="fetchProblems()"
    />

    <div v-else-if="loading" class="loading">{{ t('common.loading') }}</div>

    <template v-else-if="problems.length">
      <div class="problems-grid" data-testid="problems-grid">
        <router-link
          v-for="problem in problems"
          :key="problem.id"
          :to="`/problems/${problem.id}`"
          class="problem-card"
        >
          <div class="problem-card-head">
            <div>
              <h3>{{ problem.title }}</h3>
              <p>{{ problem.description || t('problems.createFirst') }}</p>
            </div>
            <span class="status" :class="problem.status">{{ problem.status }}</span>
          </div>
          <div class="problem-meta-row">
            <span v-if="problem.learning_mode" class="mode-badge">
              {{ problem.learning_mode === 'exploration' ? t('problemDetail.modeExploration') : t('problemDetail.modeSocratic') }}
            </span>
            <span class="meta-pill" v-if="problem.associated_concepts?.length">
              {{ problem.associated_concepts.length }} {{ t('problems.concepts') }}
            </span>
            <span class="meta-pill">{{ formatDate(problem.updated_at || problem.created_at) }}</span>
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

    <div v-if="showCreateModal" class="modal-overlay" @click.self="closeCreateModal">
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
          <div class="form-group">
            <label>{{ t('problems.startModeTitle') }}</label>
            <p class="field-hint">{{ t('problems.startModeMessage') }}</p>
            <div class="mode-choice-grid">
              <button
                type="button"
                class="mode-choice"
                :class="{ active: newProblem.learning_mode === 'socratic' }"
                data-testid="problems-create-mode-socratic"
                @click="newProblem.learning_mode = 'socratic'"
              >
                <strong>{{ t('problems.startModeSocratic') }}</strong>
                <span>{{ t('problemDetail.modeSocraticHint') }}</span>
              </button>
              <button
                type="button"
                class="mode-choice"
                :class="{ active: newProblem.learning_mode === 'exploration' }"
                data-testid="problems-create-mode-exploration"
                @click="newProblem.learning_mode = 'exploration'"
              >
                <strong>{{ t('problems.startModeExploration') }}</strong>
                <span>{{ t('problemDetail.modeExplorationHint') }}</span>
              </button>
            </div>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="closeCreateModal">
              {{ t('common.cancel') }}
            </button>
            <button type="submit" class="btn btn-primary" :disabled="creating || !newProblem.learning_mode">
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
import PrimaryAsyncStateCard from '@/components/PrimaryAsyncStateCard.vue'
import type { AsyncPageState } from '@/types/ui'

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
const pageState = ref<AsyncPageState>('loading')
const pageError = ref('')
const searchQuery = ref('')
const learningModeFilter = ref('all')
const statusFilter = ref('all')
const sortBy = ref('updated_desc')
const trimmedSearchQuery = computed(() => searchQuery.value.trim())
const hasSecondaryFilters = computed(() => (
  learningModeFilter.value !== 'all'
  || statusFilter.value !== 'all'
  || sortBy.value !== 'updated_desc'
))
const hasActiveFilters = computed(() => (
  Boolean(trimmedSearchQuery.value)
  || hasSecondaryFilters.value
))
const activeFilterCount = computed(() => (
  [
    learningModeFilter.value !== 'all',
    statusFilter.value !== 'all',
    sortBy.value !== 'updated_desc',
  ].filter(Boolean).length
))
const emptyProblemsMessage = computed(() => (
  hasActiveFilters.value ? t('problems.noProblems') : t('problems.createFirst')
))
let latestFetchId = 0
let searchDebounceId: number | null = null

const newProblem = ref<{
  title: string
  description: string
  concepts: string
  learning_mode: 'socratic' | 'exploration' | ''
}>({
  title: '',
  description: '',
  concepts: '',
  learning_mode: '',
})

const formatDate = (value: string | undefined) => {
  if (!value) return '-'
  return new Date(value).toLocaleDateString()
}

const resetNewProblem = () => {
  newProblem.value = {
    title: '',
    description: '',
    concepts: '',
    learning_mode: '',
  }
}

const closeCreateModal = () => {
  if (creating.value) return
  showCreateModal.value = false
  error.value = ''
  resetNewProblem()
}

const clearFilters = () => {
  searchQuery.value = ''
  learningModeFilter.value = 'all'
  statusFilter.value = 'all'
  sortBy.value = 'updated_desc'
}

const fetchProblems = async ({ append = false }: { append?: boolean } = {}) => {
  const fetchId = ++latestFetchId
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
    pageError.value = ''
    pageState.value = 'loading'
  }

  try {
    const response = await api.get('/problems/', {
      params: {
        q: trimmedSearchQuery.value || undefined,
        learning_mode: learningModeFilter.value === 'all' ? undefined : learningModeFilter.value,
        status: statusFilter.value === 'all' ? undefined : statusFilter.value,
        sort: sortBy.value,
        limit: PAGE_SIZE,
        offset: append ? problems.value.length : 0,
      },
    })
    if (fetchId !== latestFetchId) return
    const nextProblems = response.data || []
    problems.value = append ? [...problems.value, ...nextProblems] : nextProblems
    hasMoreProblems.value = nextProblems.length === PAGE_SIZE
    if (!append) pageState.value = 'ready'
  } catch (e) {
    if (fetchId !== latestFetchId) return
    console.error('Failed to fetch problems:', e)
    if (append) {
      hasMoreProblems.value = false
    } else {
      problems.value = []
      pageError.value = t('problems.errorMessage')
      pageState.value = 'error'
    }
  } finally {
    if (fetchId !== latestFetchId) return
    loading.value = false
    loadingMore.value = false
  }
}

const queueProblemSearch = () => {
  if (searchDebounceId !== null) window.clearTimeout(searchDebounceId)
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
  if (!newProblem.value.learning_mode) {
    error.value = t('problems.startModeMessage')
    return
  }

  error.value = ''
  creating.value = true

  try {
    const concepts = newProblem.value.concepts
      ? newProblem.value.concepts.split(',').map((c) => c.trim()).filter(Boolean)
      : []

    const response = await api.post('/problems/', {
      title: newProblem.value.title,
      description: newProblem.value.description,
      associated_concepts: concepts,
      learning_mode: newProblem.value.learning_mode,
    }, {
      timeout: 15000,
    })

    const createdProblem = response.data
    problems.value = [createdProblem, ...problems.value.filter((item) => item.id !== createdProblem.id)]
    pageState.value = 'ready'
    showCreateModal.value = false
    const destination = `/problems/${createdProblem.id}`
    resetNewProblem()
    await router.push(destination)
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
  if (searchDebounceId !== null) window.clearTimeout(searchDebounceId)
})

watch([trimmedSearchQuery, learningModeFilter, statusFilter, sortBy], () => {
  queueProblemSearch()
})
</script>

<style scoped>
.problems-page {
  display: grid;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 1rem;
}

.page-kicker {
  color: var(--primary);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.page-subtitle {
  margin-top: 0.35rem;
  color: var(--text-muted);
  max-width: 52rem;
}

.search-row {
  display: flex;
}

.filters-panel {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.02);
  padding: 0.95rem 1rem;
}

.filters-panel summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  font-weight: 700;
}

.filters-hint {
  margin: 0.55rem 0 0.85rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.filters-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.5rem;
  height: 1.5rem;
  padding: 0 0.45rem;
  border-radius: 999px;
  background: rgba(74, 222, 128, 0.15);
  color: #bbf7d0;
  font-size: 0.8rem;
  font-weight: 700;
}

.filters-bar {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.filters-reset {
  margin-left: auto;
}

.search-input,
.filter-select {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  padding: 0.75rem 1rem;
}

.search-input {
  flex: 1 1 18rem;
  min-width: 16rem;
}

.filter-select {
  min-width: 11rem;
}

.problems-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.problem-card {
  display: grid;
  gap: 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 1.35rem;
  text-decoration: none;
  color: var(--text);
  transition: all 0.2s ease;
}

.problem-card:hover {
  border-color: var(--primary);
  transform: translateY(-1px);
}

.problem-card-head {
  display: flex;
  justify-content: space-between;
  gap: 0.85rem;
}

.problem-card-head h3 {
  margin-bottom: 0.35rem;
}

.problem-card-head p {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.problem-meta-row {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  align-items: center;
}

.meta-pill,
.mode-badge,
.status {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
}

.meta-pill {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}

.mode-badge {
  border: 1px solid rgba(96, 165, 250, 0.35);
  background: rgba(96, 165, 250, 0.1);
  color: #bfdbfe;
}

.status {
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

.problem-cta {
  color: var(--primary);
  font-size: 0.9rem;
  font-weight: 600;
}

.load-more-row {
  display: flex;
  justify-content: center;
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
  border-radius: 16px;
  padding: 2rem;
  width: 100%;
  max-width: 620px;
}

.modal h2 {
  margin-bottom: 1rem;
}

.field-hint {
  margin-top: 0.3rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.mode-choice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 0.8rem;
}

.mode-choice {
  display: grid;
  gap: 0.35rem;
  text-align: left;
  padding: 1rem;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
  cursor: pointer;
}

.mode-choice span {
  color: var(--text-muted);
  font-size: 0.88rem;
}

.mode-choice.active {
  border-color: rgba(74, 222, 128, 0.42);
  background: rgba(74, 222, 128, 0.08);
}

.modal-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

.loading,
.empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}

@media (max-width: 760px) {
  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .filters-reset {
    margin-left: 0;
  }

  .mode-choice-grid {
    grid-template-columns: 1fr;
  }
}
</style>
