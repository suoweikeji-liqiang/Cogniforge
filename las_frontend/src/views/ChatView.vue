<template>
  <div class="chat-page">
    <div class="chat-sidebar">
      <h3>{{ t('chat.conversations') }}</h3>
      <button class="btn btn-primary new-chat" @click="newChat">
        {{ t('chat.newConversation') }}
      </button>
      <div class="conversations-list">
        <div 
          v-for="conv in conversations" 
          :key="conv.id"
          class="conversation-item"
          :class="{ active: conv.id === currentConversationId }"
          @click="loadConversation(conv.id)"
        >
          {{ conv.title || t('chat.newConversation') }}
        </div>
      </div>
    </div>
    
    <div class="chat-main">
      <div class="chat-messages" ref="messagesContainer">
        <div 
          v-for="(msg, index) in messages" 
          :key="index"
          class="message"
          :class="msg.role"
        >
          <div class="message-content">{{ msg.content }}</div>
        </div>
        
        <div v-if="loading" class="message assistant">
          <div class="message-content">{{ t('common.loading') }}</div>
        </div>
      </div>
      
      <div class="chat-input">
        <div class="input-options">
          <label>
            <input type="checkbox" v-model="options.generateContradiction" />
            {{ t('modelCards.counterExamples') }}
          </label>
          <label>
            <input type="checkbox" v-model="options.suggestMigration" />
            {{ t('chat.newConversation') }}
          </label>
        </div>
        <form @submit.prevent="sendMessage">
          <input 
            v-model="userInput" 
            type="text" 
            :placeholder="t('chat.typeMessage')"
            :disabled="loading"
          />
          <button type="submit" class="btn btn-primary" :disabled="loading || !userInput.trim()">
            {{ t('chat.send') }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const route = useRoute()

const conversations = ref<any[]>([])
const currentConversationId = ref<string | null>(null)
const messages = ref<any[]>([])
const userInput = ref('')
const loading = ref(false)
const messagesContainer = ref<HTMLElement>()

const options = ref({
  generateContradiction: false,
  suggestMigration: false,
})

const fetchConversations = async () => {
  try {
    const response = await api.get('/conversations/')
    conversations.value = response.data
    
    if (route.params.id) {
      const conversationId = route.params.id as string
      currentConversationId.value = conversationId
      await loadConversation(conversationId)
    } else if (conversations.value.length > 0) {
      await loadConversation(conversations.value[0].id)
    }
  } catch (e) {
    console.error('Failed to fetch conversations:', e)
  }
}

const loadConversation = async (id: string) => {
  currentConversationId.value = id
  try {
    const response = await api.get(`/conversations/${id}`)
    messages.value = response.data.messages || []
    scrollToBottom()
  } catch (e) {
    console.error('Failed to load conversation:', e)
  }
}

const newChat = async () => {
  try {
    const response = await api.post('/conversations/', {
      title: 'New Chat',
    })
    conversations.value.unshift(response.data)
    currentConversationId.value = response.data.id
    messages.value = []
  } catch (e) {
    console.error('Failed to create conversation:', e)
  }
}

const sendMessage = async () => {
  if (!userInput.value.trim() || loading.value) return
  
  const userMessage = userInput.value.trim()
  userInput.value = ''
  
  messages.value.push({ role: 'user', content: userMessage })
  loading.value = true
  scrollToBottom()
  
  try {
    const response = await api.post('/conversations/chat', {
      conversation_id: currentConversationId.value,
      message: userMessage,
      generate_contradiction: options.value.generateContradiction,
      suggest_migration: options.value.suggestMigration,
    })
    
    messages.value.push({ role: 'assistant', content: response.data.message })
    
    if (response.data.metadata?.counter_examples?.length) {
      messages.value.push({
        role: 'assistant',
        content: '💡 Counter Examples: ' + response.data.metadata.counter_examples.join(', '),
      })
    }
    
    if (response.data.metadata?.migrations?.length) {
      messages.value.push({
        role: 'assistant',
        content: '🔀 Migration Suggestions: ' + JSON.stringify(response.data.metadata.migrations),
      })
    }
    
    currentConversationId.value = response.data.conversation_id
  } catch (e) {
    messages.value.push({ 
      role: 'assistant', 
      content: 'Sorry, I encountered an error. Please try again.' 
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

onMounted(() => {
  fetchConversations()
})
</script>

<style scoped>
.chat-page {
  display: grid;
  grid-template-columns: 250px 1fr;
  height: calc(100vh - 120px);
  gap: 1rem;
}

.chat-sidebar {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
}

.chat-sidebar h3 {
  margin-bottom: 1rem;
}

.new-chat {
  margin-bottom: 1rem;
}

.conversations-list {
  flex-grow: 1;
  overflow-y: auto;
}

.conversation-item {
  padding: 0.75rem;
  cursor: pointer;
  border-radius: 6px;
  margin-bottom: 0.25rem;
  color: var(--text-muted);
}

.conversation-item:hover {
  background: var(--bg-dark);
}

.conversation-item.active {
  background: var(--primary);
  color: var(--bg-dark);
}

.chat-main {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex-grow: 1;
  padding: 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message {
  max-width: 80%;
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.message-content {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  white-space: pre-wrap;
}

.message.user .message-content {
  background: var(--primary);
  color: var(--bg-dark);
}

.message.assistant .message-content {
  background: var(--bg-dark);
}

.chat-input {
  padding: 1rem;
  border-top: 1px solid var(--border);
}

.input-options {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.input-options label {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.input-options input {
  width: auto;
}

.chat-input form {
  display: flex;
  gap: 0.5rem;
}

.chat-input input {
  flex-grow: 1;
}
</style>
