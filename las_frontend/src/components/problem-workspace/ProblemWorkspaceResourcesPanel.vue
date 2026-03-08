<template>
  <section class="card resources-card" data-testid="workspace-resources-panel">
    <h2>{{ t('resources.workspaceTitle') }}</h2>
    <p class="section-subtitle">{{ t('resources.workspaceSubtitle') }}</p>

    <form class="resource-form" @submit.prevent="submitResource">
      <input
        v-model="draftUrl"
        type="url"
        class="input"
        :placeholder="t('resources.urlPlaceholder')"
        data-testid="workspace-resource-url"
      />
      <input
        v-model="draftTitle"
        type="text"
        class="input"
        :placeholder="t('resources.titlePlaceholder')"
      />
      <div class="resource-actions">
        <select v-model="draftType" class="input type-select">
          <option value="webpage">{{ t('resources.webpage') }}</option>
          <option value="video">{{ t('resources.video') }}</option>
        </select>
        <button
          type="submit"
          class="btn btn-secondary"
          :disabled="saving || !draftUrl.trim()"
          data-testid="save-workspace-resource"
        >
          {{ saving ? t('common.loading') : t('resources.saveToProblem') }}
        </button>
      </div>
      <p class="scope-line">
        <strong>{{ t('resources.contextLabel') }}:</strong>
        {{ currentTurnId ? t('resources.currentTurnContext') : t('resources.problemOnlyContext') }}
      </p>
    </form>

    <div v-if="resources.length" class="resource-list">
      <article
        v-for="resource in resources"
        :key="resource.id"
        class="resource-item"
        :class="{ 'resource-current-turn': currentTurnId && resource.source_turn_id === currentTurnId }"
      >
        <div class="resource-head">
          <span class="type-badge" :class="resource.link_type">{{ resource.link_type }}</span>
          <span v-if="currentTurnId && resource.source_turn_id === currentTurnId" class="turn-badge">
            {{ t('resources.currentTurnResource') }}
          </span>
          <span class="resource-date">{{ formatDate(resource.created_at) }}</span>
        </div>
        <h3>
          <a href="#" @click.prevent="open(resource.url)">{{ resource.title || resource.url }}</a>
        </h3>
        <p v-if="resource.ai_summary" class="resource-summary">{{ resource.ai_summary }}</p>
        <div class="resource-row">
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="interpretingId === resource.id"
            @click="emit('interpret', resource.id)"
          >
            {{ interpretingId === resource.id ? t('common.loading') : t('resources.interpret') }}
          </button>
          <button
            type="button"
            class="btn btn-secondary"
            @click="emit('delete', resource.id)"
          >
            {{ t('common.delete') }}
          </button>
        </div>
      </article>
    </div>
    <p v-else class="empty">{{ t('resources.noProblemResources') }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

defineProps<{
  resources: any[]
  saving?: boolean
  interpretingId?: string | null
  currentTurnId?: string | null
}>()

const emit = defineEmits<{
  save: [payload: { url: string; title: string; linkType: string }]
  delete: [resourceId: string]
  interpret: [resourceId: string]
}>()

const { t } = useI18n()
const draftUrl = ref('')
const draftTitle = ref('')
const draftType = ref('webpage')

const submitResource = () => {
  const url = draftUrl.value.trim()
  if (!url) return
  emit('save', {
    url,
    title: draftTitle.value.trim(),
    linkType: draftType.value,
  })
  draftUrl.value = ''
  draftTitle.value = ''
  draftType.value = 'webpage'
}

const open = (url: string) => {
  window.open(url, '_blank', 'noopener')
}

const formatDate = (value: string) => new Date(value).toLocaleString()
</script>

<style scoped>
.section-subtitle,
.scope-line,
.resource-date {
  color: var(--text-muted);
}

.resource-form {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}

.resource-actions,
.resource-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.type-select {
  min-width: 0;
  flex: 1 1 160px;
}

.resource-list {
  display: grid;
  gap: 0.75rem;
}

.resource-item {
  padding: 0.8rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-dark);
}

.resource-current-turn {
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.25);
}

.resource-head {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 0.4rem;
}

.type-badge,
.turn-badge {
  font-size: 0.72rem;
  padding: 0.14rem 0.45rem;
  border-radius: 999px;
}

.type-badge {
  background: rgba(74, 222, 128, 0.16);
  color: #bbf7d0;
}

.type-badge.video {
  background: rgba(249, 115, 22, 0.16);
  color: #fdba74;
}

.turn-badge {
  background: rgba(96, 165, 250, 0.16);
  color: #bfdbfe;
}

.resource-item h3 a {
  color: var(--primary);
  text-decoration: none;
  word-break: break-all;
}

.resource-summary {
  margin: 0.6rem 0;
  color: var(--text-muted);
  white-space: pre-wrap;
}
</style>
