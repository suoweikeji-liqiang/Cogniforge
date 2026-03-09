<template>
  <section class="card notes-card" data-testid="workspace-notes-panel">
    <h2>{{ t('notes.workspaceTitle') }}</h2>
    <p class="section-subtitle">{{ t('notes.workspaceSubtitle') }}</p>

    <form class="notes-form" @submit.prevent="submitNote">
      <textarea
        v-model="draft"
        rows="3"
        class="input"
        :placeholder="t('notes.placeholder')"
        data-testid="workspace-note-input"
      ></textarea>
      <div class="notes-actions">
        <input
          v-model="tagInput"
          type="text"
          class="input tag-input"
          :placeholder="t('notes.tagPlaceholder')"
          @keydown.enter.prevent="addTag"
        />
        <button
          type="submit"
          class="btn btn-secondary"
          :disabled="saving || !draft.trim()"
          data-testid="save-workspace-note"
        >
          {{ saving ? t('common.loading') : t('notes.saveToProblem') }}
        </button>
      </div>
      <div v-if="tags.length" class="tag-row">
        <span
          v-for="tag in tags"
          :key="tag"
          class="note-tag"
          @click="removeTag(tag)"
        >
          {{ tag }} ×
        </span>
      </div>
      <p class="scope-line">
        <strong>{{ t('notes.contextLabel') }}:</strong>
        {{ currentTurnId ? t('notes.currentTurnContext') : t('notes.problemOnlyContext') }}
      </p>
    </form>

    <div v-if="notes.length" class="notes-list">
      <article
        v-for="note in notes"
        :key="note.id"
        class="note-item"
        :class="{ 'note-current-turn': currentTurnId && note.source_turn_id === currentTurnId }"
      >
        <div class="note-head">
          <span class="source-badge">{{ note.source }}</span>
          <span v-if="currentTurnId && note.source_turn_id === currentTurnId" class="turn-badge">
            {{ t('notes.currentTurnNote') }}
          </span>
          <span class="note-date">{{ formatDate(note.created_at) }}</span>
          <button
            type="button"
            class="btn-delete"
            @click="emit('delete', note.id)"
          >
            {{ t('common.delete') }}
          </button>
        </div>
        <p class="note-content">{{ note.content }}</p>
        <div v-if="note.tags?.length" class="tag-row">
          <span v-for="tag in note.tags" :key="`${note.id}-${tag}`" class="note-tag static-tag">{{ tag }}</span>
        </div>
      </article>
    </div>
    <p v-else class="empty">{{ t('notes.noProblemNotes') }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

defineProps<{
  notes: any[]
  saving?: boolean
  currentTurnId?: string | null
}>()

const emit = defineEmits<{
  save: [payload: { content: string; tags: string[] }]
  delete: [noteId: string]
}>()

const { t } = useI18n()
const draft = ref('')
const tagInput = ref('')
const tags = ref<string[]>([])

const addTag = () => {
  const value = tagInput.value.trim()
  if (value && !tags.value.includes(value)) {
    tags.value.push(value)
  }
  tagInput.value = ''
}

const removeTag = (tag: string) => {
  tags.value = tags.value.filter((item) => item !== tag)
}

const submitNote = () => {
  const content = draft.value.trim()
  if (!content) return
  emit('save', { content, tags: [...tags.value] })
  draft.value = ''
  tagInput.value = ''
  tags.value = []
}

const formatDate = (value: string) => new Date(value).toLocaleString()
</script>

<style scoped>
.section-subtitle,
.scope-line,
.note-date {
  color: var(--text-muted);
}

.notes-form {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}

.notes-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tag-input {
  min-width: 0;
  flex: 1 1 180px;
}

.tag-row {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.note-tag {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  background: rgba(74, 222, 128, 0.14);
  border: 1px solid rgba(74, 222, 128, 0.22);
  color: #bbf7d0;
  cursor: pointer;
}

.static-tag {
  cursor: default;
}

.notes-list {
  display: grid;
  gap: 0.75rem;
}

.note-item {
  padding: 0.8rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-dark);
}

.note-current-turn {
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.25);
}

.note-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.45rem;
}

.source-badge,
.turn-badge {
  font-size: 0.72rem;
  border-radius: 999px;
  padding: 0.14rem 0.45rem;
}

.source-badge {
  background: rgba(255, 255, 255, 0.05);
}

.turn-badge {
  background: rgba(96, 165, 250, 0.16);
  color: #bfdbfe;
}

.btn-delete {
  margin-left: auto;
  border: none;
  background: transparent;
  color: #fca5a5;
  cursor: pointer;
}

.note-content {
  white-space: pre-wrap;
  line-height: 1.55;
}
</style>
