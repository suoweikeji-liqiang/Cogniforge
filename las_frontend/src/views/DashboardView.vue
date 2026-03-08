<template>
  <div class="dashboard">
    <section class="hero-shell">
      <div class="hero-copy">
        <p class="hero-kicker">{{ t('dashboard.focusTitle') }}</p>
        <h1>{{ t('dashboard.welcome') }}, {{ authStore.user?.username }}</h1>
        <p class="hero-subtitle">{{ t('dashboard.focusSubtitle') }}</p>
      </div>

      <div class="focus-grid">
        <router-link :to="focusCard.to" class="focus-card" :class="focusCard.tone">
          <span class="focus-eyebrow">{{ focusCard.eyebrow }}</span>
          <h2>{{ focusCard.title }}</h2>
          <p>{{ focusCard.description }}</p>
          <span class="focus-cta">{{ focusCard.cta }}</span>
        </router-link>

        <div class="focus-side">
          <div class="review-assistant card-panel">
            <div class="section-meta">{{ t('dashboard.reviewAssistant') }}</div>
            <h3>{{ t('dashboard.prioritySummary') }}</h3>
            <p>{{ t('dashboard.reviewRecommendation', {
              type: t(`dashboard.reviewTypes.${recommendedReview.type}`),
              period: recommendedReview.period,
            }) }}</p>
            <div class="assistant-actions">
              <button
                v-if="!recommendedReviewExists"
                class="btn btn-primary"
                :disabled="reviewGenerating"
                @click="generateRecommendedReview"
              >
                {{ reviewGenerating ? t('reviews.generating') : t('dashboard.generateReviewNow') }}
              </button>
              <router-link v-else to="/reviews" class="inline-link">
                {{ t('dashboard.viewReviewHistory') }}
              </router-link>
            </div>
            <p v-if="reviewMessage" class="assistant-message">{{ reviewMessage }}</p>
          </div>

          <div class="momentum-card card-panel">
            <div class="section-meta">{{ t('dashboard.keepMomentum') }}</div>
            <h3>{{ t('dashboard.activityWindow') }}</h3>
            <p>{{ t('dashboard.momentumDescription') }}</p>
            <div class="momentum-metrics">
              <div>
                <strong>{{ activeDays }}</strong>
                <span>{{ t('dashboard.activeDays') }}</span>
              </div>
              <div>
                <strong>{{ stats.dueReviews }}</strong>
                <span>{{ t('dashboard.openReviews') }}</span>
              </div>
              <div>
                <strong>{{ stats.practice }}</strong>
                <span>{{ t('dashboard.practiceTasks') }}</span>
              </div>
            </div>
          </div>

          <div class="retrieval-card card-panel">
            <div class="section-meta">{{ t('dashboard.retrievalObserver') }}</div>
            <h3>{{ t('dashboard.retrievalTitle') }}</h3>
            <p>{{ t('dashboard.retrievalDescription') }}</p>
            <div class="retrieval-metrics">
              <div>
                <strong>{{ retrievalSummary.total_events }}</strong>
                <span>{{ t('dashboard.retrievalEvents') }}</span>
              </div>
              <div>
                <strong>{{ retrievalSummary.average_hits }}</strong>
                <span>{{ t('dashboard.averageHits') }}</span>
              </div>
              <div>
                <strong>{{ retrievalSummary.total_hits }}</strong>
                <span>{{ t('dashboard.totalHits') }}</span>
              </div>
            </div>
            <div class="retrieval-health" :class="retrievalSummary.health_status">
              <strong>{{ t(`dashboard.retrievalHealth.${retrievalSummary.health_status || 'healthy'}`) }}</strong>
              <span>
                {{ t('dashboard.retrievalHealthMeta', {
                  zeroHits: retrievalSummary.zero_hit_events,
                  poorHits: retrievalSummary.poor_hit_events,
                }) }}
              </span>
            </div>
            <div v-if="retrievalLogs.length" class="retrieval-list">
              <div
                v-for="log in retrievalLogs"
                :key="log.id"
                class="retrieval-item"
              >
                <div class="retrieval-item-top">
                  <span class="retrieval-source">{{ formatRetrievalSource(log.source) }}</span>
                  <span class="retrieval-count">{{ log.result_count }} {{ t('dashboard.hitsUnit') }}</span>
                </div>
                <p class="retrieval-query">{{ log.query }}</p>
                <p class="retrieval-preview">{{ summarizeRetrievalItems(log.items) }}</p>
              </div>
            </div>
            <p v-else class="empty">{{ t('dashboard.noRetrievalLogs') }}</p>
          </div>
        </div>
      </div>
    </section>

    <section class="stats-section">
      <div class="stats-grid">
        <div class="stat-card">
          <h3>{{ t('dashboard.problems') }}</h3>
          <p class="stat-number">{{ stats.problems }}</p>
        </div>
        <div class="stat-card">
          <h3>{{ t('dashboard.modelCards') }}</h3>
          <p class="stat-number">{{ stats.modelCards }}</p>
        </div>
        <div class="stat-card">
          <h3>{{ t('dashboard.conversations') }}</h3>
          <p class="stat-number">{{ stats.conversations }}</p>
        </div>
        <div class="stat-card">
          <h3>{{ t('dashboard.practiceTasks') }}</h3>
          <p class="stat-number">{{ stats.practice }}</p>
        </div>
      </div>
    </section>

    <section class="actions-section">
      <div class="section-heading">
        <div>
          <p class="section-meta">{{ t('dashboard.quickActions') }}</p>
          <h2>{{ t('dashboard.quickActionTitle') }}</h2>
        </div>
      </div>
      <div class="actions-grid">
        <router-link to="/problems" class="action-card">
          <h3>{{ t('dashboard.newProblem') }}</h3>
          <p>{{ t('dashboard.startLearning') }}</p>
        </router-link>
        <router-link to="/model-cards" class="action-card">
          <h3>{{ t('dashboard.modelLibrary') }}</h3>
          <p>{{ t('dashboard.browseModels') }}</p>
        </router-link>
        <router-link :to="explorationAction.to" class="action-card" data-testid="dashboard-exploration-action">
          <h3>{{ explorationAction.title }}</h3>
          <p>{{ explorationAction.description }}</p>
        </router-link>
        <router-link to="/practice" class="action-card">
          <h3>{{ t('dashboard.practiceTest') }}</h3>
          <p>{{ t('dashboard.testUnderstanding') }}</p>
        </router-link>
      </div>
    </section>

    <section class="insights-grid">
      <div class="heatmap-section card-panel">
        <div class="section-heading">
          <div>
            <p class="section-meta">{{ t('dashboard.heatmapTitle') }}</p>
            <h2>{{ t('dashboard.activityWindow') }}</h2>
          </div>
        </div>
        <div class="heatmap-grid">
          <div
            v-for="day in heatmapDays"
            :key="day.date"
            class="heatmap-cell"
            :class="'level-' + day.level"
            :title="day.date + ': ' + day.count + ' activities'"
          ></div>
        </div>
      </div>

      <div class="recent-section card-panel">
        <div class="section-heading">
          <div>
            <p class="section-meta">{{ t('dashboard.recentActivity') }}</p>
            <h2>{{ t('dashboard.recentTitle') }}</h2>
          </div>
        </div>
        <div v-if="recentProblems.length" class="recent-list">
          <router-link
            v-for="problem in recentProblems"
            :key="problem.id"
            :to="`/problems/${problem.id}`"
            class="recent-item"
          >
            <div>
              <h4>{{ problem.title }}</h4>
              <p>{{ problem.description || t('dashboard.resumeLatestProblemDescription') }}</p>
            </div>
            <span class="status">{{ problem.status }}</span>
          </router-link>
        </div>
        <p v-else class="empty">{{ t('dashboard.noRecent') }}</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'

const { t } = useI18n()
const authStore = useAuthStore()

const stats = ref({
  problems: 0,
  modelCards: 0,
  conversations: 0,
  practice: 0,
  dueReviews: 0,
})

const recentProblems = ref<any[]>([])
const heatmapDays = ref<any[]>([])
const reviewGenerating = ref(false)
const reviewMessage = ref('')
const existingReviews = ref<any[]>([])
const retrievalSummary = ref({
  total_events: 0,
  total_hits: 0,
  average_hits: 0,
  zero_hit_events: 0,
  poor_hit_events: 0,
  zero_hit_rate: 0,
  health_status: 'healthy',
  source_breakdown: {} as Record<string, number>,
})
const retrievalLogs = ref<any[]>([])

const buildHeatmap = (activity: Record<string, number>) => {
  const days = []
  const now = new Date()
  for (let i = 89; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    const count = activity[key] || 0
    const level = count === 0 ? 0 : count <= 1 ? 1 : count <= 3 ? 2 : count <= 5 ? 3 : 4
    days.push({ date: key, count, level })
  }
  return days
}

const getWeekPeriod = (date: Date) => {
  const utcDate = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const day = utcDate.getUTCDay() || 7
  utcDate.setUTCDate(utcDate.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1))
  const weekNo = Math.ceil((((utcDate.getTime() - yearStart.getTime()) / 86400000) + 1) / 7)
  return `${utcDate.getUTCFullYear()}-W${String(weekNo).padStart(2, '0')}`
}

const recommendedReview = computed(() => {
  const now = new Date()
  if (now.getDate() === 1) {
    return {
      type: 'monthly',
      period: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
    }
  }
  if (now.getDay() === 1) {
    return {
      type: 'weekly',
      period: getWeekPeriod(now),
    }
  }
  return {
    type: 'daily',
    period: now.toISOString().slice(0, 10),
  }
})

const recommendedReviewExists = computed(() =>
  existingReviews.value.some((review) =>
    review.review_type === recommendedReview.value.type &&
    review.period === recommendedReview.value.period
  )
)

const activeDays = computed(() =>
  heatmapDays.value.filter((day: any) => day.count > 0).length
)

const formatRetrievalSource = (source: string) =>
  t(`dashboard.retrievalSources.${source}`, source.replace(/_/g, ' '))

const summarizeRetrievalItems = (items: any[]) => {
  if (!items?.length) {
    return t('dashboard.noRetrievalHits')
  }
  return items
    .slice(0, 2)
    .map((item) => item.title)
    .join(' · ')
}

const focusCard = computed(() => {
  if (stats.value.dueReviews > 0) {
    return {
      eyebrow: t('dashboard.priorityNow'),
      title: t('dashboard.reviewQueueReady', { count: stats.value.dueReviews }),
      description: t('dashboard.reviewQueueDescription'),
      cta: t('dashboard.startReview'),
      to: '/srs-review',
      tone: 'tone-alert',
    }
  }

  if (recentProblems.value.length > 0) {
    return {
      eyebrow: t('dashboard.priorityNow'),
      title: t('dashboard.resumeLatestProblem'),
      description: recentProblems.value[0].title,
      cta: t('dashboard.openProblem'),
      to: `/problems/${recentProblems.value[0].id}`,
      tone: 'tone-primary',
    }
  }

  if (stats.value.modelCards === 0) {
    return {
      eyebrow: t('dashboard.priorityNow'),
      title: t('dashboard.buildModelLibrary'),
      description: t('dashboard.modelLibraryDescription'),
      cta: t('dashboard.createModelCard'),
      to: '/model-cards',
      tone: 'tone-neutral',
    }
  }

  return {
    eyebrow: t('dashboard.priorityNow'),
    title: t('dashboard.captureFirstProblem'),
    description: t('dashboard.resumeLatestProblemDescription'),
    cta: t('dashboard.newProblem'),
    to: '/problems',
    tone: 'tone-primary',
  }
})

const explorationAction = computed(() => {
  if (recentProblems.value.length > 0) {
    return {
      to: `/problems/${recentProblems.value[0].id}`,
      title: t('dashboard.exploreInWorkspace'),
      description: t('dashboard.exploreInWorkspaceDescription', {
        title: recentProblems.value[0].title,
      }),
    }
  }

  return {
    to: '/problems',
    title: t('dashboard.exploreInWorkspace'),
    description: t('dashboard.exploreInWorkspaceFallback'),
  }
})

const fetchDashboardData = async () => {
  try {
    const [
      problemsRes,
      cardsRes,
      convsRes,
      practiceRes,
      statsRes,
      heatmapRes,
      reviewsRes,
      retrievalSummaryRes,
      retrievalLogsRes,
    ] = await Promise.all([
      api.get('/problems/'),
      api.get('/model-cards/'),
      api.get('/conversations/'),
      api.get('/practice/tasks'),
      api.get('/statistics/overview'),
      api.get('/statistics/heatmap'),
      api.get('/reviews/').catch(() => ({ data: [] })),
      api.get('/retrieval/summary').catch(() => ({
        data: {
          total_events: 0,
          total_hits: 0,
          average_hits: 0,
          zero_hit_events: 0,
          poor_hit_events: 0,
          zero_hit_rate: 0,
          health_status: 'healthy',
          source_breakdown: {},
        },
      })),
      api.get('/retrieval/logs', { params: { limit: 3 } }).catch(() => ({ data: [] })),
    ])

    stats.value.problems = problemsRes.data.length
    stats.value.modelCards = cardsRes.data.length
    stats.value.conversations = convsRes.data.length
    stats.value.practice = practiceRes.data.length
    stats.value.dueReviews = statsRes.data.due_reviews || 0
    recentProblems.value = problemsRes.data.slice(0, 5)
    heatmapDays.value = buildHeatmap(heatmapRes.data.activity || {})
    existingReviews.value = reviewsRes.data
    retrievalSummary.value = retrievalSummaryRes.data
    retrievalLogs.value = retrievalLogsRes.data
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
  }
}

const generateRecommendedReview = async () => {
  reviewGenerating.value = true
  reviewMessage.value = ''

  try {
    const generated = await api.post('/reviews/generate', {
      review_type: recommendedReview.value.type,
      period: recommendedReview.value.period,
    })

    await api.post('/reviews/', {
      review_type: recommendedReview.value.type,
      period: recommendedReview.value.period,
      content: generated.data.content,
    })

    reviewMessage.value = t('dashboard.reviewCreated')
    await fetchDashboardData()
  } catch (error) {
    console.error('Failed to generate recommended review:', error)
    reviewMessage.value = t('dashboard.reviewCreateFailed')
  } finally {
    reviewGenerating.value = false
  }
}

onMounted(() => {
  fetchDashboardData()
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

.hero-shell {
  display: flex;
  flex-direction: column;
  gap: 1.4rem;
}

.hero-copy h1 {
  font-size: clamp(2rem, 3vw, 3rem);
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
  max-width: 680px;
  margin-top: 0.75rem;
  color: var(--text-muted);
  font-size: 1rem;
}

.focus-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.9fr);
  gap: 1rem;
}

.focus-card,
.card-panel {
  border-radius: 18px;
  padding: 1.5rem;
  border: 1px solid var(--border);
}

.focus-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 280px;
  text-decoration: none;
  color: var(--text);
  background: linear-gradient(180deg, rgba(26, 26, 46, 0.94), rgba(15, 15, 35, 0.98));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.focus-card h2 {
  margin-top: 0.75rem;
  font-size: 1.75rem;
  line-height: 1.1;
}

.focus-card p {
  margin-top: 0.75rem;
  color: #d3d7df;
  max-width: 42ch;
}

.focus-eyebrow {
  display: inline-flex;
  align-self: flex-start;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-muted);
  font-size: 0.78rem;
}

.focus-cta {
  margin-top: auto;
  display: inline-flex;
  align-self: flex-start;
  padding: 0.7rem 0.95rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.09);
}

.tone-primary {
  border-color: rgba(74, 222, 128, 0.2);
  background:
    radial-gradient(circle at top right, rgba(74, 222, 128, 0.18), transparent 32%),
    linear-gradient(180deg, rgba(21, 33, 29, 0.96), rgba(13, 17, 27, 0.98));
}

.tone-alert {
  border-color: rgba(250, 204, 21, 0.2);
  background:
    radial-gradient(circle at top right, rgba(250, 204, 21, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(40, 32, 17, 0.96), rgba(20, 20, 24, 0.98));
}

.tone-neutral {
  border-color: rgba(255, 255, 255, 0.08);
}

.focus-side {
  display: grid;
  gap: 1rem;
}

.card-panel {
  background: var(--bg-card);
}

.card-panel h3 {
  margin-top: 0.45rem;
  font-size: 1.15rem;
}

.card-panel p {
  margin-top: 0.55rem;
  color: var(--text-muted);
}

.assistant-actions {
  margin-top: 1rem;
}

.inline-link {
  color: var(--primary);
  text-decoration: none;
}

.assistant-message {
  margin-top: 0.75rem;
  color: var(--primary);
  font-size: 0.875rem;
}

.momentum-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
  margin-top: 1rem;
}

.momentum-metrics div,
.retrieval-metrics div {
  padding: 0.8rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
}

.momentum-metrics strong,
.retrieval-metrics strong {
  display: block;
  font-size: 1.5rem;
  color: var(--text);
}

.momentum-metrics span,
.retrieval-metrics span {
  display: block;
  margin-top: 0.25rem;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.retrieval-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
  margin-top: 1rem;
}

.retrieval-health {
  margin-top: 0.85rem;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
}

.retrieval-health strong {
  display: block;
  font-size: 0.92rem;
}

.retrieval-health span {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.retrieval-health.healthy {
  border-color: rgba(74, 222, 128, 0.25);
}

.retrieval-health.needs_attention {
  border-color: rgba(250, 204, 21, 0.28);
}

.retrieval-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
}

.retrieval-item {
  padding: 0.9rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
}

.retrieval-item-top {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
}

.retrieval-source,
.retrieval-count {
  font-size: 0.8rem;
  color: var(--primary);
}

.retrieval-query {
  margin-top: 0.45rem;
  color: var(--text);
  font-size: 0.92rem;
}

.retrieval-preview {
  margin-top: 0.35rem;
  color: var(--text-muted);
  font-size: 0.84rem;
}

.stats-grid,
.actions-grid,
.insights-grid {
  display: grid;
  gap: 1rem;
}

.stats-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stat-card {
  padding: 1.25rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.stat-card h3 {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.stat-number {
  margin-top: 0.45rem;
  font-size: 2rem;
  font-weight: 700;
  color: var(--primary);
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: end;
  margin-bottom: 0.9rem;
}

.section-heading h2 {
  margin-top: 0.25rem;
}

.actions-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.action-card {
  padding: 1.25rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.03);
  text-decoration: none;
  color: var(--text);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.action-card:hover {
  transform: translateY(-2px);
  border-color: rgba(74, 222, 128, 0.28);
}

.action-card h3 {
  color: var(--primary);
}

.action-card p {
  margin-top: 0.45rem;
  color: var(--text-muted);
}

.insights-grid {
  grid-template-columns: 1.15fr 0.95fr;
}

.heatmap-grid {
  display: grid;
  grid-template-columns: repeat(18, 1fr);
  gap: 0.35rem;
  margin-top: 1rem;
}

.heatmap-cell {
  aspect-ratio: 1;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.04);
}

.level-1 { background: rgba(74, 222, 128, 0.25); }
.level-2 { background: rgba(74, 222, 128, 0.45); }
.level-3 { background: rgba(74, 222, 128, 0.65); }
.level-4 { background: rgba(74, 222, 128, 0.9); }

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  margin-top: 1rem;
}

.recent-item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  text-decoration: none;
  color: var(--text);
}

.recent-item p {
  margin-top: 0.35rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.status {
  align-self: flex-start;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  background: rgba(74, 222, 128, 0.12);
  color: var(--primary);
  font-size: 0.78rem;
  text-transform: capitalize;
}

.empty {
  margin-top: 1rem;
  color: var(--text-muted);
}

@media (max-width: 1024px) {
  .focus-grid,
  .insights-grid,
  .actions-grid,
  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 768px) {
  .focus-grid,
  .insights-grid,
  .actions-grid,
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .momentum-metrics {
    grid-template-columns: 1fr;
  }

  .retrieval-metrics {
    grid-template-columns: 1fr;
  }

  .recent-item {
    flex-direction: column;
  }

  .heatmap-grid {
    grid-template-columns: repeat(10, 1fr);
  }
}
</style>
