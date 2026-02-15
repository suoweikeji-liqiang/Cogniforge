<template>
  <div class="reviews-page">
    <div class="page-header">
      <h1>Review & Reflection</h1>
      <button class="btn btn-primary" @click="showCreateModal = true">
        New Review
      </button>
    </div>
    
    <div v-if="reviews.length" class="reviews-list">
      <div v-for="review in reviews" :key="review.id" class="review-card card">
        <div class="review-header">
          <h3>{{ review.review_type }}</h3>
          <span class="period">{{ review.period }}</span>
        </div>
        <div class="review-content">
          <p v-if="review.content?.summary"><strong>Summary:</strong> {{ review.content.summary }}</p>
          <p v-if="review.content?.insights"><strong>Insights:</strong> {{ review.content.insights }}</p>
          <p v-if="review.content?.next_steps"><strong>Next Steps:</strong> {{ review.content.next_steps }}</p>
        </div>
        <div class="review-date">
          {{ new Date(review.created_at).toLocaleDateString() }}
        </div>
      </div>
    </div>
    
    <p v-else class="empty">No reviews yet. Create your first review!</p>
    
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <h2>Create Review</h2>
        <form @submit.prevent="createReview">
          <div class="form-group">
            <label>Review Type</label>
            <select v-model="newReview.review_type" required>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div class="form-group">
            <label>Period</label>
            <input v-model="newReview.period" type="text" placeholder="e.g., Week 1, January 2024" required />
          </div>
          <div class="form-group">
            <label>Summary</label>
            <textarea v-model="newReview.summary" rows="2"></textarea>
          </div>
          <div class="form-group">
            <label>Key Insights</label>
            <textarea v-model="newReview.insights" rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>Next Steps</label>
            <textarea v-model="newReview.next_steps" rows="2"></textarea>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="showCreateModal = false">
              Cancel
            </button>
            <button type="submit" class="btn btn-primary" :disabled="creating">
              {{ creating ? 'Creating...' : 'Create' }}
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

const reviews = ref<any[]>([])
const showCreateModal = ref(false)
const creating = ref(false)
const error = ref('')

const newReview = ref({
  review_type: 'daily',
  period: '',
  summary: '',
  insights: '',
  next_steps: '',
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
      },
    })
    
    showCreateModal.value = false
    newReview.value = { review_type: 'daily', period: '', summary: '', insights: '', next_steps: '' }
    await fetchReviews()
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to create review'
  } finally {
    creating.value = false
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
