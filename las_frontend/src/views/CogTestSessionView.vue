<template>
  <div class="cog-test-session">
    <div class="session-header">
      <button class="btn btn-secondary" @click="$router.push('/cog-test')">{{ t('common.back') }}</button>
      <h1>{{ store.concept }}</h1>
      <span class="round-badge">{{ t('cogTest.round') }} {{ store.currentRound }}/{{ store.maxRounds }}</span>
    </div>

    <div v-if="store.status === 'connecting' || store.error || store.status === 'completed' || store.status === 'stopped'" class="status-bar">
      <div v-if="store.status === 'connecting'" class="connecting">{{ t('cogTest.connecting') }}</div>
      <div v-if="store.error" class="error">{{ store.error }}</div>
      <div v-if="store.status === 'completed'" class="completed">{{ t('cogTest.sessionComplete') }}</div>
      <button
        v-if="store.status === 'completed' || store.status === 'stopped'"
        class="btn btn-secondary"
        @click="store.exportReport(store.sessionId!, store.concept)"
      >
        {{ t('cogTest.exportReport') }}
      </button>
    </div>

    <div class="messages-container" ref="messagesContainer">
      <div
        v-for="(msg, i) in store.messages"
        :key="i"
        class="message"
        :class="[msg.role, { streaming: msg.streaming }]"
      >
        <span class="role-label">{{ roleLabel(msg.role) }}</span>
        <div class="message-content">
          {{ msg.content }}<span v-if="msg.streaming" class="cursor">|</span>
        </div>
      </div>
    </div>

    <div class="input-area">
      <button
        v-if="store.status === 'streaming' || store.status === 'waiting'"
        class="btn btn-stop"
        @click="store.stopSession()"
      >
        {{ t('cogTest.stopAndDiagnose') }}
      </button>
      <form
        v-if="store.status !== 'completed' && store.status !== 'stopped'"
        class="input-form"
        @submit.prevent="submitTurn"
      >
        <input
          v-model="userInput"
          :disabled="store.status !== 'waiting'"
          :placeholder="t('cogTest.inputPlaceholder')"
        />
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="store.status !== 'waiting' || !userInput.trim()"
        >
          {{ t('cogTest.send') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useCogTestStore } from '@/stores/cogTest'
import type { Message } from '@/stores/cogTest'

const { t } = useI18n()
const router = useRouter()
const store = useCogTestStore()

const userInput = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const roleLabel = (role: Message['role']): string => {
  if (role === 'guide') return t('cogTest.guide')
  if (role === 'challenger') return t('cogTest.challenger')
  return t('cogTest.you')
}

const scrollToBottom = () => {
  nextTick(() => {
    messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' })
  })
}

watch(() => store.messages, scrollToBottom, { deep: true })

const submitTurn = async () => {
  if (!userInput.value.trim()) return
  await store.submitUserTurn(userInput.value.trim())
  userInput.value = ''
}

onMounted(() => {
  if (store.status === 'idle' && !store.sessionId) {
    router.push('/cog-test')
  }
})
</script>

<style scoped>
.cog-test-session {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
}

.session-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.session-header h1 {
  flex: 1;
  margin: 0;
}

.round-badge {
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.8rem;
}

.status-bar {
  margin-bottom: 0.5rem;
}

.status-bar .connecting {
  color: var(--text-muted);
  text-align: center;
  padding: 1rem;
}

.status-bar .error {
  color: var(--error);
  text-align: center;
  padding: 1rem;
}

.status-bar .completed {
  color: var(--primary);
  text-align: center;
  padding: 1rem;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-width: 80%;
}

.message.user {
  align-self: flex-end;
}

.message.guide,
.message.challenger {
  align-self: flex-start;
}

.role-label {
  font-size: 0.75rem;
  font-weight: 600;
}

.message.guide .role-label {
  color: var(--primary);
}

.message.challenger .role-label {
  color: #f59e0b;
}

.message.user .role-label {
  color: var(--text-muted);
}

.message-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message.guide .message-content {
  border-left: 3px solid var(--primary);
}

.message.challenger .message-content {
  border-left: 3px solid #f59e0b;
}

.message.user .message-content {
  background: var(--bg-dark);
  border-left: none;
}

.cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.input-area {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.input-form {
  display: flex;
  flex: 1;
  gap: 0.5rem;
}

.input-form input {
  flex: 1;
}

.btn-stop {
  background: var(--error);
  color: white;
  white-space: nowrap;
}
</style>
