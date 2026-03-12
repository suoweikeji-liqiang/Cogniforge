<template>
  <div class="reviews-page" data-testid="review-lifecycle-page">
    <PrimaryAsyncStateCard
      v-if="pageState === 'error'"
      kind="error"
      :title="t('reviews.errorTitle')"
      :message="pageError || t('reviews.errorMessage')"
      :retry-label="t('common.retry')"
      test-id="reviews-error-state"
      retry-test-id="reviews-error-retry"
      @retry="fetchReviewLifecycle"
    />

    <div v-else-if="pageState === 'loading'" class="empty">{{ t('common.loading') }}</div>

    <template v-else>
      <section class="hero-shell">
        <div class="hero-copy">
          <p class="hero-kicker">{{ t('reviews.focusTitle') }}</p>
          <h1>{{ t('reviews.title') }}</h1>
          <p class="hero-subtitle">{{ t('reviews.subtitle') }}</p>
        </div>

        <router-link
          :to="focusCard.to"
          class="focus-card"
          :class="focusCard.tone"
          data-testid="reviews-focus-card"
        >
          <span class="focus-eyebrow">{{ focusCard.eyebrow }}</span>
          <h2>{{ focusCard.title }}</h2>
          <p>{{ focusCard.description }}</p>
          <span class="focus-cta">{{ focusCard.cta }}</span>
        </router-link>
      </section>

      <section class="reviews-stack">
        <section class="card-panel" data-testid="reviews-due-queue">
          <p class="section-meta">{{ t('reviews.queueMeta') }}</p>
          <h2>{{ t('reviews.queueTitle') }}</h2>
          <div v-if="dueCards.length" class="queue-list">
            <article
              v-for="card in dueCards.slice(0, 4)"
              :key="card.schedule_id"
              class="queue-item"
            >
              <div class="queue-copy">
                <div class="queue-title-row">
                  <strong>{{ card.title }}</strong>
                  <span class="review-badge">{{ t('reviews.startSrs') }}</span>
                </div>
                <p>{{ card.next_review_at ? formatDateTime(card.next_review_at) : t('reviews.reviewQueueHint') }}</p>
                <p class="origin-line">{{ formatReviewOrigin(card) }}</p>
                <p class="origin-line">{{ formatReviewReason(card) }}</p>
              </div>
              <div class="queue-actions">
                <router-link to="/srs-review" class="btn btn-secondary">{{ t('reviews.startSrs') }}</router-link>
                <router-link
                  v-if="card.origin?.problem_id"
                  :to="buildWorkspaceRoute(card)"
                  class="btn btn-secondary"
                >
                  {{ t('reviews.openWorkspace') }}
                </router-link>
              </div>
            </article>
          </div>
          <div v-else class="empty-block">
            <p class="empty">{{ t('reviews.noDueReviews') }}</p>
            <router-link to="/problems" class="inline-link">
              {{ t('reviews.returnToWorkspace') }}
            </router-link>
          </div>
        </section>

        <section class="card-panel" data-testid="reviews-reinforcement-panel">
          <p class="section-meta">{{ t('reviews.reinforcementMeta') }}</p>
          <h2>{{ t('reviews.reinforcementTitle') }}</h2>
          <div v-if="reinforcementEntries.length" class="card-list">
            <article
              v-for="entry in reinforcementEntries"
              :key="entry.schedule_id"
              class="card-item"
            >
              <div class="card-copy">
                <strong>{{ entry.title }}</strong>
                <p class="card-meta-line"><strong>{{ t('reviews.lifecycleSourceLabel') }}:</strong> {{ formatReviewOrigin(entry) }}</p>
                <p class="card-meta-line"><strong>{{ t('reviews.lifecycleStateLabel') }}:</strong> {{ formatReinforcementState(entry) }}</p>
                <p class="card-meta-line"><strong>{{ t('reviews.lifecycleActionLabel') }}:</strong> {{ formatReinforcementAction(entry) }}</p>
                <router-link :to="`/model-cards/${entry.model_card_id}`" class="review-context-link">
                  {{ t('problemDetail.openModelCard') }}
                </router-link>
              </div>
              <div class="queue-actions">
                <router-link
                  v-if="entry.origin?.problem_id"
                  :to="buildWorkspaceRoute(entry)"
                  class="btn btn-secondary"
                >
                  {{ t('reviews.returnToWorkspace') }}
                </router-link>
              </div>
            </article>
          </div>
          <div v-else class="empty-block">
            <p class="empty">{{ t('reviews.reinforcementEmpty') }}</p>
            <router-link to="/problems" class="inline-link">{{ t('reviews.returnToWorkspace') }}</router-link>
          </div>
        </section>
      </section>

      <details class="card-panel archive-panel" data-testid="review-archive-panel">
        <summary class="section-heading archive-summary" data-testid="review-archive-toggle">
          <div>
            <p class="section-meta">{{ t('reviews.archiveMeta') }}</p>
            <h2>{{ t('reviews.archiveTitle') }}</h2>
          </div>
          <span class="period">{{ savedReviewCount }}</span>
        </summary>

        <div class="archive-body">
          <p class="hero-subtitle">{{ t('reviews.archiveHint') }}</p>
          <div v-if="reviews.length" class="review-archive">
            <div v-for="review in reviews" :key="review.id" class="review-card">
              <div class="review-header">
                <div>
                  <h3>{{ review.review_type }}</h3>
                  <p class="review-date">{{ formatDate(review.created_at) }}</p>
                </div>
                <span class="period">{{ review.period }}</span>
              </div>
              <div class="review-content">
                <p v-if="review.content?.summary"><strong>{{ t('reviews.content') }}:</strong> {{ review.content.summary }}</p>
                <p v-if="review.content?.insights"><strong>{{ t('reviews.insights') }}:</strong> {{ review.content.insights }}</p>
                <p v-if="review.content?.next_steps"><strong>{{ t('reviews.nextSteps') }}:</strong> {{ review.content.next_steps }}</p>
                <p v-if="review.content?.misconceptions?.length">
                  <strong>{{ t('reviews.misconceptions') }}:</strong> {{ review.content.misconceptions.join(' / ') }}
                </p>
              </div>
              <div class="review-actions-row">
                <button class="btn btn-secondary" @click="exportReview(review)">
                  {{ t('common.download') }}
                </button>
              </div>
            </div>
          </div>
          <p v-else class="empty">{{ t('reviews.noReviews') }}</p>
        </div>
      </details>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import api from '@/api'
import PrimaryAsyncStateCard from '@/components/PrimaryAsyncStateCard.vue'
import type { AsyncPageState } from '@/types/ui'

const { t } = useI18n()

const reviews = ref<any[]>([])
const dueCards = ref<any[]>([])
const schedules = ref<any[]>([])
const pageState = ref<AsyncPageState>('loading')
const pageError = ref('')

const savedReviewCount = computed(() => reviews.value.length)
const scheduleByCardId = computed(() => new Map(schedules.value.map((schedule: any) => [String(schedule.model_card_id), schedule])))

const reinforcementEntries = computed(() => {
  return [...schedules.value]
    .filter((schedule: any) => Boolean(schedule.needs_reinforcement))
    .sort((left: any, right: any) => String(right.last_reviewed_at || '').localeCompare(String(left.last_reviewed_at || '')))
    .slice(0, 6)
})

const focusCard = computed(() => {
  if (dueCards.value.length > 0) {
    const firstDueCard = dueCards.value[0]
    return {
      eyebrow: t('reviews.focusTitle'),
      title: t('reviews.focusReady', { count: dueCards.value.length }),
      description: formatReviewOrigin(firstDueCard),
      cta: t('reviews.startReviewCta'),
      to: '/srs-review',
      tone: 'tone-alert',
    }
  }

  if (reinforcementEntries.value.length > 0) {
    const firstEntry = reinforcementEntries.value[0]
    return {
      eyebrow: t('reviews.focusTitle'),
      title: t('reviews.focusReinforcement'),
      description: formatReviewOrigin(firstEntry),
      cta: t('reviews.returnToWorkspace'),
      to: buildWorkspaceRoute(firstEntry),
      tone: 'tone-primary',
    }
  }

  return {
    eyebrow: t('reviews.focusTitle'),
    title: t('reviews.focusEmpty'),
    description: t('reviews.focusEmptyDescription'),
    cta: t('reviews.returnToWorkspace'),
    to: '/problems',
    tone: 'tone-primary',
  }
})

const formatDate = (dateValue: string) => new Date(dateValue).toLocaleDateString()
const formatDateTime = (dateValue: string) => new Date(dateValue).toLocaleString()

const formatReviewOrigin = (entry: any) => {
  const origin = entry?.origin
  if (!origin?.problem_title) return t('reviews.originUnknown')
  const conceptLabel = origin.concept_text || entry?.title || t('problemDetail.derivedConceptsTitle')
  return t('reviews.originFromProblem', {
    concept: conceptLabel,
    problem: origin.problem_title,
  })
}

const formatReviewReason = (entry: any) => {
  const origin = entry?.origin
  if (origin?.learning_mode === 'exploration') return t('reviews.originModeExploration')
  if (origin?.learning_mode === 'socratic') return t('reviews.originModeSocratic')
  return t('reviews.originModeUnknown')
}

const buildWorkspaceRoute = (entry: any) => {
  const problemId = entry?.origin?.problem_id
  if (!problemId) return '/reviews'
  const resumePathId = entry?.reinforcement_target?.resume_path_id || entry?.origin?.source_path_id
  const focusCandidateId = entry?.reinforcement_target?.concept_candidate_id || entry?.origin?.concept_candidate_id
  const focusTurnId = entry?.reinforcement_target?.source_turn_id || entry?.origin?.source_turn_id
  const query: Record<string, string> = {}
  if (resumePathId) query.resume_path = String(resumePathId)
  if (entry?.model_card_id) query.focus_model_card = String(entry.model_card_id)
  if (focusCandidateId) query.focus_candidate = String(focusCandidateId)
  if (focusTurnId) query.focus_turn = String(focusTurnId)
  return {
    path: `/problems/${problemId}`,
    query,
  }
}

const formatReinforcementState = (entry: any) => {
  const schedule = scheduleByCardId.value.get(String(entry.model_card_id))
  if (schedule?.needs_reinforcement) return t('reviews.modelLifecycleStateReinforcement')
  if (schedule?.last_reviewed_at) return t('reviews.modelLifecycleStateReviewed')
  if (schedule?.next_review_at) return t('reviews.modelLifecycleStateScheduled')
  return t('reviews.modelLifecycleStateUnscheduled')
}

const formatReinforcementAction = (entry: any) => {
  const schedule = scheduleByCardId.value.get(String(entry.model_card_id))
  if (!schedule) return t('reviews.modelLifecycleActionSchedule')
  if (schedule.needs_reinforcement) return t('reviews.modelLifecycleActionRevisit')
  return t('reviews.modelLifecycleActionOpen')
}

const fetchReviewLifecycle = async () => {
  pageError.value = ''
  pageState.value = 'loading'
  try {
    const [reviewsRes, dueRes, schedulesRes] = await Promise.all([
      api.get('/reviews/'),
      api.get('/srs/due'),
      api.get('/srs/schedules'),
    ])

    reviews.value = reviewsRes.data || []
    dueCards.value = dueRes.data || []
    schedules.value = schedulesRes.data || []
    pageState.value = 'ready'
  } catch (fetchError) {
    console.error('Failed to fetch review lifecycle data:', fetchError)
    pageError.value = t('reviews.errorMessage')
    pageState.value = 'error'
  }
}

const exportReview = async (review: any) => {
  try {
    const response = await api.get(`/reviews/${review.id}/export`, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([response.data], { type: 'text/markdown' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${review.review_type}-review-${review.period.replace(/\s+/g, '-')}.md`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  } catch (exportError) {
    console.error('Failed to export review:', exportError)
  }
}

onMounted(() => {
  fetchReviewLifecycle()
})
</script>

<style scoped>
.reviews-page {
  display: grid;
  gap: 1.5rem;
}

.hero-shell {
  display: grid;
  gap: 1rem;
}

.hero-copy h1 {
  font-size: clamp(2rem, 3vw, 2.8rem);
  line-height: 1.05;
}

.hero-kicker,
.section-meta {
  color: var(--primary);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.hero-subtitle {
  max-width: 58ch;
  margin-top: 0.65rem;
  color: var(--text-muted);
}

.focus-card,
.card-panel,
.review-card {
  border-radius: 18px;
  border: 1px solid var(--border);
  background: rgba(18, 18, 34, 0.96);
}

.focus-card {
  display: grid;
  gap: 0.75rem;
  padding: 1.5rem;
  text-decoration: none;
  color: var(--text);
  background: linear-gradient(180deg, rgba(26, 26, 46, 0.94), rgba(15, 15, 35, 0.98));
}

.focus-eyebrow,
.review-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.76rem;
}

.focus-eyebrow {
  background: rgba(255, 255, 255, 0.06);
}

.review-badge {
  background: rgba(74, 222, 128, 0.14);
  color: #bbf7d0;
}

.focus-cta {
  color: #bbf7d0;
  font-weight: 700;
}

.tone-alert {
  border-color: rgba(245, 158, 11, 0.35);
}

.tone-primary {
  border-color: rgba(74, 222, 128, 0.25);
}

.reviews-stack {
  display: grid;
  gap: 1rem;
}

.card-panel {
  padding: 1.4rem;
}

.card-panel h2 {
  margin-top: 0.35rem;
  margin-bottom: 0.9rem;
}

.queue-list,
.card-list,
.review-archive {
  display: grid;
  gap: 0.85rem;
}

.queue-item,
.card-item,
.review-card {
  padding: 1rem;
  border-radius: 12px;
  background: var(--bg-dark);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.queue-item,
.card-item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.queue-copy,
.card-copy {
  display: grid;
  gap: 0.3rem;
}

.queue-title-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.origin-line,
.card-meta-line,
.review-date,
.empty {
  color: var(--text-muted);
}

.queue-actions,
.review-actions-row {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
  align-items: flex-start;
}

.empty-block {
  display: grid;
  gap: 0.5rem;
}

.inline-link {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}

.review-context-link {
  width: fit-content;
  color: var(--primary);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 600;
}

.archive-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  list-style: none;
}

.archive-summary::-webkit-details-marker {
  display: none;
}

.archive-body {
  display: grid;
  gap: 1rem;
  margin-top: 1rem;
}

.review-header {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
}

.period {
  color: var(--primary);
  font-weight: 700;
}

.review-content {
  display: grid;
  gap: 0.4rem;
  margin-top: 0.75rem;
}

@media (max-width: 760px) {
  .queue-item,
  .card-item {
    flex-direction: column;
  }
}
</style>
