<template>
  <div class="email-config">
    <h1>{{ t('admin.emailConfig') }}</h1>
    <form @submit.prevent="saveConfig">
      <div class="form-group">
        <label>{{ t('email.smtpHost') }}</label>
        <input v-model="config.smtp_host" type="text" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.smtpPort') }}</label>
        <input v-model.number="config.smtp_port" type="number" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.smtpUser') }}</label>
        <input v-model="config.smtp_user" type="text" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.smtpPassword') }}</label>
        <input v-model="config.smtp_password" type="password" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.fromEmail') }}</label>
        <input v-model="config.from_email" type="email" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.fromName') }}</label>
        <input v-model="config.from_name" type="text" />
      </div>
      <div class="form-group">
        <label>
          <input v-model="config.use_tls" type="checkbox" />
          {{ t('email.useTLS') }}
        </label>
      </div>
      <button type="submit">{{ t('common.save') }}</button>
      <button type="button" @click="testEmail">{{ t('email.testEmail') }}</button>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const config = ref({
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  from_email: '',
  from_name: 'Learning Assistant',
  use_tls: true
})

const loadConfig = async () => {
  try {
    const response = await api.get('/admin/email-config')
    config.value = { ...config.value, ...response.data }
  } catch (e) {
    console.error(e)
  }
}

const saveConfig = async () => {
  await api.put('/admin/email-config', config.value)
  alert(t('email.saveSuccess'))
}

const testEmail = async () => {
  const email = prompt('Enter email to test:')
  if (email) {
    try {
      await api.post('/admin/email-config/test', { to_email: email })
      alert(t('email.testSuccess'))
    } catch (e) {
      alert(e.response?.data?.detail || 'Error')
    }
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.email-config h1 {
  color: var(--text);
  margin-bottom: 1.5rem;
}
.form-group {
  margin-bottom: 15px;
}
.form-group label {
  display: block;
  margin-bottom: 8px;
  color: var(--text-muted);
  font-size: 0.875rem;
}
.form-group label:has(input[type="checkbox"]) {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
}
.form-group input[type="text"],
.form-group input[type="email"],
.form-group input[type="password"],
.form-group input[type="number"] {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--text);
  font-size: 1rem;
}
.form-group input:focus {
  outline: none;
  border-color: var(--primary);
}
.form-group input[type="checkbox"] {
  width: auto;
  accent-color: var(--primary);
}
.email-config button[type="submit"],
.email-config button[type="button"] {
  background: var(--primary);
  color: var(--bg-dark);
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  margin-right: 12px;
}
.email-config button[type="button"] {
  background: var(--bg-card);
  color: var(--text-muted);
  border: 1px solid var(--border);
}
</style>
