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
      <div
        v-for="card in modelCards"
        :key="card.id"
        class="model-card"
        :class="card.evolutionState ? `model-card-${card.evolutionState.tone}` : ''"
      >
        <h3>{{ card.title }}</h3>
        <p v-if="card.user_notes">{{ card.user_notes }}</p>
        
        <div class="card-stats">
          <span>v{{ card.version }}</span>
          <span v-if="card.examples?.length">{{ card.examples.length }} {{ t('modelCards.examples') }}</span>
          <span v-if="card.counter_examples?.length">{{ card.counter_examples.length }} {{ t('modelCards.counterExamples') }}</span>
        </div>
        <div
          v-if="card.evolutionState"
          class="evolution-state-strip"
          data-testid="model-card-list-evolution-state"
        >
          <span class="evolution-state-pill" :class="`state-${card.evolutionState.tone}`">
            {{ formatEvolutionStateLabel(card.evolutionState) }}
          </span>
          <span class="evolution-state-copy">
            {{ formatEvolutionStateSummary(card.evolutionState, card.reviewSchedule) }}
          </span>
        </div>
        <div v-if="card.isScheduled" class="recall-strip">
          <span class="recall-pill" :class="`recall-${card.reviewSchedule?.recall_state || 'scheduled'}`">
            {{ formatRecallState(card.reviewSchedule?.recall_state) }}
          </span>
          <span class="recall-copy">{{ formatRecentOutcome(card.reviewSchedule?.recent_outcome) }}</span>
        </div>
        <p v-if="card.isScheduled" class="recall-next-action">
          {{ formatRecommendedAction(card.reviewSchedule?.recommended_action) }}
        </p>
        <p v-if="card.reviewSchedule?.needs_reinforcement" class="recall-reinforcement">
          <strong>{{ t('modelCards.needsReinforcementBadge') }}:</strong>
          {{ formatReinforcementResume(card.reviewSchedule) }}
        </p>
        
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
            {{ t('modelCards.suggestTransfer') }}
          </button>
        </div>
        
        <div v-if="card.showCounterExamples" class="generated-content">
          <h4>{{ t('modelCards.counterExamples') }}:</h4>
          <ul>
            <li v-for="(ex, i) in card.counter_examples" :key="i">{{ ex }}</li>
          </ul>
        </div>
        
        <div v-if="card.showMigrations" class="generated-content">
          <h4>{{ t('modelCards.suggestTransfer') }}:</h4>
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
import { deriveModelCardEvolutionState, type ModelCardEvolutionState } from '@/utils/modelCardEvolution'

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
    const schedulesByCardId = Object.fromEntries(
      (schedulesRes.data || []).map((schedule: any) => [String(schedule.model_card_id), schedule])
    )
    scheduledCardIds.value = new Set(Object.keys(schedulesByCardId))
    modelCards.value = cardsRes.data.map((c: any) => ({
      ...c,
      isScheduled: scheduledCardIds.value.has(c.id),
      reviewSchedule: schedulesByCardId[String(c.id)] || null,
      evolutionState: deriveModelCardEvolutionState(schedulesByCardId[String(c.id)] || null),
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
    const response = await api.post(`/srs/schedule/${card.id}`)
    card.isScheduled = true
    card.reviewSchedule = {
      model_card_id: card.id,
      next_review_at: response.data?.next_review_at,
      last_reviewed_at: null,
      recall_state: 'scheduled',
      recent_outcome: 'pending',
      recommended_action: 'complete_first_recall',
    }
  } catch (e) {
    console.error('Failed to schedule review:', e)
  } finally {
    card.scheduling = false
  }
}

const formatRecallState = (state: string | undefined | null) => {
  if (state === 'fragile') return t('modelCards.recallStateFragile')
  if (state === 'rebuilding') return t('modelCards.recallStateRebuilding')
  if (state === 'reinforcing') return t('modelCards.recallStateReinforcing')
  if (state === 'stable') return t('modelCards.recallStateStable')
  return t('modelCards.recallStateScheduled')
}

const formatRecentOutcome = (outcome: string | undefined | null) => {
  if (outcome === 'struggled') return t('modelCards.recallOutcomeStruggled')
  if (outcome === 'held_with_effort') return t('modelCards.recallOutcomeHeldWithEffort')
  if (outcome === 'held') return t('modelCards.recallOutcomeHeld')
  if (outcome === 'strong') return t('modelCards.recallOutcomeStrong')
  return t('modelCards.recallOutcomePending')
}

const formatRecommendedAction = (action: string | undefined | null) => {
  if (action === 'revisit_workspace') return t('modelCards.recallActionRevisitWorkspace')
  if (action === 'reinforce_soon') return t('modelCards.recallActionReinforceSoon')
  if (action === 'keep_spacing') return t('modelCards.recallActionKeepSpacing')
  if (action === 'extend_or_compare') return t('modelCards.recallActionExtendOrCompare')
  return t('modelCards.recallActionCompleteFirstRecall')
}

const formatLearningPathKind = (kind: string | undefined | null) => {
  if (kind === 'prerequisite') return t('problemDetail.pathKindPrerequisite')
  if (kind === 'comparison') return t('problemDetail.pathKindComparison')
  if (kind === 'branch') return t('problemDetail.pathKindBranch')
  return t('problemDetail.pathKindMain')
}

const formatReinforcementResume = (schedule: any) => {
  const target = schedule?.reinforcement_target
  const pathLabel = formatReinforcementPath(target)
  const rawStepIndex = Number(target?.resume_step_index)
  const hasStepIndex = Number.isFinite(rawStepIndex)
  const stepNumber = hasStepIndex ? rawStepIndex + 1 : null
  const stepConcept = String(target?.resume_step_concept || '').trim()

  if (stepNumber !== null && stepConcept) {
    const stepLabel = t('modelCards.reinforcementResumeStepConcept', {
      step: stepNumber,
      concept: stepConcept,
    })
    const workspaceLabel = target?.problem_title ? `${target.problem_title} · ${stepLabel}` : stepLabel
    return pathLabel ? `${pathLabel} · ${workspaceLabel}` : workspaceLabel
  }
  if (target?.problem_title && stepConcept) {
    const conceptLabel = t('modelCards.reinforcementResumeWorkspaceConcept', {
      workspace: target.problem_title,
      concept: stepConcept,
    })
    return pathLabel ? `${pathLabel} · ${conceptLabel}` : conceptLabel
  }
  if (stepConcept) {
    const conceptLabel = t('modelCards.reinforcementResumeConcept', { concept: stepConcept })
    return pathLabel ? `${pathLabel} · ${conceptLabel}` : conceptLabel
  }
  return pathLabel || t('modelCards.reinforcementResumeCurrentCard')
}

const formatEvolutionStateLabel = (state: ModelCardEvolutionState | null) => {
  if (!state) return ''
  if (state.key === 'needs_revision') return t('modelCards.evolutionStateNeedsRevision')
  if (state.key === 'rebuilding') return t('modelCards.evolutionStateRebuilding')
  if (state.key === 'reinforced_recently') return t('modelCards.evolutionStateReinforcedRecently')
  if (state.key === 'stable_base') return t('modelCards.evolutionStateStableBase')
  if (state.key === 'repeated_confusion') return t('modelCards.evolutionStateRepeatedConfusion')
  return t('modelCards.evolutionStateFirstRecallQueued')
}

const modelCardWorkspaceLabel = (schedule: any) => {
  return schedule?.reinforcement_target?.problem_title
    || schedule?.origin?.problem_title
    || t('modelCards.linkedWorkspaceFallback')
}

const formatEvolutionStateSummary = (state: ModelCardEvolutionState | null, schedule: any) => {
  if (!state) return ''
  const workspace = modelCardWorkspaceLabel(schedule)
  if (state.key === 'needs_revision') {
    return t('modelCards.evolutionStateNeedsRevisionSummary', { workspace })
  }
  if (state.key === 'rebuilding') {
    return t('modelCards.evolutionStateRebuildingSummary', { workspace })
  }
  if (state.key === 'reinforced_recently') {
    return t('modelCards.evolutionStateReinforcedRecentlySummary')
  }
  if (state.key === 'stable_base') {
    return t('modelCards.evolutionStateStableBaseSummary')
  }
  if (state.key === 'repeated_confusion') {
    return t('modelCards.evolutionStateRepeatedConfusionSummary', {
      count: state.reinforcementEventCount,
      workspace,
    })
  }
  return t('modelCards.evolutionStateFirstRecallQueuedSummary')
}

const formatReinforcementPath = (target: any) => {
  const title = String(target?.resume_path_title || '').trim()
  const kind = String(target?.resume_path_kind || '').trim()
  const kindLabel = kind ? formatLearningPathKind(kind) : ''
  if (kindLabel && title) return `${kindLabel} · ${title}`
  if (title) return title
  if (kindLabel) return kindLabel
  return ''
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

.model-card-danger {
  border-color: rgba(248, 113, 113, 0.25);
}

.model-card-warning {
  border-color: rgba(251, 191, 36, 0.24);
}

.model-card-success {
  border-color: rgba(74, 222, 128, 0.24);
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

.evolution-state-strip {
  display: grid;
  gap: 0.35rem;
  margin-bottom: 0.75rem;
}

.evolution-state-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 700;
  border: 1px solid var(--border);
}

.evolution-state-pill.state-neutral {
  border-color: rgba(96, 165, 250, 0.28);
  color: #bfdbfe;
}

.evolution-state-pill.state-danger {
  border-color: rgba(248, 113, 113, 0.3);
  color: #fca5a5;
}

.evolution-state-pill.state-warning {
  border-color: rgba(251, 191, 36, 0.3);
  color: #fde68a;
}

.evolution-state-pill.state-success {
  border-color: rgba(74, 222, 128, 0.28);
  color: #86efac;
}

.evolution-state-copy {
  color: var(--text-muted);
  font-size: 0.84rem;
}

.recall-strip {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
  margin-bottom: 0.35rem;
}

.recall-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 600;
  border: 1px solid var(--border);
}

.recall-scheduled {
  border-color: rgba(96, 165, 250, 0.28);
  color: #bfdbfe;
}

.recall-fragile {
  border-color: rgba(248, 113, 113, 0.28);
  color: #fca5a5;
}

.recall-rebuilding {
  border-color: rgba(251, 191, 36, 0.28);
  color: #fde68a;
}

.recall-reinforcing {
  border-color: rgba(74, 222, 128, 0.24);
  color: #bbf7d0;
}

.recall-stable {
  border-color: rgba(34, 197, 94, 0.35);
  color: #86efac;
}

.recall-copy,
.recall-next-action {
  color: var(--text-muted);
  font-size: 0.84rem;
}

.recall-next-action {
  margin-bottom: 0.9rem;
}

.recall-reinforcement {
  color: #fecaca;
  font-size: 0.84rem;
  margin-bottom: 0.9rem;
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
