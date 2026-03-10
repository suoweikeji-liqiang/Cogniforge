<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1>{{ t('auth.login') }}</h1>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label>{{ t('auth.username') }}</label>
          <input v-model="username" type="text" autocomplete="username" required />
        </div>
        <div class="form-group">
          <label>{{ t('auth.password') }}</label>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </div>
        <div class="remember-options">
          <label class="remember-option">
            <input v-model="rememberUsername" type="checkbox" :disabled="rememberPassword" />
            <span>{{ t('auth.rememberUsername') }}</span>
          </label>
          <label class="remember-option">
            <input v-model="rememberPassword" type="checkbox" @change="onRememberPasswordChange" />
            <span>{{ t('auth.rememberPassword') }}</span>
          </label>
          <p class="remember-hint">{{ t('auth.rememberPasswordHint') }}</p>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" class="btn btn-primary" :disabled="loading">
          {{ loading ? t('auth.loggingIn') : t('auth.login') }}
        </button>
      </form>
      <p class="auth-switch">
        {{ t('auth.noAccount') }} <router-link to="/register">{{ t('auth.register') }}</router-link>
      </p>
      <p class="auth-switch">
        <router-link to="/forgot-password">{{ t('auth.forgotPassword') }}</router-link>
      </p>
      <p v-if="isNative" class="auth-switch">
        <router-link to="/server-config">{{ t('settings.serverConfig') }}</router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const REMEMBER_USERNAME_FLAG_KEY = 'login_remember_username'
const REMEMBER_PASSWORD_FLAG_KEY = 'login_remember_password'
const SAVED_USERNAME_KEY = 'login_saved_username'
const SAVED_PASSWORD_KEY = 'login_saved_password'

const { t } = useI18n()
const isNative = !!localStorage.getItem('api_server_url')
const router = useRouter()
const authStore = useAuthStore()

const rememberUsername = ref(localStorage.getItem(REMEMBER_USERNAME_FLAG_KEY) === '1')
const rememberPassword = ref(localStorage.getItem(REMEMBER_PASSWORD_FLAG_KEY) === '1')
const username = ref(rememberUsername.value ? (localStorage.getItem(SAVED_USERNAME_KEY) || '') : '')
const password = ref(rememberPassword.value ? (localStorage.getItem(SAVED_PASSWORD_KEY) || '') : '')
const error = ref('')
const loading = ref(false)

const persistLoginPreference = () => {
  if (rememberPassword.value) {
    localStorage.setItem(REMEMBER_USERNAME_FLAG_KEY, '1')
    localStorage.setItem(REMEMBER_PASSWORD_FLAG_KEY, '1')
    localStorage.setItem(SAVED_USERNAME_KEY, username.value)
    localStorage.setItem(SAVED_PASSWORD_KEY, password.value)
    return
  }

  localStorage.removeItem(REMEMBER_PASSWORD_FLAG_KEY)
  localStorage.removeItem(SAVED_PASSWORD_KEY)

  if (rememberUsername.value) {
    localStorage.setItem(REMEMBER_USERNAME_FLAG_KEY, '1')
    localStorage.setItem(SAVED_USERNAME_KEY, username.value)
  } else {
    localStorage.removeItem(REMEMBER_USERNAME_FLAG_KEY)
    localStorage.removeItem(SAVED_USERNAME_KEY)
  }
}

const onRememberPasswordChange = () => {
  if (rememberPassword.value) {
    rememberUsername.value = true
    return
  }
  localStorage.removeItem(REMEMBER_PASSWORD_FLAG_KEY)
  localStorage.removeItem(SAVED_PASSWORD_KEY)
}

const handleLogin = async () => {
  error.value = ''
  loading.value = true
  
  try {
    await authStore.login(username.value, password.value)
    persistLoginPreference()
    router.push('/dashboard')
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('auth.loginFailed')
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

.remember-options {
  margin-top: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.remember-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.remember-option input {
  flex: 0 0 auto;
  margin: 0;
}

.remember-hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.75rem;
}
</style>
