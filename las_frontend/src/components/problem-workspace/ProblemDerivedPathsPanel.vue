<template>
  <section :class="embedded ? 'derived-paths-embedded' : 'card derived-paths-card'" data-testid="path-candidates-panel">
    <template v-if="!embedded">
      <h2>{{ t('problemDetail.pathCandidatesTitle') }}</h2>
      <p class="section-subtitle">{{ t('problemDetail.pathCandidatesSubtitle') }}</p>
    </template>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <p v-else-if="!candidates.length" class="empty">{{ t('problemDetail.noPathCandidates') }}</p>
    <div v-else class="candidate-groups">
      <template v-for="group in candidateGroups" :key="group.key">
        <details
          v-if="collapseOlder && group.key === 'older'"
          class="candidate-group candidate-group-collapsed"
          data-testid="path-candidates-older"
        >
          <summary class="group-title candidate-group-summary">{{ group.title }} ({{ group.items.length }})</summary>
          <div class="candidate-list">
            <article
              v-for="candidate in group.items"
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
                  {{ t('problemDetail.pathCandidateFollowNow') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="submittingId === candidate.id"
                  data-testid="path-candidate-save-branch"
                  @click="emit('decide', { candidateId: candidate.id, action: 'save_as_side_branch' })"
                >
                  {{ t('problemDetail.pathCandidateExploreSeparately') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="submittingId === candidate.id"
                  data-testid="path-candidate-bookmark"
                  @click="emit('decide', { candidateId: candidate.id, action: 'bookmark_for_later' })"
                >
                  {{ t('problemDetail.pathCandidateLater') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="submittingId === candidate.id"
                  data-testid="path-candidate-dismiss"
                  @click="emit('decide', { candidateId: candidate.id, action: 'dismiss' })"
                >
                  {{ t('problemDetail.pathCandidateIgnoreNow') }}
                </button>
              </div>
            </article>
          </div>
        </details>
        <section v-else class="candidate-group">
          <h3 v-if="group.title" class="group-title">{{ group.title }}</h3>
          <div class="candidate-list">
            <article
              v-for="candidate in group.items"
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
                  {{ t('problemDetail.pathCandidateFollowNow') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="submittingId === candidate.id"
                  data-testid="path-candidate-save-branch"
                  @click="emit('decide', { candidateId: candidate.id, action: 'save_as_side_branch' })"
                >
                  {{ t('problemDetail.pathCandidateExploreSeparately') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="submittingId === candidate.id"
                  data-testid="path-candidate-bookmark"
                  @click="emit('decide', { candidateId: candidate.id, action: 'bookmark_for_later' })"
                >
                  {{ t('problemDetail.pathCandidateLater') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="submittingId === candidate.id"
                  data-testid="path-candidate-dismiss"
                  @click="emit('decide', { candidateId: candidate.id, action: 'dismiss' })"
                >
                  {{ t('problemDetail.pathCandidateIgnoreNow') }}
                </button>
              </div>
            </article>
          </div>
        </section>
      </template>
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
  currentTurnId?: string | null
  embedded?: boolean
  collapseOlder?: boolean
  olderOnly?: boolean
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

const isCurrentTurnCandidate = (candidate: any) => (
  Boolean(props.currentTurnId)
  && String(candidate.source_turn_id || '') === String(props.currentTurnId)
)

const candidateGroups = computed(() => {
  if (!props.currentTurnId) {
    if (props.olderOnly) {
      return [{ key: 'older', title: t('problemDetail.earlierPathCandidates'), items: sortedCandidates.value }]
    }
    return [{ key: 'all', title: '', items: sortedCandidates.value }]
  }

  const current = sortedCandidates.value.filter((candidate) => isCurrentTurnCandidate(candidate))
  const older = sortedCandidates.value.filter((candidate) => !isCurrentTurnCandidate(candidate))
  const groups = []
  if (current.length) {
    groups.push({ key: 'current', title: t('problemDetail.currentTurnPaths'), items: current })
  }
  if (older.length) {
    groups.push({ key: 'older', title: t('problemDetail.earlierPathCandidates'), items: older })
  }
  return groups
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

.derived-paths-embedded {
  display: grid;
  gap: 0.75rem;
}

.section-subtitle,
.candidate-meta,
.candidate-source,
.candidate-evidence {
  color: var(--text-muted);
}

.candidate-groups {
  display: grid;
  gap: 0.9rem;
}

.candidate-group {
  display: grid;
  gap: 0.5rem;
}

.candidate-group-collapsed {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding-top: 0.75rem;
}

.group-title {
  font-size: 0.92rem;
  color: var(--text-muted);
}

.candidate-group-summary {
  cursor: pointer;
  list-style: none;
}

.candidate-group-summary::-webkit-details-marker {
  display: none;
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
