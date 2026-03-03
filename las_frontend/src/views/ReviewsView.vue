<template>
  <div class="reviews-page">
    <div class="page-header">
      <h1>{{ t('reviews.title') }}</h1>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="showCreateModal = true">
          {{ t('reviews.newReview') }}
        </button>
      </div>
    </div>
    
    <div v-if="reviews.length" class="reviews-list">
      <div v-for="review in reviews" :key="review.id" class="review-card card">
        <div class="review-header">
          <h3>{{ review.review_type }}</h3>
          <span class="period">{{ review.period }}</span>
        </div>
        <div class="review-content">
          <p v-if="review.content?.summary"><strong>{{ t('reviews.content') }}:</strong> {{ review.content.summary }}</p>
          <p v-if="review.content?.insights"><strong>{{ t('reviews.insights') }}:</strong> {{ review.content.insights }}</p>
          <p v-if="review.content?.next_steps"><strong>{{ t('reviews.nextSteps') }}:</strong> {{ review.content.next_steps }}</p>
          <p v-if="review.content?.misconceptions?.length"><strong>{{ t('reviews.misconceptions') }}:</strong> {{ review.content.misconceptions.join(' / ') }}</p>
        </div>
        <div class="review-actions-row">
          <button class="btn btn-secondary" @click="exportReview(review)">
            {{ t('common.download') }}
          </button>
        </div>
        <div class="review-date">
          {{ new Date(review.created_at).toLocaleDateString() }}
        </div>
      </div>
    </div>
    
    <p v-else class="empty">{{ t('reviews.noReviews') }}</p>
    
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
import { ref, onMounted } from 'vue'
import api from '@/api'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const reviews = ref<any[]>([])
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

const fetchReviews = async () => {
  try {
    const response = await api.get('/reviews/')
    reviews.value = response.data
  } catch (e) {
    console.error('Failed to fetch reviews:', e)
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
    newReview.value = {
      review_type: 'daily',
      period: '',
      summary: '',
      insights: '',
      next_steps: '',
      misconceptions: '',
    }
    await fetchReviews()
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to create review'
  } finally {
    creating.value = false
  }
}

const exportReview = async (review: any) => {
  try {
    const response = await api.get(`/reviews/${review.id}/export`, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(
      new Blob([response.data], { type: 'text/markdown' })
    )
    const a = document.createElement('a')
    a.href = url
    a.download = `${review.review_type}-review-${review.period.replace(/\s+/g, '-')}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('Failed to export review:', e)
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
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to generate review'
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  fetchReviews()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
}

.reviews-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.review-card {
  display: flex;
  flex-direction: column;
}

.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.review-header h3 {
  text-transform: capitalize;
}

.period {
  font-size: 0.875rem;
  color: var(--text-muted);
}

.review-content p {
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
}

.review-content strong {
  color: var(--primary);
}

.review-actions-row {
  margin-top: 1rem;
}

.review-date {
  margin-top: 1rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  text-align: right;
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

.empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
