<template>
  <div class="resources">
    <div class="header">
      <h1>{{ t('resources.title') }}</h1>
      <button @click="showAdd = true" class="btn-primary">{{ t('common.add') }}</button>
    </div>

    <input
      v-model="searchQuery"
      :placeholder="t('resources.searchResources')"
      class="input search-input"
    />

    <!-- Add Form -->
    <div v-if="showAdd" class="add-form card">
      <input v-model="newUrl" type="url" :placeholder="t('resources.urlPlaceholder')" class="input" />
      <input v-model="newTitle" :placeholder="t('resources.titlePlaceholder')" class="input" />
      <select v-model="newType" class="input">
        <option value="webpage">{{ t('resources.webpage') }}</option>
        <option value="video">{{ t('resources.video') }}</option>
      </select>
      <div class="form-actions">
        <button @click="addResource" class="btn-primary" :disabled="!newUrl">{{ t('common.save') }}</button>
        <button @click="showAdd = false" class="btn-secondary">{{ t('common.cancel') }}</button>
      </div>
    </div>

    <!-- Filter -->
    <div class="filter-bar">
      <button v-for="s in ['all','unread','reading','completed']" :key="s"
        :class="['filter-btn', { active: filter === s }]" @click="filter = s">
        {{ t('resources.' + s) }}
      </button>
    </div>

    <!-- List -->
    <div v-if="filtered.length" class="resource-list">
      <div v-for="r in filtered" :key="r.id" class="resource-card card">
        <div class="resource-header">
          <span class="type-badge" :class="r.link_type">{{ r.link_type }}</span>
          <select :value="r.status" @change="updateStatus(r, ($event.target as HTMLSelectElement).value)" class="status-select">
            <option value="unread">{{ t('resources.unread') }}</option>
            <option value="reading">{{ t('resources.reading') }}</option>
            <option value="completed">{{ t('resources.completed') }}</option>
          </select>
        </div>
        <h3><a href="#" @click.prevent="openLink(r.url)">{{ r.title || r.url }}</a></h3>
        <div v-if="r.ai_summary" class="ai-summary">
          <strong>{{ t('resources.aiSummary') }}</strong>
          <p>{{ r.ai_summary }}</p>
        </div>
        <div class="resource-actions">
          <button @click="interpret(r)" class="btn-small" :disabled="interpreting === r.id">
            {{ interpreting === r.id ? t('common.loading') : t('resources.interpret') }}
          </button>
          <button @click="remove(r.id)" class="btn-small btn-danger">{{ t('common.delete') }}</button>
        </div>
      </div>
    </div>
    <p v-else class="empty">{{ t('resources.noResources') }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()

const resources = ref<any[]>([])
const showAdd = ref(false)
const newUrl = ref('')
const newTitle = ref('')
const newType = ref('webpage')
const filter = ref('all')
const interpreting = ref<string | null>(null)
const searchQuery = ref('')

const openLink = async (url: string) => {
  window.open(url, '_blank', 'noopener')
}

const filtered = computed(() =>
  filter.value === 'all' ? resources.value : resources.value.filter(r => r.status === filter.value)
)

const fetchResources = async () => {
  const { data } = await api.get('/resources/', {
    params: {
      q: searchQuery.value.trim() || undefined,
    },
  })
  resources.value = data
}

const addResource = async () => {
  await api.post('/resources/', { url: newUrl.value, title: newTitle.value || null, link_type: newType.value })
  newUrl.value = ''
  newTitle.value = ''
  newType.value = 'webpage'
  showAdd.value = false
  await fetchResources()
}

const updateStatus = async (r: any, status: string) => {
  await api.put(`/resources/${r.id}`, { status })
  r.status = status
}

const interpret = async (r: any) => {
  interpreting.value = r.id
  try {
    const { data } = await api.post(`/resources/${r.id}/interpret`)
    r.ai_summary = data.ai_summary
  } finally {
    interpreting.value = null
  }
}

const remove = async (id: string) => {
  await api.delete(`/resources/${id}`)
  resources.value = resources.value.filter(r => r.id !== id)
}

onMounted(fetchResources)

watch(searchQuery, () => {
  fetchResources()
})
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.search-input { margin-bottom: 1rem; }
.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; }
.add-form { margin-bottom: 1.5rem; display: flex; flex-direction: column; gap: 0.75rem; }
.input { background: var(--bg-dark); border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem; color: var(--text); width: 100%; box-sizing: border-box; }
.form-actions { display: flex; gap: 0.5rem; }
.filter-bar { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
.filter-btn { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 0.5rem 1rem; color: var(--text-muted); cursor: pointer; }
.filter-btn.active { border-color: var(--primary); color: var(--primary); }
.resource-list { display: flex; flex-direction: column; gap: 1rem; }
.resource-card { }
.resource-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.type-badge { font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px; background: var(--primary); color: var(--bg-dark); }
.type-badge.video { background: #f97316; }
.status-select { background: var(--bg-dark); border: 1px solid var(--border); border-radius: 4px; color: var(--text); padding: 0.25rem; }
.resource-card h3 { margin-bottom: 0.5rem; }
.resource-card a { color: var(--primary); text-decoration: none; }
.resource-card a:hover { text-decoration: underline; }
.ai-summary { background: var(--bg-dark); border-radius: 8px; padding: 1rem; margin: 0.75rem 0; }
.ai-summary strong { color: var(--primary); display: block; margin-bottom: 0.5rem; font-size: 0.85rem; }
.ai-summary p { color: var(--text-muted); font-size: 0.9rem; line-height: 1.5; white-space: pre-wrap; }
.resource-actions { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
.btn-small { font-size: 0.8rem; padding: 0.35rem 0.75rem; }
.btn-danger { color: #ef4444; border-color: #ef4444; }
.empty { color: var(--text-muted); text-align: center; padding: 2rem; }
@media (max-width: 768px) {
  .header { flex-direction: column; gap: 0.75rem; align-items: stretch; }
  .filter-bar { flex-wrap: wrap; }
  .filter-btn { flex: 1; min-width: 0; text-align: center; font-size: 0.8rem; padding: 0.5rem 0.5rem; }
  .resource-card h3 { font-size: 0.95rem; word-break: break-all; }
  .form-actions { flex-direction: column; }
  .resource-actions { flex-wrap: wrap; }
}
</style>
