<template>
  <div id="app">
    <div class="global-lang-switch">
      <LangSwitch />
    </div>
    <nav v-if="authStore.isAuthenticated" class="navbar">
      <div class="nav-top">
        <router-link to="/dashboard" class="nav-brand">
          <span class="brand-mark">C</span>
          <div class="brand-copy">
            <span class="brand-name">Cogniforge</span>
            <span class="brand-subtitle">{{ t('nav.workspace') }}</span>
          </div>
        </router-link>

        <div class="nav-meta">
          <div class="nav-user">
            <span class="nav-user-label">{{ t('nav.signedInAs') }}</span>
            <strong>{{ authStore.user?.username }}</strong>
          </div>
          <button class="logout-button" @click="logout">{{ t('nav.logout') }}</button>
        </div>
      </div>

      <div class="nav-row nav-row-primary" data-testid="primary-nav">
        <router-link
          v-for="item in primaryNavItems"
          :key="item.to"
          :to="item.to"
          class="nav-pill"
          :class="{ active: isRouteActive(item.to) }"
          :data-testid="`primary-nav-item-${item.key}`"
        >
          {{ t(item.label) }}
        </router-link>

        <button class="nav-toggle" data-testid="secondary-nav-toggle" @click="secondaryExpanded = !secondaryExpanded">
          {{ secondaryExpanded ? t('nav.less') : t('nav.more') }}
        </button>
      </div>

      <div v-if="secondaryExpanded" class="nav-row nav-row-secondary" data-testid="secondary-nav">
        <div
          v-for="section in secondaryNavSections"
          :key="section.key"
          class="secondary-group"
          :data-testid="`secondary-nav-section-${section.key}`"
        >
          <span class="secondary-group-label">{{ t(section.label) }}</span>
          <div class="secondary-group-links">
            <router-link
              v-for="item in section.items"
              :key="item.to"
              :to="item.to"
              class="nav-secondary-link"
              :class="{ active: isRouteActive(item.to) }"
              :data-testid="`secondary-nav-item-${item.key}`"
            >
              {{ t(item.label) }}
            </router-link>
          </div>
        </div>
      </div>
    </nav>

    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LangSwitch from '@/components/LangSwitch.vue'

const { t } = useI18n()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const secondaryExpanded = ref(false)

const primaryNavItems = [
  { key: 'home', to: '/dashboard', label: 'nav.home' },
  { key: 'problems', to: '/problems', label: 'nav.problems' },
  { key: 'model-cards', to: '/model-cards', label: 'nav.modelCards' },
  { key: 'review', to: '/reviews', label: 'nav.reviews' },
]

const secondaryNavSections = computed(() => {
  const sections = [
    {
      key: 'tools',
      label: 'nav.tools',
      items: [
        { key: 'srs-review', to: '/srs-review', label: 'nav.srsReview' },
        { key: 'practice', to: '/practice', label: 'nav.practice' },
        { key: 'chat', to: '/chat', label: 'nav.chat' },
        { key: 'resources', to: '/resources', label: 'nav.resources' },
        { key: 'notes', to: '/notes', label: 'nav.notes' },
      ],
    },
    {
      key: 'experiments',
      label: 'nav.experiments',
      items: [
        { key: 'graph', to: '/knowledge-graph', label: 'nav.graph' },
        { key: 'challenges', to: '/challenges', label: 'nav.challenges' },
        { key: 'cog-test', to: '/cog-test', label: 'nav.cogTest' },
      ],
    },
  ]

  if (authStore.user?.role === 'admin') {
    sections.push({
      key: 'admin',
      label: 'nav.admin',
      items: [{ key: 'admin', to: '/admin', label: 'nav.admin' }],
    })
  }

  return sections
})

const secondaryNavItems = computed(() =>
  secondaryNavSections.value.flatMap((section) => section.items)
)

const isRouteActive = (path: string) =>
  route.path === path || route.path.startsWith(`${path}/`)

watch(
  () => route.path,
  (path) => {
    if (secondaryNavItems.value.some((item) => path === item.to || path.startsWith(`${item.to}/`))) {
      secondaryExpanded.value = true
    }
  },
  { immediate: true }
)

const logout = async () => {
  await authStore.logout()
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
  margin: 0 auto;
  max-width: 1280px;
  padding: 1.25rem 2rem 0;
}

.nav-top,
.nav-row {
  display: flex;
  align-items: center;
}

.nav-top {
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.1rem;
  border: 1px solid rgba(74, 222, 128, 0.16);
  border-radius: 20px 20px 0 0;
  background:
    radial-gradient(circle at top left, rgba(74, 222, 128, 0.12), transparent 40%),
    linear-gradient(180deg, rgba(26, 26, 46, 0.94), rgba(16, 16, 34, 0.98));
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  color: var(--text);
  text-decoration: none;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--primary), #8bffbe);
  color: #07210f;
  font-size: 1.15rem;
  font-weight: 800;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.brand-name {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.brand-subtitle {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.nav-meta {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.nav-user {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.1rem;
  font-size: 0.9rem;
}

.nav-user-label {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.logout-button {
  border: 1px solid rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.14);
  color: #ffd3d3;
  padding: 0.65rem 0.95rem;
  border-radius: 999px;
  cursor: pointer;
}

.nav-row {
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.95rem 1.1rem;
  border-left: 1px solid rgba(74, 222, 128, 0.12);
  border-right: 1px solid rgba(74, 222, 128, 0.12);
  background: rgba(19, 19, 37, 0.96);
}

.nav-row-primary {
  border-top: 1px solid rgba(74, 222, 128, 0.12);
}

.nav-row-secondary {
  display: grid;
  gap: 0.85rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(74, 222, 128, 0.12);
  border-radius: 0 0 20px 20px;
}

.nav-pill,
.nav-secondary-link,
.nav-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  border-radius: 999px;
  text-decoration: none;
  transition: all 0.2s ease;
}

.nav-pill {
  padding: 0.65rem 1rem;
  color: #d3d8df;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid transparent;
}

.nav-pill.active {
  color: #04160a;
  background: linear-gradient(135deg, var(--primary), #7cf0a9);
  box-shadow: 0 10px 24px rgba(74, 222, 128, 0.2);
}

.nav-secondary-link {
  padding: 0.4rem 0.8rem;
  color: var(--text-muted);
}

.nav-secondary-link.active {
  color: var(--primary);
  background: rgba(74, 222, 128, 0.08);
}

.secondary-group {
  display: grid;
  gap: 0.45rem;
}

.secondary-group-label {
  color: var(--text-muted);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.secondary-group-links {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.nav-toggle {
  margin-left: auto;
  padding: 0.65rem 0.95rem;
  border: 1px dashed rgba(255, 255, 255, 0.16);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.main-content {
  padding: 2rem;
  max-width: 1280px;
  margin: 0 auto;
}

@media (max-width: 900px) {
  .navbar {
    padding: 0.9rem 1rem 0;
  }

  .nav-top {
    align-items: flex-start;
    flex-direction: column;
  }

  .nav-meta {
    width: 100%;
    justify-content: space-between;
  }

  .nav-user {
    align-items: flex-start;
  }

  .nav-toggle {
    margin-left: 0;
  }

  .main-content {
    padding: 1rem;
  }
}
</style>
