<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <h2>{{ t('admin.title') }}</h2>
      <nav>
        <router-link to="/admin">{{ t('admin.stats') }}</router-link>
        <router-link to="/admin/users">{{ t('admin.users') }}</router-link>
        <router-link to="/admin/llm-config">{{ t('admin.llmConfig') }}</router-link>
        <router-link to="/admin/email-config">{{ t('admin.emailConfig') }}</router-link>
      </nav>
    </aside>
    <main class="admin-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<style scoped>
.admin-layout {
  display: flex;
  min-height: 100vh;
}
.admin-sidebar {
  width: 250px;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  padding: 20px;
}
.admin-sidebar h2 {
  color: var(--text);
  margin-bottom: 1.5rem;
}
.admin-sidebar a {
  display: block;
  padding: 10px;
  margin: 5px 0;
  color: var(--text-muted);
  text-decoration: none;
  border-radius: 6px;
  transition: all 0.2s;
}
.admin-sidebar a:hover {
  background: var(--bg-dark);
  color: var(--text);
}
.admin-sidebar a.router-link-active {
  background: var(--primary);
  color: var(--bg-dark);
}
.admin-content {
  flex: 1;
  padding: 20px;
  background: var(--bg-dark);
}
</style>
