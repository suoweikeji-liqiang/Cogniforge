<template>
  <section class="card derived-paths-card" data-testid="path-candidates-panel">
    <h2>{{ t('problemDetail.pathCandidatesTitle') }}</h2>
    <p class="section-subtitle">{{ t('problemDetail.pathCandidatesSubtitle') }}</p>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <p v-else-if="!candidates.length" class="empty">{{ t('problemDetail.noPathCandidates') }}</p>
    <div v-else class="candidate-list">
      <article
        v-for="candidate in sortedCandidates"
        :key="candidate.id"
        class="candidate-item"
        :class="`candidate-${candidate.status}`"
        data-testid="path-candidate-card"
      >
        <div class="candidate-head">
          <strong>{{ candidate.title }}</strong>
          <span class="candidate-status">{{ formatPathCandidateStatus(candidate.status) }}</span>
          <span class="candidate-source">{{ formatLearningMode(candidate.learning_mode) }}</span>
          <span class="candidate-source">{{ formatPathSuggestionType(candidate.type) }}</span>
        </div>
        <p v-if="candidate.reason" class="candidate-evidence">{{ candidate.reason }}</p>
        <p class="candidate-meta">
          <strong>{{ t('problemDetail.pathCandidateRecommendedInsertion') }}:</strong>
          {{ formatInsertionBehavior(candidate.recommended_insertion) }}
        </p>
        <p v-if="candidate.selected_insertion" class="candidate-meta">
          <strong>{{ t('problemDetail.pathCandidateChosenInsertion') }}:</strong>
          {{ formatInsertionBehavior(candidate.selected_insertion) }}
        </p>

        <div v-if="candidate.status !== 'dismissed'" class="candidate-actions">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="submittingId === candidate.id"
            data-testid="path-candidate-insert-main"
            @click="emit('decide', { candidateId: candidate.id, action: 'insert_before_current_main' })"
          >
            {{ t('problemDetail.pathCandidateInsertBeforeCurrent') }}
          </button>
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="submittingId === candidate.id"
            data-testid="path-candidate-save-branch"
            @click="emit('decide', { candidateId: candidate.id, action: 'save_as_side_branch' })"
          >
            {{ t('problemDetail.pathCandidateSaveAsBranch') }}
          </button>
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="submittingId === candidate.id"
            data-testid="path-candidate-bookmark"
            @click="emit('decide', { candidateId: candidate.id, action: 'bookmark_for_later' })"
          >
            {{ t('problemDetail.pathCandidateBookmark') }}
          </button>
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="submittingId === candidate.id"
            data-testid="path-candidate-dismiss"
            @click="emit('decide', { candidateId: candidate.id, action: 'dismiss' })"
          >
            {{ t('problemDetail.pathCandidateDismiss') }}
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  candidates: any[]
  loading?: boolean
  submittingId?: string | null
}>()

const emit = defineEmits<{
  decide: [payload: { candidateId: string; action: string }]
}>()

const { t } = useI18n()

const statusRank = (status: string | undefined | null) => {
  if (status === 'pending') return 0
  if (status === 'planned') return 1
  if (status === 'bookmarked') return 2
  if (status === 'dismissed') return 3
  return 4
}

const sortedCandidates = computed(() => {
  return [...(props.candidates || [])].sort((left, right) => {
    const leftStatus = statusRank(left.status)
    const rightStatus = statusRank(right.status)
    if (leftStatus !== rightStatus) return leftStatus - rightStatus
    return String(right.created_at || '').localeCompare(String(left.created_at || ''))
  })
})

const formatLearningMode = (mode: string | undefined | null) => {
  return mode === 'exploration'
    ? t('problemDetail.modeExploration')
    : t('problemDetail.modeSocratic')
}

const formatPathSuggestionType = (pathType: string | undefined | null) => {
  if (pathType === 'prerequisite') return t('problemDetail.pathSuggestionPrerequisite')
  if (pathType === 'comparison_path') return t('problemDetail.pathSuggestionComparisonPath')
  return t('problemDetail.pathSuggestionBranchDeepDive')
}

const formatPathCandidateStatus = (status: string | undefined | null) => {
  if (status === 'planned') return t('problemDetail.pathCandidateStatusPlanned')
  if (status === 'bookmarked') return t('problemDetail.pathCandidateStatusBookmarked')
  if (status === 'dismissed') return t('problemDetail.pathCandidateStatusDismissed')
  return t('problemDetail.pathCandidateStatusPending')
}

const formatInsertionBehavior = (action: string | undefined | null) => {
  if (action === 'insert_before_current_main') return t('problemDetail.insertionInsertBeforeCurrentMain')
  if (action === 'save_as_side_branch') return t('problemDetail.insertionSaveAsSideBranch')
  return t('problemDetail.insertionBookmarkForLater')
}
</script>

<style scoped>
.derived-paths-card {
  height: fit-content;
}

.section-subtitle,
.candidate-meta,
.candidate-source,
.candidate-evidence {
  color: var(--text-muted);
}

.candidate-list {
  display: grid;
  gap: 0.75rem;
}

.candidate-item {
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-dark);
}

.candidate-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.candidate-status {
  font-size: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
}

.candidate-evidence,
.candidate-meta {
  margin-top: 0.45rem;
  font-size: 0.85rem;
}

.candidate-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
  flex-wrap: wrap;
}

.candidate-pending {
  border-color: rgba(250, 204, 21, 0.35);
}

.candidate-planned {
  border-color: rgba(34, 197, 94, 0.35);
}

.candidate-bookmarked {
  border-color: rgba(96, 165, 250, 0.35);
}

.candidate-dismissed {
  border-color: rgba(148, 163, 184, 0.28);
  opacity: 0.82;
}
</style>
