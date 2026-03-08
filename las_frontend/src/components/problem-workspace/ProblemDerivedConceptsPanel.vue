<template>
  <section class="card derived-concepts-card">
    <h2>{{ t('problemDetail.derivedConceptsTitle') }}</h2>
    <p class="section-subtitle">{{ t('problemDetail.derivedConceptsSubtitle') }}</p>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <p v-else-if="!sortedCandidates.length" class="empty">{{ t('problemDetail.noConceptCandidates') }}</p>
    <div v-else class="candidate-groups">
      <section
        v-for="group in candidateGroups"
        :key="group.key"
        class="candidate-group"
      >
        <h3 v-if="group.title" class="group-title">{{ group.title }}</h3>
        <div class="candidate-list">
          <article
            v-for="candidate in group.items"
            :key="candidate.id"
            class="candidate-item"
            :class="[`candidate-${candidate.status}`, { 'candidate-current': isCurrentTurnCandidate(candidate) }]"
          >
            <div class="candidate-head">
              <strong>{{ candidate.concept_text }}</strong>
              <span class="candidate-status">{{ formatCandidateStatus(candidate.status) }}</span>
              <span class="candidate-mode">{{ formatLearningMode(candidate.learning_mode) }}</span>
              <span class="candidate-confidence">{{ formatConfidence(candidate.confidence) }}</span>
            </div>

            <p class="candidate-meta">
              <strong>{{ t('problemDetail.derivedConceptSourceLabel') }}:</strong>
              {{ formatCandidateSource(candidate.source) }}
            </p>
            <p class="candidate-meta">
              <strong>{{ t('problemDetail.sourceTurnLabel') }}:</strong>
              {{ candidate.source_turn_preview || t('problemDetail.sourceTurnUnavailable') }}
            </p>
            <p v-if="candidate.evidence_snippet" class="candidate-evidence">
              <strong>{{ t('problemDetail.evidenceLabel') }}:</strong>
              {{ candidate.evidence_snippet }}
            </p>
            <p v-if="candidate.merged_into_concept" class="candidate-meta">
              <strong>{{ t('problemDetail.mergeIntoLabel') }}:</strong>
              {{ candidate.merged_into_concept }}
            </p>

            <div v-if="canModerate(candidate)" class="candidate-actions">
              <button
                type="button"
                class="btn btn-primary"
                :disabled="actionPendingId === candidate.id"
                @click="emit('accept', candidate.id)"
              >
                {{ t('problemDetail.acceptCandidate') }}
              </button>
              <button
                type="button"
                class="btn btn-secondary"
                :disabled="actionPendingId === candidate.id"
                @click="emit('reject', candidate.id)"
              >
                {{ t('problemDetail.rejectCandidate') }}
              </button>
              <button
                v-if="candidate.status !== 'postponed'"
                type="button"
                class="btn btn-secondary"
                :disabled="actionPendingId === candidate.id"
                @click="emit('postpone', candidate.id)"
              >
                {{ t('problemDetail.postponeCandidate') }}
              </button>
            </div>

            <div v-if="canMerge(candidate)" class="candidate-merge-row">
              <select
                v-model="selectedMergeTargets[candidate.id]"
                class="merge-select"
                :disabled="actionPendingId === candidate.id"
              >
                <option value="">{{ t('problemDetail.mergeTargetPlaceholder') }}</option>
                <option
                  v-for="target in mergeTargetsFor(candidate)"
                  :key="`${candidate.id}-${target}`"
                  :value="target"
                >
                  {{ target }}
                </option>
              </select>
              <button
                type="button"
                class="btn btn-secondary"
                :disabled="actionPendingId === candidate.id || !selectedMergeTargets[candidate.id]"
                @click="emitMerge(candidate.id)"
              >
                {{ t('problemDetail.mergeCandidate') }}
              </button>
            </div>

            <div v-if="candidate.status === 'accepted'" class="candidate-actions">
              <button
                type="button"
                class="btn btn-secondary"
                :disabled="actionPendingId === candidate.id"
                @click="emit('rollback', { candidateId: candidate.id, conceptText: candidate.concept_text })"
              >
                {{ t('problemDetail.rollbackConcept') }}
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  candidates: any[]
  loading?: boolean
  currentTurnId?: string | null
  mergeTargets?: string[]
  actionPendingId?: string | null
}>()

const emit = defineEmits<{
  accept: [candidateId: string]
  reject: [candidateId: string]
  postpone: [candidateId: string]
  merge: [payload: { candidateId: string; targetConcept: string }]
  rollback: [payload: { candidateId: string; conceptText: string }]
}>()

const { t } = useI18n()
const selectedMergeTargets = ref<Record<string, string>>({})

const normalizeKey = (value: string | undefined | null) => String(value || '').trim().toLowerCase()

const isCurrentTurnCandidate = (candidate: any) => Boolean(props.currentTurnId && candidate.source_turn_id === props.currentTurnId)

const statusRank = (status: string | undefined | null) => {
  if (status === 'pending') return 0
  if (status === 'postponed') return 1
  if (status === 'accepted') return 2
  if (status === 'merged') return 3
  if (status === 'reverted') return 4
  return 5
}

const sortedCandidates = computed(() => {
  return [...(props.candidates || [])].sort((left, right) => {
    const leftCurrent = isCurrentTurnCandidate(left) ? 0 : 1
    const rightCurrent = isCurrentTurnCandidate(right) ? 0 : 1
    if (leftCurrent !== rightCurrent) return leftCurrent - rightCurrent

    const leftStatus = statusRank(left.status)
    const rightStatus = statusRank(right.status)
    if (leftStatus !== rightStatus) return leftStatus - rightStatus

    return String(right.created_at || '').localeCompare(String(left.created_at || ''))
  })
})

const candidateGroups = computed(() => {
  if (!props.currentTurnId) {
    return [{ key: 'all', title: '', items: sortedCandidates.value }]
  }

  const current = sortedCandidates.value.filter((candidate) => isCurrentTurnCandidate(candidate))
  const older = sortedCandidates.value.filter((candidate) => !isCurrentTurnCandidate(candidate))
  const groups = []
  if (current.length) {
    groups.push({ key: 'current', title: t('problemDetail.currentTurnConcepts'), items: current })
  }
  if (older.length) {
    groups.push({ key: 'older', title: t('problemDetail.earlierDerivedConcepts'), items: older })
  }
  return groups
})

const formatConfidence = (value: number | string | undefined | null) => {
  const parsed = Number(value ?? 0)
  if (!Number.isFinite(parsed)) return '0%'
  return `${Math.round(Math.max(0, Math.min(1, parsed)) * 100)}%`
}

const formatLearningMode = (mode: string | undefined | null) => {
  return mode === 'exploration'
    ? t('problemDetail.modeExploration')
    : t('problemDetail.modeSocratic')
}

const formatCandidateStatus = (status: string | undefined | null) => {
  if (status === 'accepted') return t('problemDetail.conceptStatusAccepted')
  if (status === 'rejected') return t('problemDetail.conceptStatusRejected')
  if (status === 'reverted') return t('problemDetail.conceptStatusReverted')
  if (status === 'postponed') return t('problemDetail.conceptStatusPostponed')
  if (status === 'merged') return t('problemDetail.conceptStatusMerged')
  return t('problemDetail.conceptStatusPending')
}

const formatCandidateSource = (source: string | undefined | null) => {
  if (source === 'problem_inline_qa' || source === 'ask') return t('problemDetail.derivedConceptSourceAsk')
  if (source === 'problem_response' || source === 'response') return t('problemDetail.derivedConceptSourceResponse')
  return source || t('problemDetail.derivedConceptSourceUnknown')
}

const mergeTargetsFor = (candidate: any) => {
  return (props.mergeTargets || []).filter((target) => normalizeKey(target) !== normalizeKey(candidate.concept_text))
}

const canModerate = (candidate: any) => ['pending', 'postponed'].includes(candidate.status)

const canMerge = (candidate: any) => canModerate(candidate) && mergeTargetsFor(candidate).length > 0

const emitMerge = (candidateId: string) => {
  const targetConcept = selectedMergeTargets.value[candidateId]
  if (!targetConcept) return
  emit('merge', { candidateId, targetConcept })
}
</script>

<style scoped>
.derived-concepts-card {
  height: fit-content;
}

.section-subtitle {
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.candidate-groups {
  display: grid;
  gap: 1rem;
}

.candidate-group {
  display: grid;
  gap: 0.5rem;
}

.group-title {
  font-size: 0.92rem;
  color: var(--text-muted);
}

.candidate-list {
  display: grid;
  gap: 0.75rem;
}

.candidate-item {
  padding: 0.8rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-dark);
}

.candidate-current {
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.25);
}

.candidate-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
}

.candidate-status {
  font-size: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  color: var(--text-muted);
}

.candidate-mode,
.candidate-confidence,
.candidate-meta {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.candidate-meta {
  margin-top: 0.4rem;
}

.candidate-evidence {
  margin-top: 0.45rem;
  font-size: 0.85rem;
  color: var(--text);
  white-space: pre-wrap;
}

.candidate-actions,
.candidate-merge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.65rem;
}

.merge-select {
  min-width: 0;
  flex: 1 1 180px;
}

.candidate-pending,
.candidate-postponed {
  border-color: rgba(250, 204, 21, 0.35);
}

.candidate-accepted,
.candidate-merged {
  border-color: rgba(34, 197, 94, 0.35);
}

.candidate-rejected,
.candidate-reverted {
  border-color: rgba(148, 163, 184, 0.28);
  opacity: 0.85;
}
</style>
