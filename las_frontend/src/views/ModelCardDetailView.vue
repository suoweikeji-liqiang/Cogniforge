<template>
  <div class="model-card-detail">
    <div class="page-header">
      <button class="btn btn-secondary" @click="$router.back()">{{ t('common.back') }}</button>
      <h1>{{ card?.title }}</h1>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <template v-else-if="card">
      <div class="card-info">
        <div class="info-section">
          <h3>{{ t('modelCards.notes') }}</h3>
          <p>{{ card.user_notes || '-' }}</p>
        </div>

        <div class="info-row">
          <div class="info-section">
            <h3>{{ t('modelCards.examples') }}</h3>
            <ul v-if="card.examples?.length">
              <li v-for="(ex, i) in card.examples" :key="i">{{ ex }}</li>
            </ul>
            <p v-else>-</p>
          </div>
          <div class="info-section">
            <h3>{{ t('modelCards.counterExamples') }}</h3>
            <ul v-if="card.counter_examples?.length">
              <li v-for="(ex, i) in card.counter_examples" :key="i">{{ ex }}</li>
            </ul>
            <p v-else>-</p>
          </div>
        </div>

        <div class="card-meta">
          <span>{{ t('modelCards.version') }}: v{{ card.version }}</span>
          <span>{{ t('problems.createdAt') }}: {{ formatDate(card.created_at) }}</span>
        </div>
        <div class="review-actions">
          <button
            class="btn btn-secondary"
            :disabled="schedulingReview || isScheduled"
            @click="scheduleReview"
          >
            {{ isScheduled ? t('modelCards.scheduled') : t('modelCards.addToReview') }}
          </button>
          <router-link to="/reviews" class="btn btn-secondary review-hub-link">
            {{ t('modelCards.openReviewHub') }}
          </router-link>
        </div>
        <div v-if="reviewSchedule" class="recall-status-card" data-testid="model-card-recall-status">
          <div class="recall-status-head">
            <div>
              <span class="recall-eyebrow">{{ t('modelCards.recallStatusTitle') }}</span>
              <strong>{{ formatRecallState(reviewSchedule.recall_state) }}</strong>
              <p>{{ formatRecallOutcome(reviewSchedule) }}</p>
            </div>
            <router-link
              v-if="reviewSchedule.origin?.problem_id"
              :to="`/problems/${reviewSchedule.origin.problem_id}`"
              class="btn btn-secondary review-hub-link"
            >
              {{ t('reviews.openWorkspace') }}
            </router-link>
          </div>
          <div class="recall-meta-grid">
            <span>{{ t('modelCards.lastRecallAt') }}: {{ formatDateTime(reviewSchedule.last_reviewed_at) }}</span>
            <span>{{ t('modelCards.nextRecallAt') }}: {{ formatDateTime(reviewSchedule.next_review_at) }}</span>
            <span>{{ t('modelCards.recallNextAction') }}: {{ formatRecommendedAction(reviewSchedule.recommended_action) }}</span>
          </div>
        </div>
        <div class="cog-test-action">
          <button class="btn btn-secondary" @click="startCogTest">
            {{ t('modelCards.runDiagnostic') }}
          </button>
        </div>
      </div>

      <!-- Evolution Timeline -->
      <div class="evolution-section">
        <h2>{{ t('evolution.title') }}</h2>
        <div v-if="evolutionCompare" class="summary-card">
          <h3>{{ t('evolution.latestSummary') }}</h3>
          <p>{{ evolutionCompare.changes_summary }}</p>
          <div class="summary-meta">
            <span v-if="evolutionCompare.old_version">
              v{{ evolutionCompare.old_version.version }} -> v{{ evolutionCompare.new_version.version }}
            </span>
            <span v-else>
              v{{ evolutionCompare.new_version.version }}
            </span>
          </div>
        </div>
        <div v-if="evolutionLogs.length" class="timeline">
          <div
            v-for="log in evolutionLogs"
            :key="log.id"
            class="timeline-item"
          >
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <div class="timeline-header">
                <span class="action-badge">{{ log.action_taken }}</span>
                <span class="timeline-date">{{ formatDate(log.created_at) }}</span>
              </div>
              <p v-if="log.reason_for_change">{{ log.reason_for_change }}</p>
              <div v-if="log.snapshot" class="snapshot-preview">
                <span>v{{ log.snapshot.version }} - {{ log.snapshot.title || card.title }}</span>
              </div>
            </div>
          </div>
        </div>
        <p v-else class="empty">{{ t('evolution.noLogs') }}</p>
      </div>

      <div class="evolution-section">
        <h2>{{ t('modelCards.similarCards') }}</h2>
        <div v-if="similarCards.length" class="similar-list">
          <router-link
            v-for="similar in similarCards"
            :key="similar.id"
            :to="`/model-cards/${similar.id}`"
            class="similar-card"
          >
            <strong>{{ similar.title }}</strong>
            <p>{{ similar.user_notes || '-' }}</p>
          </router-link>
        </div>
        <p v-else class="empty">{{ t('modelCards.noSimilarCards') }}</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import api from '@/api'
import { useCogTestStore } from '@/stores/cogTest'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const cogTestStore = useCogTestStore()

const startCogTest = async () => {
  await cogTestStore.startSession(card.value.title, card.value.id)
  router.push('/cog-test/session')
}

const card = ref<any>(null)
const evolutionLogs = ref<any[]>([])
const evolutionCompare = ref<any>(null)
const similarCards = ref<any[]>([])
const loading = ref(true)
const schedulingReview = ref(false)
const isScheduled = ref(false)
const reviewSchedule = ref<any | null>(null)

const formatDate = (d: string) => new Date(d).toLocaleDateString()
const formatDateTime = (d: string | undefined | null) => (d ? new Date(d).toLocaleString() : '-')

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

const formatRecallOutcome = (schedule: any) => {
  return t('modelCards.recallOutcomeSummary', {
    outcome: formatRecentOutcome(schedule?.recent_outcome),
    action: formatRecommendedAction(schedule?.recommended_action),
  })
}

const fetchCard = async () => {
  try {
    const id = route.params.id
    const [cardRes, logsRes, schedulesRes, compareRes, similarRes] = await Promise.all([
      api.get(`/model-cards/${id}`),
      api.get(`/model-cards/${id}/evolution`),
      api.get('/srs/schedules').catch(() => ({ data: [] })),
      api.get(`/model-cards/${id}/compare`).catch(() => ({ data: null })),
      api.get(`/model-cards/${id}/similar`).catch(() => ({ data: [] })),
    ])
    card.value = cardRes.data
    evolutionLogs.value = logsRes.data
    evolutionCompare.value = compareRes.data
    similarCards.value = similarRes.data
    reviewSchedule.value = schedulesRes.data.find((schedule: any) => schedule.model_card_id === id) || null
    isScheduled.value = Boolean(reviewSchedule.value)
  } catch (e) {
    console.error('Failed to fetch model card:', e)
  } finally {
    loading.value = false
  }
}

const scheduleReview = async () => {
  if (!card.value || isScheduled.value || schedulingReview.value) return

  schedulingReview.value = true

  try {
    const response = await api.post(`/srs/schedule/${card.value.id}`)
    isScheduled.value = true
    reviewSchedule.value = {
      model_card_id: card.value.id,
      title: card.value.title,
      next_review_at: response.data?.next_review_at,
      last_reviewed_at: null,
      recall_state: 'scheduled',
      recent_outcome: 'pending',
      recommended_action: 'complete_first_recall',
      origin: null,
    }
  } catch (e) {
    console.error('Failed to schedule review:', e)
  } finally {
    schedulingReview.value = false
  }
}

onMounted(fetchCard)
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.card-info {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.info-section { margin-bottom: 1rem; }
.info-section h3 { color: var(--primary); margin-bottom: 0.5rem; }
.info-section ul { padding-left: 1.5rem; color: var(--text-muted); }

.info-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.card-meta {
  display: flex;
  gap: 2rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.review-actions {
  margin-top: 1rem;
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.review-hub-link {
  text-decoration: none;
}

.recall-status-card {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid rgba(74, 222, 128, 0.24);
  background: rgba(74, 222, 128, 0.08);
}

.recall-status-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  flex-wrap: wrap;
}

.recall-eyebrow {
  display: inline-flex;
  color: var(--primary);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.35rem;
}

.recall-meta-grid {
  display: grid;
  gap: 0.45rem;
  margin-top: 0.85rem;
  color: var(--text-muted);
  font-size: 0.88rem;
}

.evolution-section { margin-top: 2rem; }
.evolution-section h2 { margin-bottom: 1rem; }

.summary-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.summary-card h3 {
  margin-bottom: 0.5rem;
  color: var(--primary);
}

.summary-card p {
  color: var(--text-muted);
  line-height: 1.6;
}

.summary-meta {
  margin-top: 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.timeline {
  position: relative;
  padding-left: 2rem;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 8px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--border);
}

.timeline-item {
  position: relative;
  margin-bottom: 1.5rem;
}

.timeline-dot {
  position: absolute;
  left: -2rem;
  top: 4px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--primary);
  border: 2px solid var(--bg-dark);
}

.timeline-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.action-badge {
  background: var(--primary);
  color: var(--bg-dark);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.timeline-date { font-size: 0.75rem; color: var(--text-muted); }

.snapshot-preview {
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  font-style: italic;
}

.loading, .empty {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}

.similar-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}

.similar-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  text-decoration: none;
  color: var(--text);
}

.similar-card p {
  margin-top: 0.5rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.cog-test-action {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}
</style>
