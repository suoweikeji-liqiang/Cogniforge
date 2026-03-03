<template>
  <div class="dashboard">
    <h1>{{ t('dashboard.welcome') }}, {{ authStore.user?.username }}</h1>
    
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
      <div class="stat-card stat-card-alert" v-if="stats.dueReviews > 0">
        <h3>{{ t('dashboard.dueReviews') }}</h3>
        <p class="stat-number due">{{ stats.dueReviews }}</p>
        <router-link to="/srs-review" class="review-link">{{ t('dashboard.startReview') }}</router-link>
      </div>
    </div>
    
    <div class="actions-section">
      <h2>{{ t('dashboard.quickActions') }}</h2>
      <div class="actions-grid">
        <router-link to="/problems" class="action-card">
          <h3>{{ t('dashboard.newProblem') }}</h3>
          <p>{{ t('dashboard.startLearning') }}</p>
        </router-link>
        <router-link to="/model-cards" class="action-card">
          <h3>{{ t('dashboard.modelLibrary') }}</h3>
          <p>{{ t('dashboard.browseModels') }}</p>
        </router-link>
        <router-link to="/chat" class="action-card">
          <h3>{{ t('dashboard.aiChat') }}</h3>
          <p>{{ t('dashboard.chatAssistant') }}</p>
        </router-link>
        <router-link to="/practice" class="action-card">
          <h3>{{ t('dashboard.practiceTest') }}</h3>
          <p>{{ t('dashboard.testUnderstanding') }}</p>
        </router-link>
      </div>
    </div>

    <div class="review-assistant card-panel">
      <div class="assistant-header">
        <div>
          <h2>{{ t('dashboard.reviewAssistant') }}</h2>
          <p>{{ t('dashboard.reviewRecommendation', {
            type: t(`dashboard.reviewTypes.${recommendedReview.type}`),
            period: recommendedReview.period,
          }) }}</p>
        </div>
        <div class="assistant-actions">
          <button
            v-if="!recommendedReviewExists"
            class="btn btn-primary"
            :disabled="reviewGenerating"
            @click="generateRecommendedReview"
          >
            {{ reviewGenerating ? t('reviews.generating') : t('dashboard.generateReviewNow') }}
          </button>
          <router-link v-else to="/reviews" class="review-link">
            {{ t('dashboard.viewReviewHistory') }}
          </router-link>
        </div>
      </div>
      <p v-if="reviewMessage" class="assistant-message">{{ reviewMessage }}</p>
    </div>

    <!-- Learning Heatmap -->
    <div class="heatmap-section">
      <h2>{{ t('dashboard.heatmapTitle') }}</h2>
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

    <div class="recent-section">
      <h2>{{ t('dashboard.recentActivity') }}</h2>
      <div v-if="recentProblems.length" class="recent-list">
        <router-link 
          v-for="problem in recentProblems" 
          :key="problem.id" 
          :to="`/problems/${problem.id}`"
          class="recent-item"
        >
          <h4>{{ problem.title }}</h4>
          <span class="status">{{ problem.status }}</span>
        </router-link>
      </div>
      <p v-else class="empty">{{ t('dashboard.noRecent') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
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

const fetchDashboardData = async () => {
  try {
    const [problemsRes, cardsRes, convsRes, practiceRes, statsRes, heatmapRes, reviewsRes] = await Promise.all([
      api.get('/problems/'),
      api.get('/model-cards/'),
      api.get('/conversations/'),
      api.get('/practice/tasks'),
      api.get('/statistics/overview'),
      api.get('/statistics/heatmap'),
      api.get('/reviews/').catch(() => ({ data: [] })),
    ])

    stats.value.problems = problemsRes.data.length
    stats.value.modelCards = cardsRes.data.length
    stats.value.conversations = convsRes.data.length
    stats.value.practice = practiceRes.data.length
    stats.value.dueReviews = statsRes.data.due_reviews || 0
    recentProblems.value = problemsRes.data.slice(0, 5)
    heatmapDays.value = buildHeatmap(heatmapRes.data.activity || {})
    existingReviews.value = reviewsRes.data
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
.dashboard h1 {
  margin-bottom: 2rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
}

.stat-card h3 {
  color: var(--text-muted);
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
}

.stat-number {
  font-size: 2rem;
  font-weight: bold;
  color: var(--primary);
}

.actions-section {
  margin-bottom: 2rem;
}

.actions-section h2 {
  margin-bottom: 1rem;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.action-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  text-decoration: none;
  color: var(--text);
  transition: all 0.2s;
}

.action-card:hover {
  border-color: var(--primary);
  transform: translateY(-2px);
}

.action-card h3 {
  color: var(--primary);
  margin-bottom: 0.5rem;
}

.action-card p {
  color: var(--text-muted);
  font-size: 0.875rem;
}

.card-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.assistant-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
}

.assistant-header p {
  margin-top: 0.35rem;
  color: var(--text-muted);
}

.assistant-actions {
  display: flex;
  align-items: center;
}

.assistant-message {
  margin-top: 0.75rem;
  color: var(--primary);
  font-size: 0.875rem;
}

.recent-section h2 {
  margin-bottom: 1rem;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.recent-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  text-decoration: none;
  color: var(--text);
}

.recent-item:hover {
  border-color: var(--primary);
}

.status {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  background: var(--primary);
  color: var(--bg-dark);
  border-radius: 4px;
}

.empty {
  color: var(--text-muted);
  text-align: center;
  padding: 2rem;
}

.stat-card-alert {
  border-color: #f97316;
}

.stat-number.due {
  color: #f97316;
}

.review-link {
  display: inline-block;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--primary);
  text-decoration: none;
}

.heatmap-section {
  margin-bottom: 2rem;
}

.heatmap-section h2 {
  margin-bottom: 1rem;
}

.heatmap-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.heatmap-cell {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.level-0 { background: var(--bg-card); border: 1px solid var(--border); }
.level-1 { background: #0e4429; }
.level-2 { background: #006d32; }
.level-3 { background: #26a641; }
.level-4 { background: #39d353; }
</style>
