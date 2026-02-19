<template>
  <div class="admin-dashboard">
    <h1>{{ t('admin.stats') }}</h1>
    <div class="stats-grid">
      <div class="stat-card">
        <h3>{{ t('admin.statsUsers') }}</h3>
        <p class="stat-number">{{ stats.users }}</p>
      </div>
      <div class="stat-card">
        <h3>{{ t('admin.statsProblems') }}</h3>
        <p class="stat-number">{{ stats.problems }}</p>
      </div>
      <div class="stat-card">
        <h3>{{ t('admin.statsModels') }}</h3>
        <p class="stat-number">{{ stats.model_cards }}</p>
      </div>
      <div class="stat-card">
        <h3>{{ t('admin.statsConversations') }}</h3>
        <p class="stat-number">{{ stats.conversations }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const stats = ref({ users: 0, problems: 0, model_cards: 0, conversations: 0 })

onMounted(async () => {
  try {
    const response = await api.get('/admin/users/stats')
    stats.value = response.data
  } catch (e) {
    console.error(e)
  }
})
</script>

<style scoped>
.admin-dashboard h1 {
  color: var(--text);
  margin-bottom: 1rem;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 20px;
}
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 20px;
  border-radius: 12px;
}
.stat-card h3 {
  color: var(--text-muted);
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
}
.stat-number {
  font-size: 32px;
  font-weight: bold;
  color: var(--primary);
}
</style>
