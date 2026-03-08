<template>
  <section class="card turn-outcome-card" data-testid="turn-outcome-panel">
    <h2>{{ t('problemDetail.turnResultTitle') }}</h2>
    <p class="section-subtitle">
      {{ learningMode === 'exploration' ? t('problemDetail.turnResultSubtitleExploration') : t('problemDetail.turnResultSubtitleSocratic') }}
    </p>

    <template v-if="learningMode === 'socratic'">
      <div v-if="latestResponse && latestFeedback" class="turn-outcome-body">
        <p v-if="latestResponse.question_kind" class="meta-line">
          <strong>{{ t('problemDetail.questionKind') }}:</strong> {{ formatQuestionKind(latestResponse.question_kind) }}
        </p>
        <p v-if="latestResponse.socratic_question" class="meta-line">
          <strong>{{ t('problemDetail.questionLabel') }}:</strong> {{ latestResponse.socratic_question }}
        </p>
        <p v-if="latestFeedback.correctness">
          <strong>{{ t('feedback.correctness') }}:</strong> {{ latestFeedback.correctness }}
        </p>
        <p v-if="latestFeedback.mastery_score !== undefined">
          <strong>{{ t('problemDetail.masteryScore') }}:</strong> {{ latestFeedback.mastery_score }}
          · <strong>{{ t('problemDetail.confidence') }}:</strong> {{ formatConfidence(latestFeedback.confidence) }}
        </p>
        <p v-if="latestResponse.decision" class="meta-line">
          <strong>{{ t('problemDetail.progressionDecision') }}:</strong>
          {{ latestResponse.decision.advance ? t('problemDetail.advanceYes') : t('problemDetail.advanceNo') }}
          · {{ latestResponse.decision.progression_ran ? t('problemDetail.progressionRan') : t('problemDetail.progressionSkipped') }}
        </p>
        <p v-if="latestResponse.follow_up?.needed && latestResponse.follow_up?.question">
          <strong>{{ t('problemDetail.nextActionTitle') }}:</strong> {{ latestResponse.follow_up.question }}
        </p>
        <p v-if="latestResponse.accepted_concepts?.length" class="accent-line">
          <strong>{{ t('problemDetail.newConceptsTitle') }}:</strong> {{ latestResponse.accepted_concepts.join(' / ') }}
        </p>
        <p v-if="latestResponse.pending_concepts?.length" class="pending-line">
          <strong>{{ t('problemDetail.pendingConceptsTitle') }}:</strong> {{ latestResponse.pending_concepts.join(' / ') }}
        </p>
        <div v-if="latestResponse.derived_path_candidates?.length" class="artifact-block">
          <strong>{{ t('problemDetail.pathSuggestions') }}</strong>
          <div class="artifact-list">
            <div
              v-for="candidate in latestResponse.derived_path_candidates"
              :key="candidate.id || candidate.title"
              class="artifact-item"
            >
              <div class="artifact-head">
                <span class="artifact-badge">{{ formatPathSuggestionType(candidate.type) }}</span>
                <strong>{{ candidate.title }}</strong>
              </div>
              <p v-if="candidate.reason">{{ candidate.reason }}</p>
            </div>
          </div>
        </div>
      </div>
      <p v-else class="empty">{{ t('problemDetail.noTurnResultSocratic') }}</p>
    </template>

    <template v-else>
      <div v-if="latestQa" class="turn-outcome-body">
        <p v-if="latestQa.answer_type" class="meta-line">
          <strong>{{ t('problemDetail.answerType') }}:</strong> {{ formatAnswerType(latestQa.answer_type) }}
        </p>
        <div class="qa-block">
          <strong>{{ t('problemDetail.answerLabel') }}</strong>
          <p>{{ latestQa.answer }}</p>
        </div>
        <p v-if="latestQa.answered_concepts?.length" class="meta-line">
          <strong>{{ t('problemDetail.answeredConcepts') }}:</strong> {{ latestQa.answered_concepts.join(' / ') }}
        </p>
        <p v-if="latestQa.related_concepts?.length" class="meta-line">
          <strong>{{ t('problemDetail.relatedConcepts') }}:</strong> {{ latestQa.related_concepts.join(' / ') }}
        </p>
        <div v-if="latestQa.next_learning_actions?.length" class="artifact-block">
          <strong>{{ t('problemDetail.nextActionTitle') }}</strong>
          <ul class="artifact-actions">
            <li v-for="(action, index) in latestQa.next_learning_actions" :key="`${index}-${action}`">{{ action }}</li>
          </ul>
        </div>
        <div v-if="displayPathSuggestions.length" class="artifact-block">
          <strong>{{ t('problemDetail.pathSuggestions') }}</strong>
          <div class="artifact-list">
            <div
              v-for="candidate in displayPathSuggestions"
              :key="candidate.id || candidate.title"
              class="artifact-item"
            >
              <div class="artifact-head">
                <span class="artifact-badge">{{ formatPathSuggestionType(candidate.type) }}</span>
                <strong>{{ candidate.title }}</strong>
              </div>
              <p v-if="candidate.reason">{{ candidate.reason }}</p>
            </div>
          </div>
        </div>
        <p class="meta-line">
          <strong>{{ t('problemDetail.returnToMainPath') }}:</strong>
          {{ latestQa.return_to_main_path_hint ? t('problemDetail.returnToMainPathYes') : t('problemDetail.returnToMainPathNo') }}
        </p>
        <p v-if="latestQa.accepted_concepts?.length" class="accent-line">
          <strong>{{ t('problemDetail.newConceptsTitle') }}:</strong> {{ latestQa.accepted_concepts.join(' / ') }}
        </p>
        <p v-if="latestQa.pending_concepts?.length" class="pending-line">
          <strong>{{ t('problemDetail.pendingConceptsTitle') }}:</strong> {{ latestQa.pending_concepts.join(' / ') }}
        </p>
      </div>
      <p v-else class="empty">{{ t('problemDetail.noTurnResultExploration') }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  learningMode: 'socratic' | 'exploration'
  latestResponse?: any | null
  latestFeedback?: any | null
  latestQa?: any | null
}>()

const { t } = useI18n()

const formatConfidence = (value: number | string | undefined | null) => {
  const parsed = Number(value ?? 0)
  if (!Number.isFinite(parsed)) return '0%'
  return `${Math.round(Math.max(0, Math.min(1, parsed)) * 100)}%`
}

const formatQuestionKind = (kind: string | undefined | null) => {
  return kind === 'checkpoint'
    ? t('problemDetail.questionKindCheckpoint')
    : t('problemDetail.questionKindProbe')
}

const formatAnswerType = (answerType: string | undefined | null) => {
  if (answerType === 'boundary_clarification') return t('problemDetail.answerTypeBoundaryClarification')
  if (answerType === 'misconception_correction') return t('problemDetail.answerTypeMisconceptionCorrection')
  if (answerType === 'comparison') return t('problemDetail.answerTypeComparison')
  if (answerType === 'prerequisite_explanation') return t('problemDetail.answerTypePrerequisiteExplanation')
  if (answerType === 'worked_example') return t('problemDetail.answerTypeWorkedExample')
  return t('problemDetail.answerTypeConceptExplanation')
}

const formatPathSuggestionType = (pathType: string | undefined | null) => {
  if (pathType === 'prerequisite') return t('problemDetail.pathSuggestionPrerequisite')
  if (pathType === 'comparison_path') return t('problemDetail.pathSuggestionComparisonPath')
  return t('problemDetail.pathSuggestionBranchDeepDive')
}

const displayPathSuggestions = computed(() => {
  if (props.latestQa?.derived_path_candidates?.length) {
    return props.latestQa.derived_path_candidates
  }
  return props.latestQa?.path_suggestions || []
})
</script>

<style scoped>
.turn-outcome-card {
  height: fit-content;
}

.turn-outcome-body {
  display: grid;
  gap: 0.55rem;
}

.section-subtitle {
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.meta-line {
  color: var(--text-muted);
  font-size: 0.86rem;
}

.accent-line {
  color: #86efac;
}

.pending-line {
  color: #fcd34d;
}

.artifact-block {
  margin-top: 0.4rem;
}

.artifact-actions {
  margin: 0.35rem 0 0;
  padding-left: 1.1rem;
}

.artifact-actions li + li {
  margin-top: 0.2rem;
}

.artifact-list {
  display: grid;
  gap: 0.5rem;
  margin-top: 0.45rem;
}

.artifact-item {
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-dark);
}

.artifact-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.artifact-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.14rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  color: #bfdbfe;
  font-size: 0.75rem;
  font-weight: 600;
}

.qa-block p {
  margin-top: 0.25rem;
  white-space: pre-wrap;
}
</style>
