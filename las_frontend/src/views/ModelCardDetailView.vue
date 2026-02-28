<template>
  <div class="model-card-detail">
    <div class="page-header">
      <button class="btn btn-secondary" @click="$router.back()">{{ t('common.back') }}</button>
      <h1>{{ card?.title }}</h1>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <template v-else-if="card">
      <div class="card-info">
        <div class="info-section">
          <h3>{{ t('modelCards.notes') }}</h3>
          <p>{{ card.user_notes || '-' }}</p>
        </div>

        <div class="info-row">
          <div class="info-section">
            <h3>{{ t('modelCards.examples') }}</h3>
            <ul v-if="card.examples?.length">
              <li v-for="(ex, i) in card.examples" :key="i">{{ ex }}</li>
            </ul>
            <p v-else>-</p>
          </div>
          <div class="info-section">
            <h3>{{ t('modelCards.counterExamples') }}</h3>
            <ul v-if="card.counter_examples?.length">
              <li v-for="(ex, i) in card.counter_examples" :key="i">{{ ex }}</li>
            </ul>
            <p v-else>-</p>
          </div>
        </div>

        <div class="card-meta">
          <span>{{ t('modelCards.version') }}: v{{ card.version }}</span>
          <span>{{ t('problems.createdAt') }}: {{ formatDate(card.created_at) }}</span>
        </div>
        <div class="cog-test-action">
          <button class="btn btn-primary" @click="startCogTest">
            {{ t('cogTest.startTest') }}
          </button>
        </div>
      </div>

      <!-- Evolution Timeline -->
      <div class="evolution-section">
        <h2>{{ t('evolution.title') }}</h2>
        <div v-if="evolutionLogs.length" class="timeline">
          <div
            v-for="log in evolutionLogs"
            :key="log.id"
            class="timeline-item"
          >
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <div class="timeline-header">
                <span class="action-badge">{{ log.action_taken }}</span>
                <span class="timeline-date">{{ formatDate(log.created_at) }}</span>
              </div>
              <p v-if="log.reason_for_change">{{ log.reason_for_change }}</p>
              <div v-if="log.snapshot" class="snapshot-preview">
                <span>v{{ log.snapshot.version }} - {{ log.snapshot.title }}</span>
              </div>
            </div>
          </div>
        </div>
        <p v-else class="empty">{{ t('evolution.noLogs') }}</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import api from '@/api'
import { useCogTestStore } from '@/stores/cogTest'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const cogTestStore = useCogTestStore()

const startCogTest = async () => {
  await cogTestStore.startSession(card.value.title, card.value.id)
  router.push('/cog-test/session')
}

const card = ref<any>(null)
const evolutionLogs = ref<any[]>([])
const loading = ref(true)

const formatDate = (d: string) => new Date(d).toLocaleDateString()

const fetchCard = async () => {
  try {
    const id = route.params.id
    const [cardRes, logsRes] = await Promise.all([
      api.get(`/model-cards/${id}`),
      api.get(`/model-cards/${id}/evolution`),
    ])
    card.value = cardRes.data
    evolutionLogs.value = logsRes.data
  } catch (e) {
    console.error('Failed to fetch model card:', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchCard)
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.card-info {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.info-section { margin-bottom: 1rem; }
.info-section h3 { color: var(--primary); margin-bottom: 0.5rem; }
.info-section ul { padding-left: 1.5rem; color: var(--text-muted); }

.info-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.card-meta {
  display: flex;
  gap: 2rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.evolution-section { margin-top: 2rem; }
.evolution-section h2 { margin-bottom: 1rem; }

.timeline {
  position: relative;
  padding-left: 2rem;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 8px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--border);
}

.timeline-item {
  position: relative;
  margin-bottom: 1.5rem;
}

.timeline-dot {
  position: absolute;
  left: -2rem;
  top: 4px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--primary);
  border: 2px solid var(--bg-dark);
}

.timeline-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.action-badge {
  background: var(--primary);
  color: var(--bg-dark);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.timeline-date { font-size: 0.75rem; color: var(--text-muted); }

.snapshot-preview {
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  font-style: italic;
}

.loading, .empty {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}

.cog-test-action {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}
</style>
