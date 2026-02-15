<template>
  <div class="dashboard">
    <h1>Welcome, {{ authStore.user?.username }}</h1>
    
    <div class="stats-grid">
      <div class="stat-card">
        <h3>Problems</h3>
        <p class="stat-number">{{ stats.problems }}</p>
      </div>
      <div class="stat-card">
        <h3>Model Cards</h3>
        <p class="stat-number">{{ stats.modelCards }}</p>
      </div>
      <div class="stat-card">
        <h3>Conversations</h3>
        <p class="stat-number">{{ stats.conversations }}</p>
      </div>
      <div class="stat-card">
        <h3>Practice Tasks</h3>
        <p class="stat-number">{{ stats.practice }}</p>
      </div>
    </div>
    
    <div class="actions-section">
      <h2>Quick Actions</h2>
      <div class="actions-grid">
        <router-link to="/problems" class="action-card">
          <h3>New Problem</h3>
          <p>Start a new learning journey</p>
        </router-link>
        <router-link to="/model-cards" class="action-card">
          <h3>Model Library</h3>
          <p>Browse your knowledge models</p>
        </router-link>
        <router-link to="/chat" class="action-card">
          <h3>AI Chat</h3>
          <p>Interact with learning assistant</p>
        </router-link>
        <router-link to="/practice" class="action-card">
          <h3>Practice</h3>
          <p>Test your understanding</p>
        </router-link>
      </div>
    </div>
    
    <div class="recent-section">
      <h2>Recent Activity</h2>
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
      <p v-else class="empty">No recent problems. Start learning!</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'

const authStore = useAuthStore()

const stats = ref({
  problems: 0,
  modelCards: 0,
  conversations: 0,
  practice: 0,
})

const recentProblems = ref<any[]>([])

const fetchDashboardData = async () => {
  try {
    const [problemsRes, cardsRes, convsRes] = await Promise.all([
      api.get('/problems/'),
      api.get('/model-cards/'),
      api.get('/conversations/'),
    ])
    
    stats.value.problems = problemsRes.data.length
    stats.value.modelCards = cardsRes.data.length
    stats.value.conversations = convsRes.data.length
    recentProblems.value = problemsRes.data.slice(0, 5)
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
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
</style>
