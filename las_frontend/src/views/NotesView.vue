<template>
  <div class="notes">
    <SecondarySurfaceBanner
      test-id="notes-secondary-banner"
      :eyebrow="t('notes.secondaryTitle')"
      :title="t('notes.secondaryHeading')"
      :message="t('notes.secondaryMessage')"
      :primary-label="t('notes.captureInProblem')"
      primary-to="/problems"
      :secondary-label="t('nav.reviews')"
      secondary-to="/reviews"
    />
    <div class="header">
      <div>
        <h1>{{ t('notes.title') }}</h1>
        <p class="subtitle">{{ t('notes.archiveSubtitle') }}</p>
      </div>
      <div class="header-actions">
        <router-link to="/problems" class="btn-secondary notes-link">
          {{ t('notes.captureInProblem') }}
        </router-link>
        <button @click="showAdd = !showAdd" class="btn-secondary" data-testid="notes-toggle-add">
          {{ showAdd ? t('common.close') : t('notes.addAnnotation') }}
        </button>
      </div>
    </div>

    <!-- Input Area -->
    <div v-if="showAdd" class="note-input card" data-testid="notes-add-form">
      <textarea v-model="newContent" :placeholder="t('notes.placeholder')" class="input" rows="3"></textarea>
      <div class="input-footer">
        <div class="tags-input">
          <input v-model="tagInput" @keydown.enter.prevent="addTag" :placeholder="t('notes.tagPlaceholder')" class="input tag-field" />
          <span v-for="tag in tags" :key="tag" class="tag" @click="tags = tags.filter(t => t !== tag)">{{ tag }} ×</span>
        </div>
        <div class="input-actions">
          <button @click="toggleVoice" :class="['btn-voice', { recording }]">
            {{ recording ? t('notes.stopRecording') : t('notes.startRecording') }}
          </button>
          <button @click="saveNote" class="btn-secondary" :disabled="!newContent.trim()">{{ t('common.save') }}</button>
        </div>
      </div>
    </div>

    <!-- Notes List -->
    <div v-if="notes.length" class="notes-list">
      <div v-for="note in notes" :key="note.id" class="note-card card">
        <div class="note-meta">
          <span class="source-badge">{{ note.source }}</span>
          <span class="context-badge">{{ note.problem_id ? t('notes.problemNote') : t('notes.generalNote') }}</span>
          <span class="note-date">{{ new Date(note.created_at).toLocaleString() }}</span>
          <button @click="remove(note.id)" class="btn-delete">{{ t('common.delete') }}</button>
        </div>
        <p class="note-content">{{ note.content }}</p>
        <div v-if="note.tags?.length" class="note-tags">
          <span v-for="tag in note.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </div>
    </div>
    <p v-else class="empty">{{ t('notes.noNotes') }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'
import SecondarySurfaceBanner from '@/components/SecondarySurfaceBanner.vue'

const { t } = useI18n()

const notes = ref<any[]>([])
const showAdd = ref(false)
const newContent = ref('')
const tags = ref<string[]>([])
const tagInput = ref('')
const recording = ref(false)
let recognition: any = null

const addTag = () => {
  const v = tagInput.value.trim()
  if (v && !tags.value.includes(v)) tags.value.push(v)
  tagInput.value = ''
}

const fetchNotes = async () => {
  const { data } = await api.get('/notes/')
  notes.value = data
}

const saveNote = async () => {
  if (!newContent.value.trim()) return
  await api.post('/notes/', {
    content: newContent.value,
    source: recording.value ? 'voice' : 'text',
    tags: tags.value,
  })
  newContent.value = ''
  tags.value = []
  showAdd.value = false
  await fetchNotes()
}

const remove = async (id: string) => {
  await api.delete(`/notes/${id}`)
  notes.value = notes.value.filter(n => n.id !== id)
}

const toggleVoice = async () => {
  if (recording.value) {
    recognition?.stop()
    recording.value = false
    return
  }

  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    alert(t('notes.voiceNotSupported')); return
  }
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  recognition = new SR()
  recognition.continuous = true
  recognition.interimResults = true
  recognition.lang = navigator.language
  recognition.onresult = (e: any) => {
    let transcript = ''
    for (let i = 0; i < e.results.length; i++) transcript += e.results[i][0].transcript
    newContent.value = transcript
  }
  recognition.onerror = () => { recording.value = false }
  recognition.onend = () => { recording.value = false }
  recognition.start()
  recording.value = true
}

onMounted(fetchNotes)
onUnmounted(() => {
  recognition?.stop()
})
</script>

<style scoped>
.header { margin-bottom: 1.5rem; display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; flex-wrap: wrap; }
.header-actions { display: flex; gap: 0.75rem; flex-wrap: wrap; }
.subtitle { color: var(--text-muted); margin-top: 0.35rem; max-width: 56ch; }
.notes-link { text-decoration: none; display: inline-flex; align-items: center; }
.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; }
.note-input { margin-bottom: 1.5rem; }
.input { background: var(--bg-dark); border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem; color: var(--text); width: 100%; box-sizing: border-box; resize: vertical; }
.input-footer { display: flex; justify-content: space-between; align-items: flex-start; margin-top: 0.75rem; gap: 1rem; flex-wrap: wrap; }
.tags-input { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; flex: 1; }
.tag-field { width: 120px; flex: none; }
.tag { font-size: 0.75rem; padding: 0.2rem 0.5rem; background: var(--primary); color: var(--bg-dark); border-radius: 4px; cursor: pointer; }
.input-actions { display: flex; gap: 0.5rem; }
.btn-voice { background: var(--bg-dark); border: 1px solid var(--border); color: var(--text); padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; }
.btn-voice.recording { border-color: #ef4444; color: #ef4444; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.notes-list { display: flex; flex-direction: column; gap: 1rem; }
.note-card { }
.note-meta { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }
.source-badge { font-size: 0.7rem; padding: 0.15rem 0.4rem; border-radius: 4px; background: var(--border); color: var(--text-muted); }
.context-badge { font-size: 0.7rem; padding: 0.15rem 0.45rem; border-radius: 999px; background: rgba(96, 165, 250, 0.12); color: #bfdbfe; }
.note-date { font-size: 0.8rem; color: var(--text-muted); }
.btn-delete { margin-left: auto; font-size: 0.75rem; color: #ef4444; background: none; border: none; cursor: pointer; }
.note-content { color: var(--text); line-height: 1.6; white-space: pre-wrap; }
.note-tags { display: flex; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap; }
.empty { color: var(--text-muted); text-align: center; padding: 2rem; }
@media (max-width: 768px) {
  .input-footer { flex-direction: column; }
  .tags-input { width: 100%; }
  .tag-field { width: 100%; flex: 1; }
  .input-actions { width: 100%; justify-content: stretch; }
  .input-actions button { flex: 1; }
  .note-meta { flex-wrap: wrap; }
}
</style>
