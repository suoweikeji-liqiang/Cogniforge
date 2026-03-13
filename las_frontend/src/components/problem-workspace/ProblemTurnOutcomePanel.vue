<template>
  <section :class="embedded ? 'turn-outcome-embedded' : 'card turn-outcome-card'" data-testid="turn-outcome-panel">
    <template v-if="!embedded">
      <h2>{{ t('problemDetail.turnResultTitle') }}</h2>
      <p class="section-subtitle">
        {{ learningMode === 'exploration' ? t('problemDetail.turnResultSubtitleExploration') : t('problemDetail.turnResultSubtitleSocratic') }}
      </p>
    </template>

    <template v-if="learningMode === 'socratic'">
      <div v-if="latestResponse && latestFeedback" class="turn-outcome-body">
        <div class="turn-summary-grid">
          <article class="result-summary-card" data-testid="turn-result-status-card">
            <span class="summary-label">{{ t('problemDetail.turnResultStatusLabel') }}</span>
            <strong>{{ socraticSummary.status }}</strong>
            <p>{{ socraticSummary.statusSupport }}</p>
          </article>
          <article class="result-summary-card" data-testid="turn-result-gap-card">
            <span class="summary-label">{{ t('problemDetail.turnResultGapLabel') }}</span>
            <strong>{{ socraticSummary.gap }}</strong>
            <p>{{ socraticSummary.gapSupport }}</p>
          </article>
          <article class="result-summary-card" data-testid="turn-result-next-card">
            <span class="summary-label">{{ t('problemDetail.turnResultNextLabel') }}</span>
            <strong>{{ socraticSummary.next }}</strong>
            <p>{{ socraticSummary.nextSupport }}</p>
          </article>
        </div>

        <details class="turn-outcome-details" :open="!embedded">
          <summary>{{ t('problemDetail.turnResultDetailsToggle') }}</summary>
          <div class="turn-outcome-detail-stack">
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
        <div v-if="latestFeedback.misconceptions?.length" class="artifact-block">
          <strong>{{ t('feedback.misconceptions') }}</strong>
          <ul class="artifact-actions">
            <li v-for="(item, index) in latestFeedback.misconceptions" :key="`misconception-${index}`">{{ item }}</li>
          </ul>
        </div>
        <div v-if="latestFeedback.suggestions?.length" class="artifact-block">
          <strong>{{ t('feedback.suggestions') }}</strong>
          <ul class="artifact-actions">
            <li v-for="(item, index) in latestFeedback.suggestions" :key="`suggestion-${index}`">{{ item }}</li>
          </ul>
        </div>
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
        <div v-if="socraticActionHints.length" class="artifact-block">
          <strong>{{ t('problemDetail.nextActionTitle') }}</strong>
          <ul class="artifact-actions">
            <li v-for="(hint, index) in socraticActionHints" :key="`socratic-hint-${index}`">{{ hint }}</li>
          </ul>
        </div>
          </div>
        </details>
      </div>
      <p v-else class="empty">{{ t('problemDetail.noTurnResultSocratic') }}</p>
    </template>

    <template v-else>
      <div v-if="latestQa" class="turn-outcome-body">
        <div class="turn-summary-grid">
          <article class="result-summary-card" data-testid="turn-result-status-card">
            <span class="summary-label">{{ t('problemDetail.turnResultStatusLabel') }}</span>
            <strong>{{ explorationSummary.status }}</strong>
            <p>{{ explorationSummary.statusSupport }}</p>
          </article>
          <article class="result-summary-card" data-testid="turn-result-gap-card">
            <span class="summary-label">{{ t('problemDetail.turnResultInsightLabel') }}</span>
            <strong>{{ explorationSummary.insight }}</strong>
            <p>{{ explorationSummary.insightSupport }}</p>
          </article>
          <article class="result-summary-card" data-testid="turn-result-next-card">
            <span class="summary-label">{{ t('problemDetail.turnResultNextLabel') }}</span>
            <strong>{{ explorationSummary.next }}</strong>
            <p>{{ explorationSummary.nextSupport }}</p>
          </article>
        </div>

        <details class="turn-outcome-details" :open="!embedded">
          <summary>{{ t('problemDetail.turnResultDetailsToggle') }}</summary>
          <div class="turn-outcome-detail-stack">
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
        <div v-if="explorationActionHints.length" class="artifact-block">
          <strong>{{ t('problemDetail.nextActionTitle') }}</strong>
          <ul class="artifact-actions">
            <li v-for="(hint, index) in explorationActionHints" :key="`exploration-hint-${index}`">{{ hint }}</li>
          </ul>
        </div>
          </div>
        </details>
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
  embedded?: boolean
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

const buildActionHints = (acceptedConcepts: any[], pendingConcepts: any[], pathSuggestions: any[]) => {
  const hints = []
  if (acceptedConcepts?.length) {
    hints.push(t('problemDetail.handoffHintPromoteConcepts'))
  }
  if (pendingConcepts?.length) {
    hints.push(t('problemDetail.handoffHintReviewPendingConcepts'))
  }
  if (pathSuggestions?.length) {
    hints.push(t('problemDetail.handoffHintReviewPathSuggestions'))
  }
  return hints
}

const socraticActionHints = computed(() => {
  return buildActionHints(
    props.latestResponse?.accepted_concepts || [],
    props.latestResponse?.pending_concepts || [],
    props.latestResponse?.derived_path_candidates || [],
  )
})

const explorationActionHints = computed(() => {
  return buildActionHints(
    props.latestQa?.accepted_concepts || [],
    props.latestQa?.pending_concepts || [],
    displayPathSuggestions.value,
  )
})

const normalizeInline = (value: unknown) => String(value || '').replace(/\s+/g, ' ').trim()

const truncateInline = (value: unknown, max = 140) => {
  const normalized = normalizeInline(value)
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, max - 1).trimEnd()}…`
}

const socraticSummary = computed(() => {
  const mastery = props.latestFeedback?.mastery_score
  const confidence = formatConfidence(props.latestFeedback?.confidence)
  const progressed = props.latestResponse?.decision?.advance
  const misconceptions = props.latestFeedback?.misconceptions || []
  const suggestions = props.latestFeedback?.suggestions || []
  const followUp = normalizeInline(props.latestResponse?.follow_up?.question)
  const decisionReason = normalizeInline(props.latestResponse?.decision?.reason)
  const correctness = normalizeInline(props.latestFeedback?.correctness)

  const status = progressed
    ? t('problemDetail.turnResultAdvanced')
    : t('problemDetail.turnResultNeedsWork')

  const statusSupport = mastery !== undefined
    ? t('problemDetail.turnResultScoreConfidence', { score: mastery, confidence })
    : (correctness || t('problemDetail.turnResultStatusSupportFallback'))

  const gap = truncateInline(misconceptions[0] || decisionReason || correctness || t('problemDetail.turnResultGapFallback'))
  const gapSupport = truncateInline(suggestions[0] || t('problemDetail.turnResultGapSupportFallback'))

  const next = truncateInline(followUp || suggestions[0] || socraticActionHints.value[0] || t('problemDetail.turnResultNextFallback'))
  const nextSupport = props.latestResponse?.question_kind
    ? t('problemDetail.turnResultNextSupportQuestionKind', { kind: formatQuestionKind(props.latestResponse.question_kind) })
    : t('problemDetail.turnResultNextSupportSocratic')

  return { status, statusSupport, gap, gapSupport, next, nextSupport }
})

const explorationSummary = computed(() => {
  const nextActions = props.latestQa?.next_learning_actions || []
  const answeredConcepts = props.latestQa?.answered_concepts || []
  const relatedConcepts = props.latestQa?.related_concepts || []
  const answerType = formatAnswerType(props.latestQa?.answer_type)
  const answer = truncateInline(props.latestQa?.answer || t('problemDetail.turnResultInsightFallback'), 180)
  const next = truncateInline(
    nextActions[0]
      || props.latestQa?.suggested_next_focus
      || explorationActionHints.value[0]
      || t('problemDetail.turnResultNextFallback'),
  )

  const statusSupport = answeredConcepts.length
    ? t('problemDetail.turnResultStatusSupportAnswered', { concepts: answeredConcepts.join(' / ') })
    : (relatedConcepts.length
      ? t('problemDetail.turnResultStatusSupportRelated', { concepts: relatedConcepts.join(' / ') })
      : t('problemDetail.turnResultStatusSupportExplorationFallback'))

  const insightSupport = props.latestQa?.return_to_main_path_hint
    ? t('problemDetail.turnResultInsightSupportReturn')
    : t('problemDetail.turnResultInsightSupportStay')

  const nextSupport = displayPathSuggestions.value.length
    ? t('problemDetail.turnResultNextSupportPaths', { count: displayPathSuggestions.value.length })
    : t('problemDetail.turnResultNextSupportExploration')

  return {
    status: answerType,
    statusSupport,
    insight: answer,
    insightSupport,
    next,
    nextSupport,
  }
})
</script>

<style scoped>
.turn-outcome-card {
  height: fit-content;
}

.turn-outcome-embedded {
  display: grid;
  gap: 0.55rem;
}

.turn-outcome-body {
  display: grid;
  gap: 0.55rem;
}

.turn-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.result-summary-card {
  display: grid;
  gap: 0.35rem;
  padding: 0.85rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.45);
}

.summary-label {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.result-summary-card strong {
  font-size: 0.96rem;
}

.result-summary-card p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.turn-outcome-details {
  border-top: 1px solid var(--border);
  padding-top: 0.75rem;
}

.turn-outcome-details summary {
  cursor: pointer;
  color: var(--text-secondary);
  font-weight: 600;
}

.turn-outcome-detail-stack {
  display: grid;
  gap: 0.55rem;
  margin-top: 0.75rem;
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
