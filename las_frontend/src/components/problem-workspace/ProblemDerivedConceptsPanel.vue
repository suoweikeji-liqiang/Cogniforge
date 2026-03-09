<template>
  <section class="card derived-concepts-card" data-testid="derived-concepts-panel">
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
            :class="[
              `candidate-${candidate.status}`,
              {
                'candidate-current': isCurrentTurnCandidate(candidate),
                'candidate-needs-reinforcement': needsReinforcement(candidate),
                'candidate-focus-target': isFocusTarget(candidate),
              },
            ]"
            :data-testid="isFocusTarget(candidate) ? 'derived-concept-focus-target' : 'derived-concept-card'"
          >
            <div class="candidate-head">
              <strong>{{ candidate.concept_text }}</strong>
              <span v-if="isFocusTarget(candidate)" class="handoff-badge handoff-badge-alert">
                {{ t('problemDetail.reinforcementFocusBadge') }}
              </span>
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
                data-testid="accept-derived-concept"
                @click="emit('accept', candidate.id)"
              >
                {{ t('problemDetail.acceptCandidate') }}
              </button>
              <button
                type="button"
                class="btn btn-secondary"
                :disabled="actionPendingId === candidate.id"
                data-testid="reject-derived-concept"
                @click="emit('reject', candidate.id)"
              >
                {{ t('problemDetail.rejectCandidate') }}
              </button>
              <button
                v-if="candidate.status !== 'postponed'"
                type="button"
                class="btn btn-secondary"
                :disabled="actionPendingId === candidate.id"
                data-testid="postpone-derived-concept"
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
                data-testid="merge-derived-concept-target"
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
                data-testid="merge-derived-concept"
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
                data-testid="rollback-derived-concept"
                @click="emit('rollback', { candidateId: candidate.id, conceptText: candidate.concept_text })"
              >
                {{ t('problemDetail.rollbackConcept') }}
              </button>
            </div>

            <div v-if="['accepted', 'merged'].includes(candidate.status)" class="candidate-handoff">
              <p class="candidate-meta">
                <strong>{{ t('problemDetail.modelCardLinkLabel') }}:</strong>
                {{ isLinkedToModelCard(candidate) ? t('problemDetail.modelCardLinked') : t('problemDetail.modelCardNotLinked') }}
              </p>
              <p v-if="isReviewScheduled(candidate)" class="candidate-meta candidate-review-meta">
                <strong>{{ t('problemDetail.reviewStatusLabel') }}:</strong>
                {{ formatReviewSchedule(candidate) }}
              </p>
              <p v-if="isReviewScheduled(candidate)" class="candidate-meta candidate-review-meta">
                <strong>{{ t('problemDetail.reviewConsequenceLabel') }}:</strong>
                {{ formatRecallConsequence(candidate) }}
              </p>
              <div
                v-if="needsReinforcement(candidate)"
                class="candidate-reinforcement-panel"
                data-testid="derived-concept-needs-reinforcement"
              >
                <span class="handoff-badge handoff-badge-alert">{{ t('problemDetail.needsReinforcementBadge') }}</span>
                <p class="candidate-meta candidate-review-meta">
                  <strong>{{ t('problemDetail.reinforcementResumeLabel') }}:</strong>
                  {{ formatReinforcementResume(candidate) }}
                </p>
              </div>
              <div class="candidate-actions">
                <button
                  v-if="!isLinkedToModelCard(candidate)"
                  type="button"
                  class="btn btn-secondary"
                  :disabled="handoffPendingId === candidate.id"
                  data-testid="promote-derived-concept"
                  @click="emit('promote', candidate.id)"
                >
                  {{ t('problemDetail.promoteConceptToModelCard') }}
                </button>
                <button
                  v-else
                  type="button"
                  class="btn btn-secondary"
                  :disabled="handoffPendingId === candidate.id"
                  data-testid="open-derived-concept-model-card"
                  @click="emit('openCard', candidate.linked_model_card_id)"
                >
                  {{ t('problemDetail.openModelCard') }}
                </button>
                <button
                  v-if="isLinkedToModelCard(candidate) && !isReviewScheduled(candidate)"
                  type="button"
                  class="btn btn-secondary"
                  :disabled="handoffPendingId === candidate.id"
                  data-testid="schedule-derived-concept-review"
                  @click="emit('scheduleReview', candidate.id)"
                >
                  {{ t('problemDetail.addConceptToReview') }}
                </button>
                <span
                  v-if="isReviewScheduled(candidate)"
                  class="handoff-badge"
                  data-testid="derived-concept-review-scheduled"
                >
                  {{ t('problemDetail.reviewScheduled') }}
                </span>
              </div>
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
  handoffPendingId?: string | null
  scheduledModelCardIds?: string[]
  scheduledReviewsByModelCardId?: Record<string, any>
  focusCandidateId?: string | null
  focusTurnId?: string | null
  focusConceptText?: string | null
}>()

const emit = defineEmits<{
  accept: [candidateId: string]
  reject: [candidateId: string]
  postpone: [candidateId: string]
  merge: [payload: { candidateId: string; targetConcept: string }]
  rollback: [payload: { candidateId: string; conceptText: string }]
  promote: [candidateId: string]
  openCard: [modelCardId: string]
  scheduleReview: [candidateId: string]
}>()

const { t } = useI18n()
const selectedMergeTargets = ref<Record<string, string>>({})

const normalizeKey = (value: string | undefined | null) => String(value || '').trim().toLowerCase()

const isCurrentTurnCandidate = (candidate: any) => Boolean(props.currentTurnId && candidate.source_turn_id === props.currentTurnId)
const isFocusTarget = (candidate: any) => {
  if (!candidate) return false
  if (props.focusCandidateId && String(candidate.id) === String(props.focusCandidateId)) return true
  if (!props.focusTurnId || String(candidate.source_turn_id || '') !== String(props.focusTurnId)) return false
  if (props.focusConceptText) {
    return normalizeKey(candidate.concept_text) === normalizeKey(props.focusConceptText)
  }
  return true
}

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
    const leftFocus = isFocusTarget(left) ? 0 : 1
    const rightFocus = isFocusTarget(right) ? 0 : 1
    if (leftFocus !== rightFocus) return leftFocus - rightFocus

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

const isLinkedToModelCard = (candidate: any) => Boolean(candidate.linked_model_card_id)

const isReviewScheduled = (candidate: any) => {
  return Boolean(
    candidate.linked_model_card_id
      && (props.scheduledModelCardIds || []).includes(String(candidate.linked_model_card_id))
  )
}

const getReviewSchedule = (candidate: any) => {
  if (!candidate?.linked_model_card_id) return null
  return props.scheduledReviewsByModelCardId?.[String(candidate.linked_model_card_id)] || null
}

const needsReinforcement = (candidate: any) => Boolean(getReviewSchedule(candidate)?.needs_reinforcement)

const formatReviewSchedule = (candidate: any) => {
  const schedule = getReviewSchedule(candidate)
  if (!schedule) return t('problemDetail.reviewScheduled')

  const dateValue = schedule.last_reviewed_at || schedule.next_review_at
  const formattedDate = dateValue ? new Date(dateValue).toLocaleString() : '-'
  if (schedule.last_reviewed_at) {
    return t('problemDetail.reviewScheduledLastReviewedAt', { date: formattedDate })
  }
  return t('problemDetail.reviewScheduledNextAt', { date: formattedDate })
}

const formatRecallState = (state: string | undefined | null) => {
  if (state === 'fragile') return t('problemDetail.recallStateFragile')
  if (state === 'rebuilding') return t('problemDetail.recallStateRebuilding')
  if (state === 'reinforcing') return t('problemDetail.recallStateReinforcing')
  if (state === 'stable') return t('problemDetail.recallStateStable')
  return t('problemDetail.recallStateScheduled')
}

const formatRecommendedAction = (action: string | undefined | null) => {
  if (action === 'revisit_workspace') return t('problemDetail.reviewActionRevisitWorkspace')
  if (action === 'reinforce_soon') return t('problemDetail.reviewActionReinforceSoon')
  if (action === 'keep_spacing') return t('problemDetail.reviewActionKeepSpacing')
  if (action === 'extend_or_compare') return t('problemDetail.reviewActionExtendOrCompare')
  return t('problemDetail.reviewActionCompleteFirstRecall')
}

const formatRecallConsequence = (candidate: any) => {
  const schedule = getReviewSchedule(candidate)
  if (!schedule) return t('problemDetail.reviewActionCompleteFirstRecall')
  return t('problemDetail.reviewConsequenceSummary', {
    state: formatRecallState(schedule.recall_state),
    action: formatRecommendedAction(schedule.recommended_action),
  })
}

const formatReinforcementResume = (candidate: any) => {
  const target = getReviewSchedule(candidate)?.reinforcement_target
  const pathLabel = formatReinforcementPath(target)
  const rawStepIndex = Number(target?.resume_step_index)
  const hasStepIndex = Number.isFinite(rawStepIndex)
  const stepNumber = hasStepIndex ? rawStepIndex + 1 : null
  const stepConcept = String(target?.resume_step_concept || '').trim()

  if (stepNumber !== null && stepConcept) {
    const stepLabel = t('problemDetail.reinforcementResumeStepConcept', {
      step: stepNumber,
      concept: stepConcept,
    })
    return pathLabel ? `${pathLabel} · ${stepLabel}` : stepLabel
  }
  if (stepNumber !== null) {
    const stepLabel = t('problemDetail.reinforcementResumeStepOnly', { step: stepNumber })
    return pathLabel ? `${pathLabel} · ${stepLabel}` : stepLabel
  }
  if (stepConcept) {
    const conceptLabel = t('problemDetail.reinforcementResumeConcept', { concept: stepConcept })
    return pathLabel ? `${pathLabel} · ${conceptLabel}` : conceptLabel
  }
  return pathLabel || t('problemDetail.reinforcementResumeCurrentWorkspace')
}

const formatReinforcementPath = (target: any) => {
  const title = String(target?.resume_path_title || '').trim()
  const kind = String(target?.resume_path_kind || '').trim()
  const kindLabel = kind ? formatLearningPathKind(kind) : ''
  if (kindLabel && title) return `${kindLabel} · ${title}`
  if (title) return title
  if (kindLabel) return kindLabel
  return ''
}

const formatLearningPathKind = (kind: string | undefined | null) => {
  if (kind === 'prerequisite') return t('problemDetail.pathKindPrerequisite')
  if (kind === 'comparison') return t('problemDetail.pathKindComparison')
  if (kind === 'branch') return t('problemDetail.pathKindBranch')
  return t('problemDetail.pathKindMain')
}

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

.candidate-focus-target {
  border-color: rgba(248, 113, 113, 0.42);
  box-shadow: 0 0 0 2px rgba(248, 113, 113, 0.18);
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

.candidate-review-meta {
  color: #bbf7d0;
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

.candidate-handoff {
  margin-top: 0.75rem;
  padding-top: 0.7rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.merge-select {
  min-width: 0;
  flex: 1 1 180px;
}

.handoff-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: rgba(74, 222, 128, 0.14);
  border: 1px solid rgba(74, 222, 128, 0.3);
  color: #86efac;
  font-size: 0.78rem;
  font-weight: 600;
}

.handoff-badge-alert {
  background: rgba(248, 113, 113, 0.14);
  border-color: rgba(248, 113, 113, 0.3);
  color: #fecaca;
}

.candidate-reinforcement-panel {
  display: grid;
  gap: 0.4rem;
  margin-top: 0.65rem;
}

.candidate-pending,
.candidate-postponed {
  border-color: rgba(250, 204, 21, 0.35);
}

.candidate-accepted,
.candidate-merged {
  border-color: rgba(34, 197, 94, 0.35);
}

.candidate-needs-reinforcement {
  border-color: rgba(248, 113, 113, 0.36);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.14);
}

.candidate-rejected,
.candidate-reverted {
  border-color: rgba(148, 163, 184, 0.28);
  opacity: 0.85;
}
</style>
