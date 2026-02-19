<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1>{{ t('auth.register') }}</h1>
      <form @submit.prevent="handleRegister">
        <div class="form-group">
          <label>{{ t('users.email') }}</label>
          <input v-model="email" type="email" required />
        </div>
        <div class="form-group">
          <label>{{ t('auth.username') }}</label>
          <input v-model="username" type="text" required />
        </div>
        <div class="form-group">
          <label>{{ t('users.fullName') }} ({{ t('common.optional') }})</label>
          <input v-model="fullName" type="text" />
        </div>
        <div class="form-group">
          <label>{{ t('auth.password') }}</label>
          <input v-model="password" type="password" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" class="btn btn-primary" :disabled="loading">
          {{ loading ? t('auth.registering') : t('auth.register') }}
        </button>
      </form>
      <p class="auth-switch">
        {{ t('auth.hasAccount') }} <router-link to="/login">{{ t('auth.login') }}</router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const username = ref('')
const fullName = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const handleRegister = async () => {
  error.value = ''
  loading.value = true
  
  try {
    await authStore.register(email.value, username.value, password.value, fullName.value || undefined)
    router.push('/login')
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('auth.registerFailed')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
}

.auth-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 2rem;
  width: 100%;
  max-width: 400px;
}

.auth-card h1 {
  margin-bottom: 1.5rem;
  text-align: center;
}

.auth-card .btn {
  width: 100%;
  margin-top: 1rem;
}

.auth-switch {
  margin-top: 1rem;
  text-align: center;
  color: var(--text-muted);
}
</style>
