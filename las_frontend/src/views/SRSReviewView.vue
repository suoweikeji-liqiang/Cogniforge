<template>
  <div class="srs-review">
    <SecondarySurfaceBanner
      test-id="srs-secondary-banner"
      :eyebrow="t('srs.secondaryTitle')"
      :title="t('srs.secondaryHeading')"
      :message="t('srs.secondaryMessage')"
      :primary-label="t('nav.reviews')"
      primary-to="/reviews"
      :secondary-label="t('graph.openModelCards')"
      secondary-to="/model-cards"
    />
    <h1>{{ t('srs.title') }}</h1>

    <div class="srs-stats">
      <div class="stat-card">
        <h3>{{ t('srs.dueToday') }}</h3>
        <p class="stat-number">{{ dueCards.length }}</p>
      </div>
      <div class="stat-card">
        <h3>{{ t('srs.totalScheduled') }}</h3>
        <p class="stat-number">{{ allSchedules.length }}</p>
      </div>
    </div>

    <section v-if="lastReviewOutcome" class="review-outcome-card" data-testid="srs-last-review-outcome">
      <span class="outcome-eyebrow">{{ t('srs.lastReviewTitle') }}</span>
      <strong>{{ lastReviewOutcome.title }}</strong>
      <p>{{ formatReviewOutcome(lastReviewOutcome) }}</p>
      <div class="outcome-meta-grid">
        <span>{{ t('srs.recallStateLabel') }}: {{ formatRecallState(lastReviewOutcome.recall_state) }}</span>
        <span>{{ t('srs.nextActionLabel') }}: {{ formatRecommendedAction(lastReviewOutcome.recommended_action) }}</span>
      </div>
      <div class="origin-links">
        <router-link
          v-if="lastReviewOutcome.origin?.problem_id"
          :to="`/problems/${lastReviewOutcome.origin.problem_id}`"
          class="btn btn-secondary"
        >
          {{ t('srs.openWorkspace') }}
        </router-link>
        <router-link :to="`/model-cards/${lastReviewOutcome.model_card_id}`" class="btn btn-secondary">
          {{ t('problemDetail.openModelCard') }}
        </router-link>
      </div>
    </section>

    <!-- Review Card -->
    <div v-if="currentCard" class="review-card">
      <h2>{{ currentCard.title }}</h2>
      <div v-if="currentCard.origin" class="origin-card" data-testid="srs-origin-panel">
        <div class="origin-head">
          <div>
            <span class="outcome-eyebrow">{{ t('srs.originLabel') }}</span>
            <strong>{{ formatOriginHeading(currentCard) }}</strong>
          </div>
          <div class="origin-links">
            <router-link
              v-if="currentCard.origin?.problem_id"
              :to="`/problems/${currentCard.origin.problem_id}`"
              class="btn btn-secondary"
            >
              {{ t('srs.openWorkspace') }}
            </router-link>
            <router-link :to="`/model-cards/${currentCard.model_card_id}`" class="btn btn-secondary">
              {{ t('problemDetail.openModelCard') }}
            </router-link>
          </div>
        </div>
        <p class="origin-copy">{{ formatOriginReason(currentCard) }}</p>
        <p v-if="currentCard.origin?.source_turn_preview" class="origin-copy">{{ currentCard.origin.source_turn_preview }}</p>
        <p v-if="currentCard.origin?.evidence_snippet" class="origin-copy">{{ currentCard.origin.evidence_snippet }}</p>
      </div>
      <p class="review-prompt">{{ t('srs.recallPrompt') }}</p>

      <div v-if="!showAnswer" class="review-action">
        <button class="btn btn-primary" @click="showAnswer = true">
          {{ t('srs.showAnswer') }}
        </button>
      </div>

      <div v-else>
        <div class="answer-panel">
          <div v-if="currentCard.user_notes" class="answer-section">
            <h3>{{ t('modelCards.notes') }}</h3>
            <p>{{ currentCard.user_notes }}</p>
          </div>
          <div v-if="currentCard.examples?.length" class="answer-section">
            <h3>{{ t('modelCards.examples') }}</h3>
            <ul>
              <li v-for="(example, index) in currentCard.examples" :key="index">{{ example }}</li>
            </ul>
          </div>
          <div v-if="currentCard.counter_examples?.length" class="answer-section">
            <h3>{{ t('modelCards.counterExamples') }}</h3>
            <ul>
              <li v-for="(example, index) in currentCard.counter_examples" :key="index">{{ example }}</li>
            </ul>
          </div>
        </div>

        <div class="quality-buttons">
          <p class="quality-label">{{ t('srs.rateRecall') }}</p>
          <div class="quality-grid">
            <button class="btn q-btn q-0" @click="submitReview(0)">0 - {{ t('srs.forgot') }}</button>
            <button class="btn q-btn q-1" @click="submitReview(1)">1</button>
            <button class="btn q-btn q-2" @click="submitReview(2)">2</button>
            <button class="btn q-btn q-3" @click="submitReview(3)">3 - {{ t('srs.ok') }}</button>
            <button class="btn q-btn q-4" @click="submitReview(4)">4</button>
            <button class="btn q-btn q-5" @click="submitReview(5)">5 - {{ t('srs.perfect') }}</button>
          </div>
        </div>
      </div>
    </div>

    <p v-else-if="!loading" class="empty">{{ t('srs.allDone') }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'
import SecondarySurfaceBanner from '@/components/SecondarySurfaceBanner.vue'

const { t } = useI18n()

const dueCards = ref<any[]>([])
const allSchedules = ref<any[]>([])
const loading = ref(true)
const showAnswer = ref(false)
const currentIndex = ref(0)
const lastReviewOutcome = ref<any | null>(null)

const currentCard = computed(() => dueCards.value[currentIndex.value] || null)

const formatDateTime = (dateValue: string | undefined | null) => {
  if (!dateValue) return '-'
  return new Date(dateValue).toLocaleString()
}

const formatOriginHeading = (entry: any) => {
  const origin = entry?.origin
  if (!origin?.problem_title) return entry?.title || ''
  const conceptLabel = origin.concept_text || entry.title
  return `${conceptLabel} · ${origin.problem_title}`
}

const formatOriginReason = (entry: any) => {
  const origin = entry?.origin
  if (origin?.learning_mode === 'exploration') return t('srs.originModeExploration')
  if (origin?.learning_mode === 'socratic') return t('srs.originModeSocratic')
  return t('srs.originModeUnknown')
}

const formatRecallState = (state: string | undefined | null) => {
  if (state === 'fragile') return t('srs.recallStateFragile')
  if (state === 'rebuilding') return t('srs.recallStateRebuilding')
  if (state === 'reinforcing') return t('srs.recallStateReinforcing')
  if (state === 'stable') return t('srs.recallStateStable')
  return t('srs.recallStateScheduled')
}

const formatRecentOutcome = (outcome: string | undefined | null) => {
  if (outcome === 'struggled') return t('srs.recallOutcomeStruggled')
  if (outcome === 'held_with_effort') return t('srs.recallOutcomeHeldWithEffort')
  if (outcome === 'held') return t('srs.recallOutcomeHeld')
  if (outcome === 'strong') return t('srs.recallOutcomeStrong')
  return t('srs.recallOutcomePending')
}

const formatRecommendedAction = (action: string | undefined | null) => {
  if (action === 'revisit_workspace') return t('srs.recallActionRevisitWorkspace')
  if (action === 'reinforce_soon') return t('srs.recallActionReinforceSoon')
  if (action === 'keep_spacing') return t('srs.recallActionKeepSpacing')
  if (action === 'extend_or_compare') return t('srs.recallActionExtendOrCompare')
  return t('srs.recallActionCompleteFirstRecall')
}

const formatQualityLabel = (quality: number) => {
  if (quality === 0) return `0 - ${t('srs.forgot')}`
  if (quality === 3) return `3 - ${t('srs.ok')}`
  if (quality === 5) return `5 - ${t('srs.perfect')}`
  return String(quality)
}

const formatReviewOutcome = (outcome: any) => {
  return t('srs.lastReviewSummary', {
    quality: formatQualityLabel(outcome.quality),
    outcome: formatRecentOutcome(outcome.recent_outcome),
    date: formatDateTime(outcome.next_review_at),
  })
}

const fetchData = async () => {
  try {
    const [dueRes, allRes] = await Promise.all([
      api.get('/srs/due'),
      api.get('/srs/schedules'),
    ])
    dueCards.value = dueRes.data
    allSchedules.value = allRes.data
  } catch (e) {
    console.error('Failed to fetch SRS data:', e)
  } finally {
    loading.value = false
  }
}

const submitReview = async (quality: number) => {
  const card = currentCard.value
  if (!card) return
  try {
    const response = await api.post(`/srs/review/${card.schedule_id}?quality=${quality}`)
    lastReviewOutcome.value = {
      title: card.title,
      quality: response.data?.quality ?? quality,
      next_review_at: response.data?.next_review_at,
      recall_state: response.data?.recall_state,
      recent_outcome: response.data?.recent_outcome,
      recommended_action: response.data?.recommended_action,
      origin: card.origin || null,
      model_card_id: card.model_card_id,
    }
    allSchedules.value = allSchedules.value.map((schedule: any) =>
      schedule.schedule_id === card.schedule_id
        ? { ...schedule, ...response.data }
        : schedule
    )
    showAnswer.value = false
    currentIndex.value++
  } catch (e) {
    console.error('Failed to submit review:', e)
  }
}

onMounted(fetchData)
</script>

<style scoped>
.srs-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
}

.stat-card h3 { color: var(--text-muted); font-size: 0.875rem; margin-bottom: 0.5rem; }
.stat-number { font-size: 2rem; font-weight: bold; color: var(--primary); }

.review-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 2rem;
  text-align: center;
  max-width: 600px;
  margin: 0 auto;
}

.review-outcome-card,
.origin-card {
  background: rgba(18, 18, 34, 0.96);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem 1.1rem;
}

.review-outcome-card {
  max-width: 720px;
  margin: 0 auto 1rem;
}

.origin-card {
  display: grid;
  gap: 0.55rem;
  margin-bottom: 1rem;
  text-align: left;
}

.origin-head {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
  flex-wrap: wrap;
}

.outcome-eyebrow {
  color: var(--primary);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.origin-copy {
  color: var(--text-muted);
  white-space: pre-wrap;
}

.origin-links {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.outcome-meta-grid {
  display: grid;
  gap: 0.45rem;
  margin: 0.75rem 0 0.85rem;
  color: var(--text-muted);
  font-size: 0.88rem;
}

.review-card h2 { margin-bottom: 1rem; }
.review-prompt { color: var(--text-muted); margin-bottom: 1.5rem; }
.review-action { margin-top: 1rem; }

.answer-panel {
  text-align: left;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--bg-dark);
  border-radius: 12px;
}

.answer-section + .answer-section {
  margin-top: 1rem;
}

.answer-section h3 {
  margin-bottom: 0.5rem;
  color: var(--primary);
  font-size: 0.95rem;
}

.answer-section p,
.answer-section li {
  color: var(--text-muted);
  line-height: 1.6;
}

.answer-section ul {
  padding-left: 1.25rem;
}

.quality-label { color: var(--text-muted); margin-bottom: 1rem; }

.quality-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}

.q-btn { font-size: 0.8rem; padding: 0.75rem; border-radius: 8px; cursor: pointer; border: 1px solid var(--border); background: var(--bg-dark); color: var(--text); }
.q-0 { border-color: #ef4444; color: #ef4444; }
.q-1 { border-color: #f97316; color: #f97316; }
.q-2 { border-color: #eab308; color: #eab308; }
.q-3 { border-color: #22c55e; color: #22c55e; }
.q-4 { border-color: #3b82f6; color: #3b82f6; }
.q-5 { border-color: #4ade80; color: #4ade80; }

.empty { text-align: center; padding: 3rem; color: var(--text-muted); }
</style>
