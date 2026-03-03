<template>
  <div class="srs-review">
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

    <!-- Review Card -->
    <div v-if="currentCard" class="review-card">
      <h2>{{ currentCard.title }}</h2>
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

const { t } = useI18n()

const dueCards = ref<any[]>([])
const allSchedules = ref<any[]>([])
const loading = ref(true)
const showAnswer = ref(false)
const currentIndex = ref(0)

const currentCard = computed(() => dueCards.value[currentIndex.value] || null)

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
    await api.post(`/srs/review/${card.schedule_id}?quality=${quality}`)
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
