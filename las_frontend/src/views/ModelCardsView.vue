<template>
  <div class="model-cards-page">
    <div class="page-header">
      <h1>{{ t('modelCards.title') }}</h1>
      <button class="btn btn-primary" @click="showCreateModal = true">
        {{ t('modelCards.newCard') }}
      </button>
    </div>

    <div class="filters-bar">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        :placeholder="t('modelCards.searchCards')"
      />
      <select v-model="filterMode" class="filter-select">
        <option value="all">{{ t('modelCards.filterAll') }}</option>
        <option value="scheduled">{{ t('modelCards.filterScheduled') }}</option>
        <option value="unscheduled">{{ t('modelCards.filterUnscheduled') }}</option>
      </select>
    </div>
    
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    
    <div v-else-if="modelCards.length" class="cards-grid">
      <div v-for="card in modelCards" :key="card.id" class="model-card">
        <h3>{{ card.title }}</h3>
        <p v-if="card.user_notes">{{ card.user_notes }}</p>
        
        <div class="card-stats">
          <span>v{{ card.version }}</span>
          <span v-if="card.examples?.length">{{ card.examples.length }} {{ t('modelCards.examples') }}</span>
          <span v-if="card.counter_examples?.length">{{ card.counter_examples.length }} {{ t('modelCards.counterExamples') }}</span>
        </div>
        
        <div class="card-actions">
          <button @click="viewCard(card)" class="btn btn-secondary">{{ t('modelCards.viewCard') }}</button>
          <button
            @click="scheduleReview(card)"
            class="btn btn-secondary"
            :disabled="card.scheduling || card.isScheduled"
          >
            {{ card.isScheduled ? t('modelCards.scheduled') : t('modelCards.addToReview') }}
          </button>
          <button @click="generateCounterExamples(card)" class="btn btn-secondary">
            {{ t('modelCards.counterExamples') }}
          </button>
          <button @click="suggestMigration(card)" class="btn btn-secondary">
            {{ t('chat.newConversation') }}
          </button>
        </div>
        
        <div v-if="card.showCounterExamples" class="generated-content">
          <h4>{{ t('modelCards.counterExamples') }}:</h4>
          <ul>
            <li v-for="(ex, i) in card.counter_examples" :key="i">{{ ex }}</li>
          </ul>
        </div>
        
        <div v-if="card.showMigrations" class="generated-content">
          <h4>{{ t('chat.newConversation') }}:</h4>
          <ul>
            <li v-for="(m, i) in card.migration_attempts" :key="i">
              {{ m.target_domain }}
            </li>
          </ul>
        </div>
      </div>
    </div>
    
    <p v-else class="empty">{{ modelCards.length ? t('modelCards.noCards') : t('modelCards.createFirst') }}</p>
    
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <h2>{{ t('modelCards.newCard') }}</h2>
        <form @submit.prevent="createCard">
          <div class="form-group">
            <label>{{ t('problemDetail.title') }}</label>
            <input v-model="newCard.title" type="text" required />
          </div>
          <div class="form-group">
            <label>{{ t('modelCards.notes') }}</label>
            <textarea v-model="newCard.user_notes" rows="4"></textarea>
          </div>
          <div class="form-group">
            <label>{{ t('modelCards.examples') }}</label>
            <input v-model="newCard.examples" type="text" placeholder="e.g., example1, example2" />
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
import { ref, onMounted, watch } from 'vue'
import api from '@/api'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const router = useRouter()

const modelCards = ref<any[]>([])
const loading = ref(true)
const showCreateModal = ref(false)
const creating = ref(false)
const error = ref('')
const scheduledCardIds = ref<Set<string>>(new Set())
const searchQuery = ref('')
const filterMode = ref('all')

const newCard = ref({
  title: '',
  user_notes: '',
  examples: '',
})

const fetchCards = async () => {
  try {
    const [cardsRes, schedulesRes] = await Promise.all([
      api.get('/model-cards/', {
        params: {
          q: searchQuery.value.trim() || undefined,
          scheduled:
            filterMode.value === 'all'
              ? undefined
              : filterMode.value === 'scheduled',
        },
      }),
      api.get('/srs/schedules').catch(() => ({ data: [] })),
    ])
    scheduledCardIds.value = new Set(
      schedulesRes.data.map((schedule: any) => schedule.model_card_id)
    )
    modelCards.value = cardsRes.data.map((c: any) => ({
      ...c,
      isScheduled: scheduledCardIds.value.has(c.id),
      scheduling: false,
      showCounterExamples: false,
      showMigrations: false,
    }))
  } catch (e) {
    console.error('Failed to fetch model cards:', e)
  } finally {
    loading.value = false
  }
}

const createCard = async () => {
  error.value = ''
  creating.value = true
  
  try {
    const examples = newCard.value.examples
      ? newCard.value.examples.split(',').map(e => e.trim()).filter(Boolean)
      : []
    
    await api.post('/model-cards/', {
      title: newCard.value.title,
      user_notes: newCard.value.user_notes,
      examples,
    })
    
    showCreateModal.value = false
    newCard.value = { title: '', user_notes: '', examples: '' }
    await fetchCards()
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to create model card'
  } finally {
    creating.value = false
  }
}

const viewCard = (card: any) => {
  router.push(`/model-cards/${card.id}`)
}

const generateCounterExamples = async (card: any) => {
  card.showCounterExamples = !card.showCounterExamples
  
  if (!card.counter_examples?.length) {
    try {
      const response = await api.post('/model-cards/counter-examples', {
        model_id: card.id,
        concept: card.title,
      })
      card.counter_examples = response.data.counter_examples
    } catch (e) {
      console.error('Failed to generate counter examples:', e)
    }
  }
}

const suggestMigration = async (card: any) => {
  card.showMigrations = !card.showMigrations
  
  if (!card.migration_attempts?.length) {
    try {
      await api.post('/model-cards/migration', {
        model_id: card.id,
        target_domain: 'general',
      })
      await fetchCards()
    } catch (e) {
      console.error('Failed to suggest migration:', e)
    }
  }
}

const scheduleReview = async (card: any) => {
  if (card.isScheduled || card.scheduling) return

  card.scheduling = true

  try {
    await api.post(`/srs/schedule/${card.id}`)
    card.isScheduled = true
  } catch (e) {
    console.error('Failed to schedule review:', e)
  } finally {
    card.scheduling = false
  }
}

onMounted(() => {
  fetchCards()
})

watch([searchQuery, filterMode], () => {
  fetchCards()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.filters-bar {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
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
  flex: 1;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1rem;
}

.model-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
}

.model-card h3 {
  margin-bottom: 0.5rem;
}

.model-card p {
  color: var(--text-muted);
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.card-stats {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.card-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.card-actions .btn {
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
}

.generated-content {
  margin-top: 1rem;
  padding: 1rem;
  background: var(--bg-dark);
  border-radius: 8px;
}

.generated-content h4 {
  margin-bottom: 0.5rem;
  color: var(--primary);
}

.generated-content ul {
  padding-left: 1.5rem;
  font-size: 0.875rem;
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
