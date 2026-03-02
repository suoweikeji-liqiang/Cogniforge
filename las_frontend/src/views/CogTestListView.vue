<template>
  <div class="cog-test-list">
    <div class="header-actions">
      <h1>{{ t('cogTest.history') }}</h1>
      <router-link to="/cog-test/session" class="btn btn-primary">
        {{ t('cogTest.startNew') || 'Start New Session' }}
      </router-link>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="store.sessions.length === 0" class="empty">{{ t('cogTest.noSessions') }}</div>

    <div v-else class="sessions-list">
      <div
        v-for="s in store.sessions"
        :key="s.id"
        class="card session-item"
      >
        <div class="session-info">
          <span class="concept">{{ s.concept }}</span>
          <span class="date">{{ formatDate(s.created_at) }}</span>
        </div>
        <span v-if="s.score != null" class="score">{{ s.score }}%</span>
        <span v-else class="status-badge" :class="s.status">{{ s.status }}</span>
        <button
          v-if="s.status === 'completed' || s.status === 'stopped'"
          class="btn btn-secondary btn-sm"
          @click.stop="store.exportReport(s.id, s.concept)"
        >
          {{ t('cogTest.exportReport') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCogTestStore } from '@/stores/cogTest'

const { t } = useI18n()
const store = useCogTestStore()
const loading = ref(true)

const formatDate = (d: string) => new Date(d).toLocaleDateString()

onMounted(async () => {
  try {
    await store.fetchSessions()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.cog-test-list h1 {
  margin-bottom: 0;
}

.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.concept {
  font-weight: 500;
  color: var(--text);
}

.date {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.status-badge {
  font-size: 0.75rem;
  padding: 0.2rem 0.6rem;
  border-radius: 10px;
  font-weight: 500;
}

.status-badge.active {
  background: rgba(74, 222, 128, 0.15);
  color: var(--primary);
}

.status-badge.completed {
  background: rgba(74, 222, 128, 0.15);
  color: var(--primary);
}

.status-badge.stopped {
  background: rgba(239, 68, 68, 0.15);
  color: var(--error);
}

.score {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--primary);
}

.loading,
.empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
