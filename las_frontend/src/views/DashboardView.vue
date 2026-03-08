<template>
  <div class="dashboard" data-testid="resume-dashboard">
    <section class="hero-shell">
      <div class="hero-copy">
        <p class="hero-kicker">{{ t('dashboard.focusTitle') }}</p>
        <h1>{{ t('dashboard.welcome') }}, {{ authStore.user?.username }}</h1>
        <p class="hero-subtitle">{{ t('dashboard.focusSubtitle') }}</p>
      </div>

      <router-link :to="focusCard.to" class="focus-card" :class="focusCard.tone" data-testid="dashboard-focus-card">
        <span class="focus-eyebrow">{{ focusCard.eyebrow }}</span>
        <h2>{{ focusCard.title }}</h2>
        <p>{{ focusCard.description }}</p>
        <span class="focus-cta">{{ focusCard.cta }}</span>
      </router-link>

      <div class="metric-grid">
        <div class="metric-card">
          <span>{{ t('dashboard.activeProblems') }}</span>
          <strong>{{ activeProblemCount }}</strong>
        </div>
        <div class="metric-card">
          <span>{{ t('dashboard.openReviews') }}</span>
          <strong>{{ dueReviewCount }}</strong>
        </div>
        <div class="metric-card">
          <span>{{ t('dashboard.modelCards') }}</span>
          <strong>{{ modelCards.length }}</strong>
        </div>
      </div>
    </section>

    <section class="dashboard-grid">
      <section class="card-panel" data-testid="dashboard-problems-panel">
        <p class="section-meta">{{ t('dashboard.resumePanelMeta') }}</p>
        <h2>{{ t('dashboard.resumeSectionTitle') }}</h2>
        <div v-if="recentProblems.length" class="resume-list">
          <router-link
            v-for="problem in recentProblems"
            :key="problem.id"
            :to="`/problems/${problem.id}`"
            class="resume-item"
          >
            <div>
              <strong>{{ problem.title }}</strong>
              <p>{{ problem.description || t('dashboard.resumeLatestProblemDescription') }}</p>
            </div>
            <span class="status">{{ problem.status }}</span>
          </router-link>
        </div>
        <p v-else class="empty">{{ t('dashboard.noRecent') }}</p>
      </section>

      <section class="card-panel" data-testid="dashboard-review-panel">
        <p class="section-meta">{{ t('dashboard.reviewPanelMeta') }}</p>
        <h2>{{ t('dashboard.reviewQueueTitle') }}</h2>
        <div v-if="dueCards.length" class="review-list">
          <router-link
            v-for="card in dueCards.slice(0, 4)"
            :key="card.schedule_id"
            to="/srs-review"
            class="review-item"
          >
            <div>
              <strong>{{ card.title }}</strong>
              <p>{{ card.user_notes || t('dashboard.reviewQueueDescription') }}</p>
            </div>
            <span class="review-badge">{{ t('dashboard.startReview') }}</span>
          </router-link>
        </div>
        <div v-else class="empty-block">
          <p class="empty">{{ t('dashboard.noDueReviews') }}</p>
          <router-link to="/model-cards" class="inline-link">
            {{ t('dashboard.createModelCard') }}
          </router-link>
        </div>
      </section>
    </section>

    <section class="card-panel" data-testid="dashboard-model-cards-panel">
      <p class="section-meta">{{ t('dashboard.modelsPanelMeta') }}</p>
      <h2>{{ t('dashboard.modelCardsSectionTitle') }}</h2>
      <div v-if="recentModelCards.length" class="model-grid">
        <router-link
          v-for="card in recentModelCards"
          :key="card.id"
          :to="`/model-cards/${card.id}`"
          class="model-card"
        >
          <strong>{{ card.title }}</strong>
          <p>{{ card.user_notes || t('dashboard.modelLibraryDescription') }}</p>
        </router-link>
      </div>
      <p v-else class="empty">{{ t('dashboard.noRecentModelCards') }}</p>
    </section>

    <section class="actions-section">
      <div class="section-heading">
        <div>
          <p class="section-meta">{{ t('dashboard.quickActions') }}</p>
          <h2>{{ t('dashboard.nextMovesTitle') }}</h2>
        </div>
      </div>
      <div class="actions-grid">
        <router-link to="/problems" class="action-card">
          <h3>{{ t('dashboard.newProblem') }}</h3>
          <p>{{ t('dashboard.startLearning') }}</p>
        </router-link>
        <router-link :to="explorationAction.to" class="action-card" data-testid="dashboard-exploration-action">
          <h3>{{ explorationAction.title }}</h3>
          <p>{{ explorationAction.description }}</p>
        </router-link>
        <router-link to="/model-cards" class="action-card">
          <h3>{{ t('dashboard.modelLibrary') }}</h3>
          <p>{{ t('dashboard.browseModels') }}</p>
        </router-link>
        <router-link to="/srs-review" class="action-card">
          <h3>{{ t('dashboard.reviewQueueTitle') }}</h3>
          <p>{{ t('dashboard.reviewQueueDescription') }}</p>
        </router-link>
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

const problems = ref<any[]>([])
const modelCards = ref<any[]>([])
const dueCards = ref<any[]>([])

const recentProblems = computed(() => problems.value.slice(0, 5))
const recentModelCards = computed(() => modelCards.value.slice(0, 4))
const dueReviewCount = computed(() => dueCards.value.length)
const activeProblemCount = computed(() =>
  problems.value.filter((problem) => problem.status !== 'completed').length
)

const focusCard = computed(() => {
  if (dueCards.value.length > 0) {
    return {
      eyebrow: t('dashboard.priorityNow'),
      title: t('dashboard.reviewQueueReady', { count: dueCards.value.length }),
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
    const [problemsRes, cardsRes, dueRes] = await Promise.all([
      api.get('/problems/'),
      api.get('/model-cards/'),
      api.get('/srs/due').catch(() => ({ data: [] })),
    ])

    problems.value = problemsRes.data || []
    modelCards.value = cardsRes.data || []
    dueCards.value = dueRes.data || []
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
  }
}

onMounted(fetchDashboardData)
</script>

<style scoped>
.dashboard {
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
  max-width: 56ch;
  margin-top: 0.65rem;
  color: var(--text-muted);
}

.focus-card,
.card-panel,
.metric-card,
.action-card {
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
.review-badge,
.status {
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
.dashboard-grid,
.model-grid,
.actions-grid {
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

.dashboard-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.card-panel {
  padding: 1.4rem;
}

.card-panel h2,
.actions-section h2 {
  margin-top: 0.35rem;
  margin-bottom: 0.9rem;
}

.resume-list,
.review-list {
  display: grid;
  gap: 0.75rem;
}

.resume-item,
.review-item,
.model-card,
.action-card {
  text-decoration: none;
  color: var(--text);
}

.resume-item,
.review-item,
.model-card {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.9rem;
  border-radius: 12px;
  background: var(--bg-dark);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.resume-item p,
.review-item p,
.model-card p,
.empty {
  color: var(--text-muted);
}

.status {
  background: rgba(96, 165, 250, 0.14);
  color: #bfdbfe;
}

.review-badge {
  background: rgba(74, 222, 128, 0.14);
  color: #bbf7d0;
}

.model-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.model-card {
  display: grid;
  gap: 0.5rem;
}

.actions-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.action-card {
  padding: 1rem 1.1rem;
}

.action-card h3 {
  margin-bottom: 0.45rem;
}

.action-card p {
  color: var(--text-muted);
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

@media (max-width: 900px) {
  .metric-grid,
  .dashboard-grid,
  .actions-grid {
    grid-template-columns: 1fr;
  }
}
</style>
