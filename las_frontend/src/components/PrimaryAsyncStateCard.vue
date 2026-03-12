<template>
  <section
    class="primary-async-state card"
    :class="`state-${kind}`"
    :data-testid="testId || null"
  >
    <div class="state-copy">
      <span class="state-eyebrow">
        {{ kind === 'error' ? t('common.error') : t('common.empty') }}
      </span>
      <h2>{{ title }}</h2>
      <p>{{ message }}</p>
    </div>

    <div v-if="retryLabel || $slots.actions" class="state-actions">
      <button
        v-if="retryLabel"
        type="button"
        class="btn btn-primary"
        :data-testid="retryTestId"
        @click="emit('retry')"
      >
        {{ retryLabel }}
      </button>
      <slot name="actions" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  kind?: 'error' | 'empty'
  title: string
  message: string
  retryLabel?: string
  testId?: string
  retryTestId?: string
}>()

const emit = defineEmits<{
  retry: []
}>()

const { t } = useI18n()

const kind = computed(() => props.kind || 'error')
const retryTestId = computed(() => (
  props.retryTestId
    || (props.testId ? props.testId.replace(/-state$/, '-retry') : null)
))
</script>

<style scoped>
.primary-async-state {
  display: grid;
  gap: 1rem;
  padding: 1.5rem;
  border-radius: 18px;
  background: rgba(18, 18, 34, 0.96);
}

.primary-async-state.state-error {
  border-color: rgba(248, 113, 113, 0.28);
}

.primary-async-state.state-empty {
  border-color: rgba(74, 222, 128, 0.2);
}

.state-copy {
  display: grid;
  gap: 0.35rem;
}

.state-eyebrow {
  color: var(--primary);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.state-copy p {
  color: var(--text-muted);
}

.state-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}
</style>
