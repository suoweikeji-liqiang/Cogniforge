<template>
  <div id="app">
    <div class="global-lang-switch">
      <LangSwitch />
    </div>
    <nav v-if="authStore.isAuthenticated" class="navbar">
      <div class="nav-brand">LAS</div>
      <div class="nav-links">
        <router-link to="/dashboard">{{ t('nav.dashboard') }}</router-link>
        <router-link to="/problems">{{ t('nav.problems') }}</router-link>
        <router-link to="/model-cards">{{ t('nav.modelCards') }}</router-link>
        <router-link to="/practice">{{ t('nav.practice') }}</router-link>
        <router-link to="/reviews">{{ t('nav.reviews') }}</router-link>
        <router-link v-if="authStore.user?.role === 'admin'" to="/admin">{{ t('nav.admin') }}</router-link>
        <button @click="logout">{{ t('nav.logout') }}</button>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LangSwitch from '@/components/LangSwitch.vue'

const { t } = useI18n()
const authStore = useAuthStore()
const router = useRouter()

const logout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
#app {
  position: relative;
  min-height: 100vh;
}

.global-lang-switch {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 1000;
}

.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: #1a1a2e;
  color: white;
}

.nav-brand {
  font-size: 1.5rem;
  font-weight: bold;
}

.nav-links {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}

.nav-links a {
  color: #a0a0a0;
  text-decoration: none;
}

.nav-links a.router-link-active {
  color: #4ade80;
}

.nav-links button {
  background: #ef4444;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.main-content {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}
</style>
