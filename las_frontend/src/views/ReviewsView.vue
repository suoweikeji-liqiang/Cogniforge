<template>
  <div class="reviews-page" data-testid="review-lifecycle-page">
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

      <div class="metric-grid">
        <div class="metric-card">
          <span>{{ t('reviews.queueCount') }}</span>
          <strong>{{ dueReviewCount }}</strong>
        </div>
        <div class="metric-card">
          <span>{{ t('reviews.scheduledCount') }}</span>
          <strong>{{ scheduledCount }}</strong>
        </div>
        <div class="metric-card">
          <span>{{ t('reviews.savedCount') }}</span>
          <strong>{{ savedReviewCount }}</strong>
        </div>
      </div>
    </section>

    <section class="reviews-grid">
      <section class="card-panel" data-testid="review-queue-panel">
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
              <p v-if="card.origin?.source_turn_preview" class="origin-preview">{{ card.origin.source_turn_preview }}</p>
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
              <router-link :to="`/model-cards/${card.model_card_id}`" class="btn btn-secondary">
                {{ t('problemDetail.openModelCard') }}
              </router-link>
            </div>
          </article>
        </div>
        <div v-else class="empty-block">
          <p class="empty">{{ t('reviews.noDueReviews') }}</p>
          <router-link to="/model-cards" class="inline-link">
            {{ t('reviews.openModelCards') }}
          </router-link>
        </div>
      </section>

      <section class="card-panel" data-testid="review-model-cards-panel">
        <p class="section-meta">{{ t('reviews.lifecycleMeta') }}</p>
        <h2>{{ t('reviews.lifecycleTitle') }}</h2>
        <div v-if="recentModelCards.length" class="card-list">
          <router-link
            v-for="card in recentModelCards"
            :key="card.id"
            :to="`/model-cards/${card.id}`"
            class="card-item"
          >
            <div>
              <strong>{{ card.title }}</strong>
              <p>{{ formatModelCardSupportText(card) }}</p>
            </div>
            <span class="status" :class="{ scheduled: isCardScheduled(card.id) }">
              {{ isCardScheduled(card.id) ? t('modelCards.scheduled') : t('reviews.needsReviewPlan') }}
            </span>
          </router-link>
        </div>
        <div v-else class="empty-block">
          <p class="empty">{{ t('modelCards.createFirst') }}</p>
          <router-link to="/model-cards" class="inline-link">
            {{ t('reviews.openModelCards') }}
          </router-link>
        </div>
      </section>
    </section>

    <section class="card-panel" data-testid="review-archive-panel">
      <div class="section-heading">
        <div>
          <p class="section-meta">{{ t('reviews.archiveMeta') }}</p>
          <h2>{{ t('reviews.archiveTitle') }}</h2>
        </div>
        <button class="btn btn-secondary" @click="showCreateModal = true">
          {{ t('reviews.newReview') }}
        </button>
      </div>

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
    </section>

    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <h2>{{ t('reviews.newReview') }}</h2>
        <form @submit.prevent="createReview">
          <div class="form-group">
            <label>{{ t('reviews.reviewType') }}</label>
            <select v-model="newReview.review_type" required>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div class="form-group">
            <label>{{ t('reviews.period') }}</label>
            <input v-model="newReview.period" type="text" placeholder="e.g., Week 1, January 2024" required />
          </div>
          <div class="form-group">
            <label>{{ t('reviews.content') }}</label>
            <textarea v-model="newReview.summary" rows="2"></textarea>
          </div>
          <div class="form-group">
            <label>{{ t('reviews.insights') }}</label>
            <textarea v-model="newReview.insights" rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>{{ t('reviews.nextSteps') }}</label>
            <textarea v-model="newReview.next_steps" rows="2"></textarea>
          </div>
          <div class="form-group">
            <label>{{ t('reviews.misconceptions') }}</label>
            <textarea v-model="newReview.misconceptions" rows="2"></textarea>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="showCreateModal = false">
              {{ t('common.cancel') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              :disabled="generating"
              @click="generateReview"
            >
              {{ generating ? t('reviews.generating') : t('reviews.generate') }}
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
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import api from '@/api'

const { t } = useI18n()

const reviews = ref<any[]>([])
const dueCards = ref<any[]>([])
const schedules = ref<any[]>([])
const modelCards = ref<any[]>([])
const showCreateModal = ref(false)
const creating = ref(false)
const generating = ref(false)
const error = ref('')

const newReview = ref({
  review_type: 'daily',
  period: '',
  summary: '',
  insights: '',
  next_steps: '',
  misconceptions: '',
})

const recentModelCards = computed(() => modelCards.value.slice(0, 4))
const dueReviewCount = computed(() => dueCards.value.length)
const scheduledCount = computed(() => schedules.value.length)
const savedReviewCount = computed(() => reviews.value.length)
const scheduledCardIds = computed(() => new Set(schedules.value.map((schedule: any) => schedule.model_card_id)))
const scheduleByCardId = computed(() => {
  return new Map(schedules.value.map((schedule: any) => [String(schedule.model_card_id), schedule]))
})

const focusCard = computed(() => {
  if (dueCards.value.length > 0) {
    const firstDueCard = dueCards.value[0]
    return {
      eyebrow: t('reviews.focusTitle'),
      title: t('reviews.focusReady', { count: dueCards.value.length }),
      description: formatReviewOrigin(firstDueCard),
      cta: t('reviews.startSrs'),
      to: '/srs-review',
      tone: 'tone-alert',
    }
  }

  if (recentModelCards.value.length > 0) {
    return {
      eyebrow: t('reviews.focusTitle'),
      title: t('reviews.focusModelCards'),
      description: recentModelCards.value[0].title,
      cta: t('reviews.openModelCards'),
      to: `/model-cards/${recentModelCards.value[0].id}`,
      tone: 'tone-primary',
    }
  }

  return {
    eyebrow: t('reviews.focusTitle'),
    title: t('reviews.focusEmpty'),
    description: t('reviews.subtitle'),
    cta: t('reviews.openModelCards'),
    to: '/model-cards',
    tone: 'tone-primary',
  }
})

const formatDate = (dateValue: string) => new Date(dateValue).toLocaleDateString()
const formatDateTime = (dateValue: string) => new Date(dateValue).toLocaleString()

const isCardScheduled = (cardId: string) => scheduledCardIds.value.has(cardId)

const formatReviewOrigin = (entry: any) => {
  const origin = entry?.origin
  if (!origin?.problem_title) {
    return t('reviews.originUnknown')
  }
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
  return {
    path: `/problems/${problemId}`,
    query: resumePathId ? { resume_path: resumePathId } : {},
  }
}

const formatModelCardSupportText = (card: any) => {
  const schedule = scheduleByCardId.value.get(String(card.id))
  if (!schedule) {
    return card.user_notes || t('reviews.modelLifecycleHint')
  }

  const originLabel = formatReviewOrigin(schedule)
  const reason = formatReviewReason(schedule)
  const origin = schedule.origin?.source_turn_preview
  if (origin) {
    return `${originLabel}. ${reason} ${origin}`
  }
  return `${originLabel}. ${reason}`
}

const fetchReviewLifecycle = async () => {
  try {
    const [reviewsRes, dueRes, schedulesRes, modelCardsRes] = await Promise.all([
      api.get('/reviews/'),
      api.get('/srs/due').catch(() => ({ data: [] })),
      api.get('/srs/schedules').catch(() => ({ data: [] })),
      api.get('/model-cards/').catch(() => ({ data: [] })),
    ])

    reviews.value = reviewsRes.data || []
    dueCards.value = dueRes.data || []
    schedules.value = schedulesRes.data || []
    modelCards.value = modelCardsRes.data || []
  } catch (fetchError) {
    console.error('Failed to fetch review lifecycle data:', fetchError)
  }
}

const resetForm = () => {
  newReview.value = {
    review_type: 'daily',
    period: '',
    summary: '',
    insights: '',
    next_steps: '',
    misconceptions: '',
  }
}

const createReview = async () => {
  error.value = ''
  creating.value = true

  try {
    await api.post('/reviews/', {
      review_type: newReview.value.review_type,
      period: newReview.value.period,
      content: {
        summary: newReview.value.summary,
        insights: newReview.value.insights,
        next_steps: newReview.value.next_steps,
        misconceptions: newReview.value.misconceptions
          ? newReview.value.misconceptions.split('\n').map((item) => item.trim()).filter(Boolean)
          : [],
      },
    })

    showCreateModal.value = false
    resetForm()
    await fetchReviewLifecycle()
  } catch (createError: any) {
    error.value = createError.response?.data?.detail || 'Failed to create review'
  } finally {
    creating.value = false
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

const generateReview = async () => {
  error.value = ''
  generating.value = true

  try {
    const response = await api.post('/reviews/generate', {
      review_type: newReview.value.review_type,
      period: newReview.value.period,
    })
    const content = response.data.content || {}
    newReview.value.summary = content.summary || ''
    newReview.value.insights = content.insights || ''
    newReview.value.next_steps = content.next_steps || ''
    newReview.value.misconceptions = (content.misconceptions || []).join('\n')
  } catch (generateError: any) {
    error.value = generateError.response?.data?.detail || 'Failed to generate review'
  } finally {
    generating.value = false
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
.metric-card,
.review-card {
  border-radius: 18px;
  border: 1px solid var(--border);
  background: rgba(18, 18, 34, 0.96);
}

.focus-card {
  display: grid;
  gap: 0.75rem;
  padding: 1.5rem;
  color: var(--text);
  text-decoration: none;
  background: linear-gradient(180deg, rgba(26, 26, 46, 0.94), rgba(15, 15, 35, 0.98));
}

.focus-eyebrow,
.review-badge,
.status,
.period {
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

.metric-grid,
.reviews-grid {
  display: grid;
  gap: 1rem;
}

.metric-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metric-card {
  padding: 1rem 1.1rem;
}

.metric-card span {
  display: block;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.metric-card strong {
  display: block;
  margin-top: 0.35rem;
  font-size: 1.8rem;
}

.reviews-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.card-panel {
  padding: 1.4rem;
}

.card-panel h2 {
  margin-top: 0.35rem;
  margin-bottom: 0.9rem;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.queue-list,
.card-list,
.review-archive {
  display: grid;
  gap: 0.85rem;
}

.queue-item,
.card-item {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.95rem;
  border-radius: 12px;
  background: var(--bg-dark);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: var(--text);
  text-decoration: none;
}

.queue-copy {
  min-width: 0;
  display: grid;
  gap: 0.3rem;
}

.queue-title-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.queue-actions {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: flex-end;
}

.origin-line,
.origin-preview {
  font-size: 0.84rem;
  color: var(--text-muted);
}

.origin-preview {
  white-space: pre-wrap;
}

.queue-item p,
.card-item p,
.review-content p,
.empty {
  color: var(--text-muted);
}

.review-badge {
  background: rgba(74, 222, 128, 0.14);
  color: #bbf7d0;
}

.status {
  background: rgba(96, 165, 250, 0.14);
  color: #bfdbfe;
}

.status.scheduled {
  background: rgba(74, 222, 128, 0.14);
  color: #bbf7d0;
}

.period {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-muted);
}

.review-card {
  padding: 1rem;
}

.review-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.review-header h3 {
  text-transform: capitalize;
}

.review-date {
  margin-top: 0.3rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.review-content strong {
  color: var(--primary);
}

.review-actions-row {
  margin-top: 1rem;
}

.empty-block {
  display: grid;
  gap: 0.5rem;
}

.inline-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 18, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.modal {
  width: min(640px, 100%);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 1.5rem;
}

.form-group {
  display: grid;
  gap: 0.45rem;
  margin-bottom: 1rem;
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.error {
  margin-bottom: 1rem;
  color: #fca5a5;
}

@media (max-width: 900px) {
  .metric-grid,
  .reviews-grid {
    grid-template-columns: 1fr;
  }

  .section-heading,
  .review-header,
  .queue-item,
  .card-item {
    display: grid;
  }

  .queue-actions {
    justify-content: flex-start;
  }
}
</style>
