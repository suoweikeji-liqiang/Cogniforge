<template>
  <div class="forgot-password">
    <h1>{{ t('auth.forgotPassword') }}</h1>
    <form @submit.prevent="sendResetLink">
      <input v-model="email" type="email" :placeholder="t('users.email')" required />
      <button type="submit">{{ t('auth.sendResetLink') }}</button>
    </form>
    <p>{{ message }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const email = ref('')
const message = ref('')

const sendResetLink = async () => {
  try {
    await api.post('/auth/forgot-password', { email: email.value })
    message.value = 'If email exists, reset link will be sent'
  } catch (e) {
    message.value = 'Error sending reset link'
  }
}
</script>

<style scoped>
.forgot-password {
  max-width: 400px;
  margin: 50px auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

form {
  display: flex;
  flex-direction: column;
  gap: 15px;
  width: 100%;
}
input {
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}
button {
  padding: 10px;
  background: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
</style>
