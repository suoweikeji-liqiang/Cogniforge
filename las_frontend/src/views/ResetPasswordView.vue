<template>
  <div class="reset-password">
    <h1>{{ t('auth.resetPassword') }}</h1>
    <form @submit.prevent="resetPassword">
      <input v-model="password" type="password" :placeholder="t('users.newPassword')" required />
      <button type="submit">{{ t('common.save') }}</button>
    </form>
    <p>{{ message }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const password = ref('')
const message = ref('')

const resetPassword = async () => {
  try {
    await api.post('/auth/reset-password', {
      token: route.query.token,
      new_password: password.value
    })
    message.value = t('auth.passwordResetSuccess')
    setTimeout(() => router.push('/login'), 2000)
  } catch (e) {
    message.value = 'Error resetting password'
  }
}
</script>

<style scoped>
.reset-password {
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
