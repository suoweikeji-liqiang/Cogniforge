<template>
  <section class="secondary-surface-banner" :data-testid="testId">
    <div class="copy">
      <p class="eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
      <p class="message">{{ message }}</p>
    </div>

    <div class="actions">
      <router-link
        :to="primaryTo"
        class="btn btn-secondary banner-link"
        :data-testid="testId ? `${testId}-primary-action` : undefined"
      >
        {{ primaryLabel }}
      </router-link>
      <router-link
        v-if="secondaryTo && secondaryLabel"
        :to="secondaryTo"
        class="btn btn-secondary banner-link banner-link-muted"
        :data-testid="testId ? `${testId}-secondary-action` : undefined"
      >
        {{ secondaryLabel }}
      </router-link>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow: string
  title: string
  message: string
  primaryLabel: string
  primaryTo: string
  secondaryLabel?: string
  secondaryTo?: string
  testId?: string
}>()
</script>

<style scoped>
.secondary-surface-banner {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1.5rem;
  padding: 1rem 1.1rem;
  border-radius: 16px;
  border: 1px solid rgba(245, 158, 11, 0.25);
  background:
    radial-gradient(circle at top left, rgba(245, 158, 11, 0.12), transparent 40%),
    linear-gradient(180deg, rgba(26, 26, 46, 0.94), rgba(16, 16, 34, 0.98));
}

.copy,
.actions {
  min-width: 0;
}

.copy h2 {
  margin-top: 0.25rem;
  margin-bottom: 0.35rem;
}

.eyebrow {
  color: #fbbf24;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.message {
  max-width: 58ch;
  color: var(--text-muted);
}

.actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-self: start;
}

.banner-link {
  text-decoration: none;
  justify-content: center;
}

.banner-link-muted {
  opacity: 0.82;
}

@media (max-width: 900px) {
  .secondary-surface-banner {
    grid-template-columns: 1fr;
  }

  .actions {
    width: 100%;
    justify-content: stretch;
  }

  .banner-link {
    width: 100%;
  }
}
</style>
