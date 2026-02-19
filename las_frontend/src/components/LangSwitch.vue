<template>
  <div class="lang-switch">
    <button 
      @click="switchLang('en')" 
      :class="{ active: locale === 'en' }"
    >EN</button>
    <button 
      @click="switchLang('zh')" 
      :class="{ active: locale === 'zh' }"
    >中文</button>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()

const switchLang = (lang: string) => {
  locale.value = lang
  localStorage.setItem('locale', lang)
}
</script>

<style scoped>
.lang-switch {
  display: flex;
  gap: 4px;
  background: rgba(255, 255, 255, 0.1);
  padding: 2px;
  border-radius: 4px;
}

.lang-switch button {
  padding: 4px 8px;
  font-size: 12px;
  border: none;
  background: transparent;
  color: #a0a0a0;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s;
}

.lang-switch button:hover {
  color: white;
}

.lang-switch button.active {
  background: #4ade80;
  color: #1a1a2e;
}
</style>
