<template>
  <div class="challenges-page">
    <SecondarySurfaceBanner
      test-id="challenges-secondary-banner"
      :eyebrow="t('challenges.secondaryTitle')"
      :title="t('challenges.secondaryHeading')"
      :message="t('challenges.secondaryMessage')"
      :primary-label="t('challenges.openReviewHub')"
      primary-to="/reviews"
      :secondary-label="t('nav.problems')"
      secondary-to="/problems"
    />
    <div class="page-header">
      <h1>{{ t('challenges.title') }}</h1>
      <button class="btn btn-secondary" @click="generateChallenge" :disabled="generating">
        {{ generating ? t('common.loading') : t('challenges.generate') }}
      </button>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="challenges.length" class="challenges-list">
      <div
        v-for="c in challenges"
        :key="c.id"
        class="challenge-card"
        :class="'status-' + c.status"
      >
        <div class="challenge-header">
          <span class="type-badge">{{ c.challenge_type }}</span>
          <span class="card-ref">{{ c.card_title }}</span>
          <span class="challenge-date">{{ formatDate(c.created_at) }}</span>
        </div>

        <p class="challenge-question">{{ c.question }}</p>

        <div v-if="c.status === 'pending'" class="answer-section">
          <textarea
            v-model="c._answer"
            :placeholder="t('challenges.yourAnswer')"
            rows="3"
          ></textarea>
          <button
            class="btn btn-secondary"
            @click="submitAnswer(c)"
            :disabled="!c._answer"
          >{{ t('common.submit') }}</button>
        </div>

        <div v-if="c.ai_feedback" class="feedback-section">
          <h4>{{ t('challenges.feedback') }}</h4>
          <p v-if="c.structured_feedback?.correctness"><strong>{{ t('feedback.correctness') }}:</strong> {{ c.structured_feedback.correctness }}</p>
          <p v-if="c.structured_feedback?.misconceptions?.length"><strong>{{ t('feedback.misconceptions') }}:</strong> {{ c.structured_feedback.misconceptions.join(' / ') }}</p>
          <p v-if="c.structured_feedback?.suggestions?.length"><strong>{{ t('feedback.suggestions') }}:</strong> {{ c.structured_feedback.suggestions.join(' / ') }}</p>
          <p v-if="c.structured_feedback?.next_question"><strong>{{ t('feedback.nextQuestion') }}:</strong> {{ c.structured_feedback.next_question }}</p>
        </div>
      </div>
    </div>

    <p v-else class="empty">{{ t('challenges.noChallenges') }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'
import SecondarySurfaceBanner from '@/components/SecondarySurfaceBanner.vue'

const { t } = useI18n()

const challenges = ref<any[]>([])
const loading = ref(true)
const generating = ref(false)

const formatDate = (d: string) => new Date(d).toLocaleDateString()

const fetchChallenges = async () => {
  try {
    const res = await api.get('/challenges/')
    challenges.value = res.data.map((c: any) => ({ ...c, _answer: '' }))
  } catch (e) {
    console.error('Failed to fetch challenges:', e)
  } finally {
    loading.value = false
  }
}

const generateChallenge = async () => {
  generating.value = true
  try {
    await api.post('/challenges/generate')
    await fetchChallenges()
  } catch (e) {
    console.error('Failed to generate challenge:', e)
  } finally {
    generating.value = false
  }
}

const submitAnswer = async (c: any) => {
  try {
    const res = await api.post(
      `/challenges/${c.id}/answer?answer=${encodeURIComponent(c._answer)}`
    )
    c.ai_feedback = res.data.ai_feedback
    c.structured_feedback = res.data.structured_feedback
    c.status = 'answered'
  } catch (e) {
    console.error('Failed to submit answer:', e)
  }
}

onMounted(fetchChallenges)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.challenges-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.challenge-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
}

.challenge-card.status-answered {
  border-color: #22c55e;
}

.challenge-header {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.type-badge {
  background: var(--primary);
  color: var(--bg-dark);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
}

.card-ref {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.challenge-date {
  margin-left: auto;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.challenge-question {
  margin-bottom: 1rem;
  line-height: 1.6;
}

.answer-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.answer-section textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-dark);
  color: var(--text);
  font-family: inherit;
  resize: vertical;
}

.feedback-section {
  margin-top: 1rem;
  padding: 1rem;
  background: var(--bg-dark);
  border-radius: 8px;
  border-left: 3px solid #22c55e;
}

.feedback-section h4 {
  color: #22c55e;
  margin-bottom: 0.5rem;
}

.feedback-section p {
  color: var(--text-muted);
  line-height: 1.6;
}

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
