<template>
  <div class="server-config">
    <h1>{{ t('settings.serverConfig') }}</h1>
    <div class="card">
      <div class="form-group">
        <label>{{ t('settings.serverUrl') }}</label>
        <input v-model="serverUrl" placeholder="http://192.168.1.100:8002/api" />
      </div>
      <button class="btn btn-primary" @click="save">{{ t('settings.save') }}</button>
      <p v-if="saved" class="success">{{ t('settings.saved') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const serverUrl = ref(localStorage.getItem('api_server_url') || 'http://10.0.2.2:8002/api')
const saved = ref(false)

const save = () => {
  localStorage.setItem('api_server_url', serverUrl.value)
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}
</script>

<style scoped>
.server-config { max-width: 500px; margin: 0 auto; padding: 2rem 1rem; }
.server-config h1 { margin-bottom: 1.5rem; }
.success { color: var(--primary); margin-top: 1rem; }
</style>
