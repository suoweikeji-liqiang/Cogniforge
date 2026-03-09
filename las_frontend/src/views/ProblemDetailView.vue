<template>
  <div class="problem-detail" data-testid="problem-detail-workspace">
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <template v-else-if="problem">
      <div class="problem-header">
        <router-link to="/problems" class="back-link">&larr; {{ t('common.back') }}</router-link>
        <h1>{{ problem.title }}</h1>
        <p>{{ problem.description }}</p>
        <div class="problem-meta">
          <span class="status" :class="problem.status">{{ problem.status }}</span>
          <span class="mode-badge">{{ t('problemDetail.currentMode') }}: {{ formatLearningMode(learningMode) }}</span>
          <span v-if="totalSteps" class="progress-text">
            {{ t('problemDetail.progress') }}: {{ completedSteps }}/{{ totalSteps }}
          </span>
        </div>
      </div>

      <div class="problem-content">
        <div class="workspace-stage workspace-stage-unified">
          <div class="workspace-main-column workspace-main-stack">
            <section class="card workspace-overview-card" data-testid="workspace-overview">
              <div class="workspace-overview-head">
                <div>
                  <p class="workspace-eyebrow">{{ t('nav.workspace') }}</p>
                  <h2>{{ t('problemDetail.workspaceOverviewTitle') }}</h2>
                  <p class="section-subtitle">{{ t('problemDetail.workspaceOverviewSubtitle') }}</p>
                </div>
                <div class="workspace-overview-actions">
                  <router-link to="/reviews" class="btn btn-secondary workspace-link-action">
                    {{ t('modelCards.openReviewHub') }}
                  </router-link>
                  <router-link to="/model-cards" class="btn btn-secondary workspace-link-action">
                    {{ t('reviews.openModelCards') }}
                  </router-link>
                </div>
              </div>

              <div class="workspace-summary-grid">
                <article class="workspace-summary-card">
                  <span class="workspace-summary-label">{{ t('problemDetail.currentStepTitle') }}</span>
                  <strong>{{ workspaceFocusTitle }}</strong>
                  <p>{{ workspaceFocusDescription }}</p>
                </article>
                <article class="workspace-summary-card" data-testid="workspace-path-summary">
                  <span class="workspace-summary-label">{{ t('problemDetail.currentPath') }}</span>
                  <strong>{{ workspacePathSummary }}</strong>
                  <p v-if="learningPath?.branch_reason">{{ learningPath.branch_reason }}</p>
                  <p v-else-if="learningPath?.parent_path_id && learningPath?.return_step_id !== null && learningPath?.return_step_id !== undefined">
                    {{ t('problemDetail.returnStepLabel', { step: learningPath.return_step_id + 1 }) }}
                  </p>
                  <p v-else>{{ t('problemDetail.progress') }}: {{ completedSteps }}/{{ totalSteps || 0 }}</p>
                </article>
                <article class="workspace-summary-card">
                  <span class="workspace-summary-label">{{ t('problemDetail.turnResultTitle') }}</span>
                  <strong>{{ workspaceTurnSummary }}</strong>
                  <p>{{ learningMode === 'exploration' ? t('problemDetail.turnResultSubtitleExploration') : t('problemDetail.turnResultSubtitleSocratic') }}</p>
                </article>
                <article class="workspace-summary-card">
                  <span class="workspace-summary-label">{{ t('problemDetail.nextActionTitle') }}</span>
                  <strong>{{ workspaceNextAction }}</strong>
                  <p>{{ learningMode === 'exploration' ? t('problemDetail.modeExplorationHint') : t('problemDetail.modeSocraticHint') }}</p>
                </article>
                <article class="workspace-summary-card" data-testid="workspace-review-summary">
                  <span class="workspace-summary-label">{{ t('problemDetail.reviewLoopTitle') }}</span>
                  <strong>{{ workspaceReviewSummary }}</strong>
                  <p>{{ workspaceReviewDescription }}</p>
                </article>
              </div>

              <div class="workspace-mode-row">
                <div class="workspace-mode-copy">
                  <span class="workspace-summary-label">{{ t('problemDetail.currentMode') }}</span>
                  <strong>{{ formatLearningMode(learningMode) }}</strong>
                  <p class="section-subtitle">
                    {{ learningMode === 'socratic' ? t('problemDetail.modeSocraticHint') : t('problemDetail.modeExplorationHint') }}
                  </p>
                </div>
                <div class="workspace-mode-toggle">
                  <button
                    type="button"
                    class="btn btn-secondary"
                    :class="{ active: learningMode === 'socratic' }"
                    :disabled="switchingMode || submitting || askingQuestion"
                    data-testid="mode-switch-socratic"
                    @click="setLearningMode('socratic')"
                  >
                    {{ t('problemDetail.modeSocratic') }}
                  </button>
                  <button
                    type="button"
                    class="btn btn-secondary"
                    :class="{ active: learningMode === 'exploration' }"
                    :disabled="switchingMode || submitting || askingQuestion"
                    data-testid="mode-switch-exploration"
                    @click="setLearningMode('exploration')"
                  >
                    {{ t('problemDetail.modeExploration') }}
                  </button>
                </div>
              </div>
            </section>

            <section
              v-if="activeReinforcementTarget && activeReinforcementEntry"
              class="card reinforcement-target-card"
              data-testid="workspace-reinforcement-target"
            >
              <div class="reinforcement-head">
                <div>
                  <p class="workspace-eyebrow">{{ t('problemDetail.reinforcementTargetTitle') }}</p>
                  <h2>{{ activeReinforcementTarget.concept_text || t('problemDetail.derivedConceptsTitle') }}</h2>
                  <p class="section-subtitle">{{ formatReinforcementSummary(activeReinforcementEntry) }}</p>
                </div>
                <span class="reinforcement-priority" :class="`priority-${activeReinforcementTarget.priority || 'medium'}`">
                  {{ t('problemDetail.needsReinforcementBadge') }}
                </span>
              </div>

              <div class="reinforcement-grid">
                <article class="workspace-summary-card">
                  <span class="workspace-summary-label">{{ t('problemDetail.reinforcementWorkspaceLabel') }}</span>
                  <strong>{{ activeReinforcementTarget.problem_title || problem.title }}</strong>
                  <p>{{ formatLearningMode(activeReinforcementEntry.origin?.learning_mode || learningMode) }}</p>
                </article>
                <article v-if="hasReinforcementPath(activeReinforcementTarget)" class="workspace-summary-card">
                  <span class="workspace-summary-label">{{ t('problemDetail.reinforcementPathLabel') }}</span>
                  <strong>{{ formatReinforcementPath(activeReinforcementTarget) }}</strong>
                  <p>{{ t('problemDetail.reinforcementPathHint') }}</p>
                </article>
                <article class="workspace-summary-card">
                  <span class="workspace-summary-label">{{ t('problemDetail.reinforcementResumeLabel') }}</span>
                  <strong>{{ formatReinforcementResume(activeReinforcementTarget) }}</strong>
                  <p>{{ t('problemDetail.reinforcementResumeHint') }}</p>
                </article>
                <article class="workspace-summary-card">
                  <span class="workspace-summary-label">{{ t('problemDetail.nextActionTitle') }}</span>
                  <strong>{{ formatRecommendedAction(activeReinforcementEntry.recommended_action) }}</strong>
                  <p>{{ t('problemDetail.reinforcementActionHint') }}</p>
                </article>
              </div>

              <article class="workspace-summary-card reinforcement-focus-card" data-testid="workspace-reinforcement-focus">
                <span class="workspace-summary-label">{{ t('problemDetail.reinforcementFocusTitle') }}</span>
                <strong>{{ reinforcementFocusTitle }}</strong>
                <p>{{ reinforcementFocusDescription }}</p>
                <p v-if="reinforcementFocusTurnPreview" class="reinforcement-preview">
                  <strong>{{ t('problemDetail.sourceTurnLabel') }}:</strong>
                  {{ reinforcementFocusTurnPreview }}
                </p>
              </article>

              <article
                v-if="reinforcementActionTemplate"
                class="workspace-summary-card reinforcement-action-card"
                data-testid="workspace-reinforcement-action"
              >
                <span class="workspace-summary-label">{{ t('problemDetail.reinforcementActionTitle') }}</span>
                <strong>{{ reinforcementActionTemplate.title }}</strong>
                <p>{{ reinforcementActionTemplate.description }}</p>
                <div
                  v-if="reinforcementActionTemplate.sourceCue"
                  class="reinforcement-action-source"
                  data-testid="reinforcement-starter-source-cue"
                >
                  <strong>{{ t('problemDetail.reinforcementStarterGroundingLabel') }}</strong>
                  <p>{{ reinforcementActionTemplate.sourceCue }}</p>
                </div>
                <div
                  v-if="reinforcementActionTemplate.sourceClue"
                  class="reinforcement-action-source"
                  data-testid="reinforcement-starter-source-clue"
                >
                  <strong>{{ t('problemDetail.reinforcementStarterClueLabel') }}</strong>
                  <p>{{ reinforcementActionTemplate.sourceClue }}</p>
                </div>
                <div
                  v-if="reinforcementActionTemplate.likelyConfusion"
                  class="reinforcement-action-source reinforcement-action-warning"
                  data-testid="reinforcement-likely-confusion"
                >
                  <strong>{{ t('problemDetail.reinforcementLikelyConfusionLabel') }}</strong>
                  <p>{{ reinforcementActionTemplate.likelyConfusion }}</p>
                </div>
                <div
                  v-if="reinforcementActionTemplate.evidenceCue"
                  class="reinforcement-action-source"
                  data-testid="reinforcement-starter-evidence"
                >
                  <strong>{{ t('problemDetail.reinforcementStarterEvidenceLabel') }}</strong>
                  <p>{{ reinforcementActionTemplate.evidenceCue }}</p>
                </div>
                <div class="reinforcement-action-starter">
                  <strong>{{ t('problemDetail.reinforcementStarterLabel') }}</strong>
                  <p>{{ reinforcementActionTemplate.starter }}</p>
                </div>
                <button
                  type="button"
                  class="btn btn-primary"
                  data-testid="apply-reinforcement-action-template"
                  @click="applyReinforcementActionTemplate"
                >
                  {{ t('problemDetail.useReinforcementStarter') }}
                </button>
              </article>

              <p
                v-if="activeReinforcementTarget.source_turn_preview && activeReinforcementTarget.source_turn_preview !== reinforcementFocusTurnPreview"
                class="reinforcement-preview"
              >
                <strong>{{ t('problemDetail.sourceTurnLabel') }}:</strong>
                {{ activeReinforcementTarget.source_turn_preview }}
              </p>

              <div class="reinforcement-actions">
                <button
                  v-if="canSwitchToReinforcementPath"
                  type="button"
                  class="btn btn-primary"
                  data-testid="switch-to-reinforcement-path"
                  @click="switchToReinforcementPath"
                >
                  {{ t('problemDetail.switchToReinforcementPath') }}
                </button>
                <router-link
                  v-if="activeReinforcementEntry.model_card_id"
                  :to="`/model-cards/${activeReinforcementEntry.model_card_id}`"
                  class="btn btn-secondary"
                >
                  {{ t('problemDetail.openModelCard') }}
                </router-link>
                <router-link to="/reviews" class="btn btn-secondary">
                  {{ t('modelCards.openReviewHub') }}
                </router-link>
              </div>
            </section>

            <section class="card current-step-section">
              <h2>{{ t('problemDetail.currentStepTitle') }}</h2>
              <div v-if="totalSteps" class="progress-overview">
                <span>{{ t('problemDetail.stepIndicator', { current: currentStepNumber, total: totalSteps }) }}</span>
                <div class="progress-track">
                  <div class="progress-fill" :style="{ width: `${progressPercent}%` }"></div>
                </div>
              </div>

              <div v-if="learningPath" class="path-structure-panel" data-testid="current-learning-path">
                <div class="path-structure-head">
                  <span class="mode-badge">{{ t('problemDetail.currentPath') }}: {{ formatLearningPathKind(learningPath.kind) }}</span>
                  <span class="candidate-status">{{ learningPath.title || t('problemDetail.unnamedPath') }}</span>
                  <span
                    v-if="learningPath.parent_path_id && learningPath.return_step_id !== null && learningPath.return_step_id !== undefined"
                    class="candidate-source"
                  >
                    {{ t('problemDetail.returnStepLabel', { step: learningPath.return_step_id + 1 }) }}
                  </span>
                </div>
                <p v-if="learningPath.branch_reason" class="section-subtitle">{{ learningPath.branch_reason }}</p>
                <div v-if="allLearningPaths.length > 1" class="path-nav-list">
                  <button
                    v-for="path in allLearningPaths"
                    :key="path.id"
                    type="button"
                    class="btn btn-secondary path-nav-button"
                    :class="{ active: path.is_active }"
                    :disabled="updatingPath"
                    data-testid="learning-path-button"
                    @click="activateLearningPathById(path.id)"
                  >
                    {{ formatLearningPathKind(path.kind) }} · {{ path.title || t('problemDetail.unnamedPath') }}
                  </button>
                </div>
                <button
                  v-if="canReturnToParent"
                  type="button"
                  class="btn btn-secondary"
                  :disabled="updatingPath"
                  data-testid="return-to-parent-path"
                  @click="returnToParentPath"
                >
                  {{ t('problemDetail.returnToParentPath') }}
                </button>
              </div>

              <div v-if="currentStep" class="step-card">
                <div class="step-number">{{ currentStepNumber }}</div>
                <div class="step-content">
                  <h3>{{ currentStep.concept }}</h3>
                  <p>{{ currentStep.description }}</p>
                  <ul v-if="currentStep.resources?.length" class="resources">
                    <li v-for="resource in currentStep.resources" :key="resource">{{ resource }}</li>
                  </ul>
                </div>
              </div>
              <div v-else-if="isPathCompleted && totalSteps" class="completion-banner">
                {{ t('problemDetail.completedAll') }}
              </div>
              <p v-else class="empty">{{ t('problemDetail.noLearningPath') }}</p>

              <div v-if="totalSteps" class="path-actions">
                <button
                  type="button"
                  class="btn btn-secondary"
                  :disabled="updatingPath || completedSteps === 0"
                  @click="updateCurrentStep(completedSteps - 1)"
                >
                  {{ t('problemDetail.previousStep') }}
                </button>
                <button
                  v-if="!isPathCompleted"
                  type="button"
                  class="btn btn-primary"
                  :disabled="updatingPath"
                  data-testid="mark-step-done"
                  @click="updateCurrentStep(completedSteps + 1)"
                >
                  {{ t('problemDetail.markStepDone') }}
                </button>
                <span v-else class="completed-badge">{{ t('problemDetail.completed') }}</span>
              </div>

              <details v-if="completedStepList.length" class="completed-panel">
                <summary>{{ t('problemDetail.completedStepsTitle', { count: completedStepList.length }) }}</summary>
                <div class="completed-list">
                  <div v-for="(step, index) in completedStepList" :key="`${step.concept}-${index}`" class="completed-item">
                    <span class="completed-index">{{ index + 1 }}</span>
                    <div>
                      <strong>{{ step.concept }}</strong>
                      <p>{{ step.description }}</p>
                    </div>
                  </div>
                </div>
              </details>
            </section>

            <section v-if="learningMode === 'socratic'" class="card responses-section">
              <h2>{{ t('problemDetail.progressSectionTitle') }}</h2>
              <p class="section-subtitle" v-if="currentStep">{{ t('problemDetail.progressForStep', { concept: currentStep.concept }) }}</p>

              <div v-if="socraticQuestion" class="socratic-question-panel" data-testid="socratic-question-panel">
                <div class="question-head">
                  <strong>{{ t('problemDetail.currentQuestionTitle') }}</strong>
                  <span class="question-kind-badge">{{ formatQuestionKind(socraticQuestion.question_kind) }}</span>
                </div>
                <p class="question-copy">{{ socraticQuestion.question }}</p>
              </div>

              <form @submit.prevent="submitResponse" class="response-form">
                <div class="form-group">
                  <label>{{ t('problemDetail.progressInputLabel') }}</label>
                  <textarea
                    v-model="responseText"
                    rows="5"
                    :placeholder="t('problemDetail.progressInputPlaceholder')"
                    data-testid="socratic-response-input"
                    required
                  ></textarea>
                </div>
                <div class="response-actions">
                  <button type="button" class="btn btn-secondary" :disabled="hintLoading || submitting" @click="prefillGuidedTemplate">
                    {{ hintLoading ? t('common.loading') : t('problemDetail.needPrompt') }}
                  </button>
                  <button type="submit" class="btn btn-primary" :disabled="submitting" data-testid="submit-socratic-response">
                    {{ submitting ? t('common.loading') : t('problemDetail.submitProgress') }}
                  </button>
                </div>
              </form>
              <p v-if="autoAdvanceMessage" class="auto-advance-notice">{{ autoAdvanceMessage }}</p>
              <div v-if="canUndoAutoAdvance" class="undo-auto-wrap">
                <button type="button" class="btn btn-secondary" :disabled="updatingPath" @click="undoAutoAdvance">
                  {{ t('problemDetail.undoAutoAdvance') }}
                </button>
              </div>

              <div v-if="stepHint" class="hint-panel">
                <h3>{{ t('problemDetail.hintTitle') }}</h3>
                <p v-if="stepHint.focus"><strong>{{ t('problemDetail.hintFocus') }}:</strong> {{ stepHint.focus }}</p>
                <ul v-if="stepHint.next_actions?.length">
                  <li v-for="(item, idx) in stepHint.next_actions" :key="`${idx}-${item}`">{{ item }}</li>
                </ul>
                <p v-if="stepHint.starter"><strong>{{ t('problemDetail.hintStarter') }}:</strong> {{ stepHint.starter }}</p>
              </div>

              <details v-if="responses.length" class="history-panel">
                <summary>{{ t('problemDetail.historyTitle', { count: responses.length }) }}</summary>
                <div class="responses-list">
                  <div v-for="response in responses" :key="response.id" class="response-item">
                    <div class="user-response">
                      <p class="mode-line">
                        <strong>{{ t('problemDetail.currentMode') }}:</strong> {{ formatLearningMode(response.learning_mode) }}
                      </p>
                      <p v-if="response.question_kind" class="mode-line">
                        <strong>{{ t('problemDetail.questionKind') }}:</strong> {{ formatQuestionKind(response.question_kind) }}
                      </p>
                      <p v-if="response.socratic_question" class="mode-line">
                        <strong>{{ t('problemDetail.questionLabel') }}:</strong> {{ response.socratic_question }}
                      </p>
                      <strong>{{ t('problemDetail.myProgressRecord') }}:</strong>
                      <p>{{ response.user_response }}</p>
                    </div>
                    <div v-if="response.structured_feedback" class="history-feedback">
                      <p v-if="response.structured_feedback.correctness">
                        <strong>{{ t('feedback.correctness') }}:</strong> {{ response.structured_feedback.correctness }}
                      </p>
                      <p v-if="response.structured_feedback.mastery_score !== undefined">
                        <strong>{{ t('problemDetail.masteryScore') }}:</strong> {{ response.structured_feedback.mastery_score }}
                        · <strong>{{ t('problemDetail.confidence') }}:</strong> {{ formatConfidence(response.structured_feedback.confidence) }}
                      </p>
                      <p v-if="response.structured_feedback.suggestions?.length">
                        <strong>{{ t('feedback.suggestions') }}:</strong> {{ response.structured_feedback.suggestions.join(' / ') }}
                      </p>
                      <p v-if="response.structured_feedback.next_question">
                        <strong>{{ t('feedback.nextQuestion') }}:</strong> {{ response.structured_feedback.next_question }}
                      </p>
                      <p v-if="response.accepted_concepts?.length">
                        <strong>{{ t('problemDetail.newConceptsTitle') }}:</strong> {{ response.accepted_concepts.join(' / ') }}
                      </p>
                      <p v-if="response.pending_concepts?.length">
                        <strong>{{ t('problemDetail.pendingConceptsTitle') }}:</strong> {{ response.pending_concepts.join(' / ') }}
                      </p>
                      <p v-if="response.trace_id || response.llm_calls !== undefined" class="ops-meta-line">
                        <strong>{{ t('problemDetail.traceId') }}:</strong> {{ response.trace_id || '-' }}
                        · <strong>{{ t('problemDetail.llmCalls') }}:</strong> {{ response.llm_calls ?? '-' }}
                        · <strong>{{ t('problemDetail.llmLatencyMs') }}:</strong> {{ response.llm_latency_ms ?? '-' }}
                      </p>
                    </div>
                  </div>
                </div>
              </details>
              <p v-else class="empty">{{ t('problemDetail.noProgressRecords') }}</p>
            </section>

            <section v-else class="card qa-section">
              <h2>{{ t('problemDetail.askTitle') }}</h2>
              <p class="section-subtitle">{{ t('problemDetail.askSubtitle') }}</p>

              <div class="ask-mode-toggle">
                <button
                  type="button"
                  class="btn btn-secondary"
                  :class="{ active: answerMode === 'direct' }"
                  :disabled="askingQuestion"
                  data-testid="exploration-answer-mode-direct"
                  @click="answerMode = 'direct'"
                >
                  {{ t('problemDetail.askModeDirect') }}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  :class="{ active: answerMode === 'guided' }"
                  :disabled="askingQuestion"
                  data-testid="exploration-answer-mode-guided"
                  @click="answerMode = 'guided'"
                >
                  {{ t('problemDetail.askModeGuided') }}
                </button>
              </div>

              <form @submit.prevent="askLearningQuestion" class="response-form">
                <div class="form-group">
                  <label>{{ t('problemDetail.askInputLabel') }}</label>
                  <textarea
                    v-model="learningQuestion"
                    rows="3"
                    :placeholder="t('problemDetail.askInputPlaceholder')"
                    data-testid="exploration-question-input"
                    required
                  ></textarea>
                </div>
                <button type="submit" class="btn btn-primary" :disabled="askingQuestion || !learningQuestion.trim()" data-testid="submit-exploration-question">
                  {{ askingQuestion ? t('common.loading') : t('problemDetail.askSubmit') }}
                </button>
              </form>

              <details v-if="qaHistory.length" class="history-panel">
                <summary>{{ t('problemDetail.qaHistoryTitle', { count: qaHistory.length }) }}</summary>
                <div class="responses-list">
                  <div v-for="(item, index) in qaHistory" :key="`${index}-${item.question}`" class="response-item">
                    <p class="mode-line">
                      <strong>{{ t('problemDetail.currentMode') }}:</strong> {{ formatLearningMode(item.learning_mode) }}
                    </p>
                    <p v-if="item.answer_type" class="mode-line">
                      <strong>{{ t('problemDetail.answerType') }}:</strong> {{ formatAnswerType(item.answer_type) }}
                    </p>
                    <div class="qa-block">
                      <strong>{{ t('problemDetail.questionLabel') }}</strong>
                      <p>{{ item.question }}</p>
                    </div>
                    <div class="qa-block">
                      <strong>{{ t('problemDetail.answerLabel') }}</strong>
                      <p>{{ item.answer }}</p>
                    </div>
                  </div>
                </div>
              </details>
            </section>
          </div>

          <aside class="workspace-side-column workspace-side-stack">
            <ProblemTurnOutcomePanel
              :learning-mode="learningMode"
              :latest-response="latestResponse"
              :latest-feedback="latestFeedback"
              :latest-qa="latestQA"
            />
            <ProblemDerivedConceptsPanel
              :candidates="conceptCandidates"
              :loading="candidateLoading"
              :current-turn-id="activeConceptTurnId"
              :focus-candidate-id="reinforcementFocusCandidateId"
              :focus-turn-id="reinforcementFocusTurnId"
              :focus-concept-text="activeReinforcementTarget?.concept_text || null"
              :merge-targets="conceptMergeTargets"
              :action-pending-id="candidateSubmittingId"
              :handoff-pending-id="handoffSubmittingId"
              :scheduled-model-card-ids="scheduledModelCardIds"
              :scheduled-reviews-by-model-card-id="scheduledReviewsByModelCardId"
              @accept="acceptCandidate"
              @reject="rejectCandidate"
              @postpone="postponeCandidate"
              @merge="mergeCandidate"
              @rollback="rollbackConcept"
              @promote="promoteCandidateToModelCard"
              @open-card="openModelCard"
              @schedule-review="scheduleCandidateReview"
            />
            <ProblemDerivedPathsPanel
              :candidates="pathCandidates"
              :loading="pathCandidateLoading"
              :submitting-id="pathCandidateSubmittingId"
              @decide="handlePathCandidateDecision"
            />
            <ProblemWorkspaceNotesPanel
              :notes="workspaceNotes"
              :saving="noteSaving"
              :current-turn-id="activeConceptTurnId"
              @save="saveWorkspaceNote"
              @delete="deleteWorkspaceNote"
            />
            <ProblemWorkspaceResourcesPanel
              :resources="workspaceResources"
              :saving="resourceSaving"
              :interpreting-id="resourceInterpretingId"
              :current-turn-id="activeConceptTurnId"
              @save="saveWorkspaceResource"
              @delete="deleteWorkspaceResource"
              @interpret="interpretWorkspaceResource"
            />
          </aside>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useI18n } from 'vue-i18n'
import ProblemTurnOutcomePanel from '@/components/problem-workspace/ProblemTurnOutcomePanel.vue'
import ProblemDerivedConceptsPanel from '@/components/problem-workspace/ProblemDerivedConceptsPanel.vue'
import ProblemDerivedPathsPanel from '@/components/problem-workspace/ProblemDerivedPathsPanel.vue'
import ProblemWorkspaceNotesPanel from '@/components/problem-workspace/ProblemWorkspaceNotesPanel.vue'
import ProblemWorkspaceResourcesPanel from '@/components/problem-workspace/ProblemWorkspaceResourcesPanel.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const problem = ref<any>(null)
const learningPath = ref<any>(null)
const allLearningPaths = ref<any[]>([])
const responses = ref<any[]>([])
const learningMode = ref<'socratic' | 'exploration'>('socratic')
const loading = ref(true)
const submitting = ref(false)
const updatingPath = ref(false)
const switchingMode = ref(false)
const hintLoading = ref(false)
const responseText = ref('')
const autoAdvanceMessage = ref('')
const canUndoAutoAdvance = ref(false)
const undoTargetStep = ref<number | null>(null)
const stepHint = ref<any | null>(null)
const socraticQuestion = ref<any | null>(null)
const learningQuestion = ref('')
const askingQuestion = ref(false)
const answerMode = ref<'direct' | 'guided'>('direct')
const qaHistory = ref<any[]>([])
const conceptCandidates = ref<any[]>([])
const pathCandidates = ref<any[]>([])
const candidateLoading = ref(false)
const candidateSubmittingId = ref<string | null>(null)
const handoffSubmittingId = ref<string | null>(null)
const pathCandidateLoading = ref(false)
const pathCandidateSubmittingId = ref<string | null>(null)
const scheduledModelCardIds = ref<string[]>([])
const scheduledReviews = ref<any[]>([])
const workspaceNotes = ref<any[]>([])
const noteSaving = ref(false)
const workspaceResources = ref<any[]>([])
const resourceSaving = ref(false)
const resourceInterpretingId = ref<string | null>(null)
const latestQA = computed(() => qaHistory.value[0] || null)

const totalSteps = computed(() => learningPath.value?.path_data?.length || 0)
const completedSteps = computed(() => learningPath.value?.current_step || 0)
const isPathCompleted = computed(() => totalSteps.value > 0 && completedSteps.value >= totalSteps.value)
const canReturnToParent = computed(() => Boolean(learningPath.value?.parent_path_id))
const currentStep = computed(() => {
  if (!learningPath.value?.path_data?.length || isPathCompleted.value) return null
  return learningPath.value.path_data[completedSteps.value] || null
})
const currentStepNumber = computed(() => {
  if (isPathCompleted.value) return totalSteps.value
  return Math.min(completedSteps.value + 1, totalSteps.value || 1)
})
const progressPercent = computed(() => {
  if (!totalSteps.value) return 0
  return Math.round((completedSteps.value / totalSteps.value) * 100)
})
const completedStepList = computed(() => (learningPath.value?.path_data || []).slice(0, completedSteps.value))
const latestResponse = computed(() => responses.value[responses.value.length - 1] || null)
const latestFeedback = computed(() => latestResponse.value?.structured_feedback || null)
const activeConceptTurnId = computed(() => {
  if (learningMode.value === 'exploration') {
    return latestQA.value?.turn_id || null
  }
  return latestResponse.value?.turn_id || null
})
const latestPathArtifacts = computed(() => {
  if (learningMode.value === 'exploration') {
    return latestQA.value?.derived_path_candidates?.length
      ? latestQA.value.derived_path_candidates
      : (latestQA.value?.path_suggestions || [])
  }
  return latestResponse.value?.derived_path_candidates || []
})
const latestDerivedConceptCount = computed(() => {
  if (learningMode.value === 'exploration') {
    return (latestQA.value?.accepted_concepts?.length || 0) + (latestQA.value?.pending_concepts?.length || 0)
  }
  return (latestResponse.value?.accepted_concepts?.length || 0) + (latestResponse.value?.pending_concepts?.length || 0)
})
const workspaceFocusTitle = computed(() => {
  if (currentStep.value?.concept) return currentStep.value.concept
  if (isPathCompleted.value) return t('problemDetail.completed')
  return problem.value?.title || t('problemDetail.title')
})
const workspaceFocusDescription = computed(() => {
  if (currentStep.value?.description) return currentStep.value.description
  if (isPathCompleted.value) return t('problemDetail.completedAll')
  return t('problemDetail.noLearningPath')
})
const workspacePathSummary = computed(() => {
  if (!learningPath.value) return t('problemDetail.noLearningPath')
  const label = `${formatLearningPathKind(learningPath.value.kind)} · ${learningPath.value.title || t('problemDetail.unnamedPath')}`
  if (!totalSteps.value) return label
  return `${label} · ${t('problemDetail.stepIndicator', { current: currentStepNumber.value, total: totalSteps.value })}`
})
const workspaceTurnSummary = computed(() => {
  if (!latestResponse.value && !latestQA.value) {
    return t('problemDetail.workspaceTurnEmpty')
  }
  if (!latestDerivedConceptCount.value && !latestPathArtifacts.value.length && latestFeedback.value?.mastery_score !== undefined) {
    return t('problemDetail.workspaceTurnMastery', { score: latestFeedback.value.mastery_score })
  }
  if (!latestDerivedConceptCount.value && !latestPathArtifacts.value.length) {
    return t('problemDetail.workspaceTurnEmpty')
  }
  return t('problemDetail.workspaceTurnSummary', {
    concepts: latestDerivedConceptCount.value,
    paths: latestPathArtifacts.value.length,
  })
})
const workspaceNextAction = computed(() => {
  const recallEntry = recallPriorityReviewEntry.value
  const recallConceptLabel = recallEntry?.origin?.concept_text || recallEntry?.title || t('problemDetail.derivedConceptsTitle')
  if (recallEntry?.recommended_action === 'revisit_workspace') {
    return t('problemDetail.workspaceNextReviewRevisit', { concept: recallConceptLabel })
  }
  if (recallEntry?.recommended_action === 'reinforce_soon') {
    return t('problemDetail.workspaceNextReviewReinforce', { concept: recallConceptLabel })
  }
  if (recallEntry?.recommended_action === 'extend_or_compare' && pendingPathFollowUpCount.value) {
    return t('problemDetail.workspaceNextReviewExtend', { concept: recallConceptLabel })
  }
  if (learningMode.value === 'exploration') {
    return latestQA.value?.next_learning_actions?.[0]
      || latestQA.value?.suggested_next_focus
      || t('problemDetail.workspaceNextExplorationDefault')
  }
  return latestResponse.value?.follow_up?.question
    || socraticQuestion.value?.question
    || t('problemDetail.workspaceNextSocraticDefault')
})
const conceptMergeTargets = computed(() => {
  const values = [
    ...(problem.value?.associated_concepts || []),
    ...conceptCandidates.value
      .filter((candidate) => ['accepted', 'merged'].includes(candidate.status))
      .map((candidate) => candidate.merged_into_concept || candidate.concept_text),
  ]
  const seen = new Set<string>()
  return values.filter((item) => {
    const key = String(item || '').trim().toLowerCase()
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
})
const scheduledReviewsByModelCardId = computed(() => {
  return Object.fromEntries(
    scheduledReviews.value.map((schedule: any) => [String(schedule.model_card_id), schedule])
  )
})
const routeFocusModelCardId = computed(() => String(route.query.focus_model_card || ''))
const routeFocusCandidateId = computed(() => String(route.query.focus_candidate || ''))
const routeFocusTurnId = computed(() => String(route.query.focus_turn || ''))
const problemReviewEntries = computed(() => {
  const problemId = String(route.params.id || '')
  return [...scheduledReviews.value]
    .filter((schedule: any) => String(schedule.origin?.problem_id || '') === problemId)
    .sort((left: any, right: any) => String(left.next_review_at || '').localeCompare(String(right.next_review_at || '')))
})
const currentTurnReviewEntries = computed(() => {
  if (!activeConceptTurnId.value) return []
  return problemReviewEntries.value.filter(
    (schedule: any) => String(schedule.origin?.source_turn_id || '') === String(activeConceptTurnId.value)
  )
})
const reinforcementReviewEntries = computed(() => {
  return [...problemReviewEntries.value]
    .filter((schedule: any) => Boolean(schedule.needs_reinforcement))
    .sort((left: any, right: any) => {
      const leftDate = String(left.last_reviewed_at || left.next_review_at || '')
      const rightDate = String(right.last_reviewed_at || right.next_review_at || '')
      return rightDate.localeCompare(leftDate)
    })
})
const activeReinforcementEntry = computed(() => {
  const routeFocusedEntry = reinforcementReviewEntries.value.find((schedule: any) => {
    if (routeFocusModelCardId.value && String(schedule.model_card_id || '') === routeFocusModelCardId.value) return true
    if (routeFocusCandidateId.value && String(schedule.reinforcement_target?.concept_candidate_id || schedule.origin?.concept_candidate_id || '') === routeFocusCandidateId.value) return true
    if (routeFocusTurnId.value && String(schedule.reinforcement_target?.source_turn_id || schedule.origin?.source_turn_id || '') === routeFocusTurnId.value) return true
    return false
  })
  if (routeFocusedEntry) return routeFocusedEntry
  return currentTurnReviewEntries.value.find((schedule: any) => Boolean(schedule.needs_reinforcement))
    || reinforcementReviewEntries.value[0]
    || null
})
const activeReinforcementTarget = computed(() => activeReinforcementEntry.value?.reinforcement_target || null)
const reinforcementFocusCandidateId = computed(() => {
  const value = routeFocusCandidateId.value || String(activeReinforcementTarget.value?.concept_candidate_id || '')
  return value || null
})
const reinforcementFocusTurnId = computed(() => {
  const value = routeFocusTurnId.value || String(activeReinforcementTarget.value?.source_turn_id || '')
  return value || null
})
const reinforcementTargetPathId = computed(() => String(activeReinforcementTarget.value?.resume_path_id || ''))
const canSwitchToReinforcementPath = computed(() => {
  return Boolean(
    reinforcementTargetPathId.value
      && String(learningPath.value?.id || '') !== reinforcementTargetPathId.value
      && allLearningPaths.value.some((path: any) => String(path.id) === reinforcementTargetPathId.value)
  )
})
const latestProblemReviewEntry = computed(() => problemReviewEntries.value[0] || null)
const latestReviewedProblemEntry = computed(() => {
  return [...problemReviewEntries.value]
    .filter((schedule: any) => Boolean(schedule.last_reviewed_at))
    .sort((left: any, right: any) => String(right.last_reviewed_at || '').localeCompare(String(left.last_reviewed_at || '')))[0] || null
})
const recallPriorityReviewEntry = computed(() => {
  const reviewedEntries = [...problemReviewEntries.value]
    .filter((schedule: any) => Boolean(schedule.last_reviewed_at))
    .sort((left: any, right: any) => String(right.last_reviewed_at || '').localeCompare(String(left.last_reviewed_at || '')))
  return reviewedEntries.find((schedule: any) => ['fragile', 'rebuilding'].includes(schedule.recall_state))
    || reviewedEntries[0]
    || latestProblemReviewEntry.value
})
const pendingPathFollowUpCount = computed(() => {
  return pathCandidates.value.filter((candidate) => ['planned', 'bookmarked'].includes(candidate.status)).length
})
const workspaceReviewSummary = computed(() => {
  if (!problemReviewEntries.value.length) {
    return t('problemDetail.workspaceReviewEmpty')
  }
  if (recallPriorityReviewEntry.value?.recall_state === 'fragile') {
    return t('problemDetail.workspaceReviewFragile', { count: problemReviewEntries.value.length })
  }
  if (recallPriorityReviewEntry.value?.recall_state === 'rebuilding') {
    return t('problemDetail.workspaceReviewRebuilding', { count: problemReviewEntries.value.length })
  }
  if (latestReviewedProblemEntry.value?.recall_state === 'stable') {
    return t('problemDetail.workspaceReviewStable', { count: problemReviewEntries.value.length })
  }
  if (currentTurnReviewEntries.value.length) {
    return t('problemDetail.workspaceReviewCurrentTurn', { count: currentTurnReviewEntries.value.length })
  }
  return t('problemDetail.workspaceReviewScheduled', { count: problemReviewEntries.value.length })
})
const workspaceReviewDescription = computed(() => {
  const latest = recallPriorityReviewEntry.value
  if (!latest) {
    if (pendingPathFollowUpCount.value) {
      return t('problemDetail.workspaceReviewPathsPending', { count: pendingPathFollowUpCount.value })
    }
    return t('problemDetail.workspaceReviewEmptyHint')
  }

  const conceptLabel = latest.origin?.concept_text || latest.title || t('problemDetail.derivedConceptsTitle')
  if (latest.last_reviewed_at) {
    return t('problemDetail.workspaceReviewOutcome', {
      concept: conceptLabel,
      state: formatRecallState(latest.recall_state),
      action: formatRecommendedAction(latest.recommended_action),
      date: formatDateTime(latest.last_reviewed_at),
    })
  }
  return t('problemDetail.workspaceReviewNextRecall', {
    concept: conceptLabel,
    date: formatDateTime(latest.next_review_at),
  })
})
type ReinforcementActionTemplate = {
  key: string
  preferredMode: 'socratic' | 'exploration'
  title: string
  description: string
  starter: string
  sourceCue?: string
  sourceClue?: string
  likelyConfusion?: string
  evidenceCue?: string
}
type ReinforcementStarterContext = {
  questionCue: string
  answerCue: string
  comparisonCue: string
  primaryCue: string
}
type ReinforcementErrorHint = {
  kind: 'comparison' | 'boundary' | 'misconception'
  text: string
}

const normalizeInlineText = (value: unknown) => String(value ?? '').replace(/\s+/g, ' ').trim()

const clipInlineText = (value: string, max = 96) => {
  const normalized = normalizeInlineText(value)
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, Math.max(0, max - 1)).trimEnd()}…`
}

const stripTrailingPunctuation = (value: string) => normalizeInlineText(value).replace(/[.?!,:;]+$/g, '').trim()
const stripQuestionLead = (value: string) => normalizeInlineText(value).replace(
  /^(what is|what's|what are|how should i|how do i|how can i|why does|why do|why is|when should i|when does|can you explain|could you explain|explain|tell me about|is it true that|is|are)\s+/i,
  '',
)
const isQuestionLike = (value: string) => /\?$/.test(normalizeInlineText(value))

const uniqueContextConcepts = (values: unknown[], exclude: string[] = []) => {
  const excluded = new Set(exclude.map((value) => normalizeInlineText(value).toLowerCase()).filter(Boolean))
  const seen = new Set<string>()
  return values
    .map((value) => normalizeInlineText(value))
    .filter((value) => {
      const normalized = value.toLowerCase()
      if (!value || excluded.has(normalized) || seen.has(normalized)) return false
      seen.add(normalized)
      return true
    })
}

const extractQuestionCue = (question: string, answerType: string, contextConcepts: string[]) => {
  const normalized = normalizeInlineText(question)
  if (!normalized) return ''

  if (answerType === 'comparison') {
    const betweenMatch = normalized.match(/\bdifference between\s+(.+?)\s+and\s+(.+?)(?:[?.!,]|$)/i)
    if (betweenMatch) {
      return clipInlineText(`${stripTrailingPunctuation(betweenMatch[1])} vs ${stripTrailingPunctuation(betweenMatch[2])}`)
    }
    const compareMatch = normalized.match(/\bcompare\s+(.+?)(?:[?.!,]|$)/i)
    if (compareMatch) {
      return clipInlineText(stripTrailingPunctuation(compareMatch[1]))
    }
    const versusMatch = normalized.match(/\b(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:[?.!,]|$)/i)
    if (versusMatch) {
      return clipInlineText(`${stripTrailingPunctuation(versusMatch[1])} vs ${stripTrailingPunctuation(versusMatch[2])}`)
    }
    if (contextConcepts.length >= 2) {
      return clipInlineText(`${contextConcepts[0]} vs ${contextConcepts[1]}`)
    }
  }

  const stripped = stripQuestionLead(normalized)
  return clipInlineText(stripTrailingPunctuation(stripped || normalized))
}

const extractAnswerCue = (answer: string) => {
  const sentences = normalizeInlineText(answer)
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => clipInlineText(sentence, 120))
    .filter(Boolean)
  if (!sentences.length) return ''
  const preferred = sentences.find((sentence) => /example|because|instead|raises|lowers|depends|tradeoff|boundary|fails|applies/i.test(sentence))
  return preferred || sentences[0]
}

const isLowSignalAnswerCue = (value: string) => {
  const normalized = normalizeInlineText(value).toLowerCase()
  return !normalized || /start from the current step concept|define it briefly|test it with one concrete example/.test(normalized)
}

const extractSentenceWithPattern = (value: string, pattern: RegExp) => {
  const sentence = normalizeInlineText(value)
    .split(/(?<=[.!?])\s+/)
    .find((item) => pattern.test(item))
  return sentence ? clipInlineText(sentence, 120) : ''
}

const splitEvidenceChunks = (value: string) => {
  const normalized = String(value || '').trim()
  if (!normalized) return []

  const chunks = normalized
    .split(/\n+/)
    .flatMap((line) => normalizeInlineText(line).split(/(?<=[.!?])\s+/))
    .map((chunk) => clipInlineText(chunk, 140))
    .filter(Boolean)

  return uniqueContextConcepts(chunks)
}

const extractBoundaryCue = (question: string, answer: string) => {
  const explicitQuestionCue = extractSentenceWithPattern(question, /\b(always|never|only|every|all|whenever|must|cannot|can't)\b/i)
  if (explicitQuestionCue) return stripTrailingPunctuation(explicitQuestionCue)
  const explicitAnswerCue = extractSentenceWithPattern(answer, /\b(always|never|only|every|all|whenever|must|cannot|can't|fails|breaks|edge case)\b/i)
  if (explicitAnswerCue) return stripTrailingPunctuation(explicitAnswerCue)
  return ''
}

const extractMisconceptionCue = (question: string, answer: string) => {
  const normalizedQuestion = normalizeInlineText(question)
  if (/\b(same as|equivalent to|means|just|only|always|never)\b/i.test(normalizedQuestion)) {
    return clipInlineText(stripTrailingPunctuation(stripQuestionLead(normalizedQuestion)), 110)
  }

  const correctiveSentence = extractSentenceWithPattern(answer, /\bnot\b.+\bbut\b|\brather than\b|\binstead of\b/i)
  if (correctiveSentence) return stripTrailingPunctuation(correctiveSentence)

  return ''
}

const deriveReinforcementErrorHint = ({
  answerType,
  question,
  answer,
  questionCue,
  comparisonCue,
}: {
  answerType: string
  question: string
  answer: string
  questionCue: string
  comparisonCue: string
}): ReinforcementErrorHint | null => {
  if (answerType === 'comparison' && /\b(compare|difference between|vs\.?|versus)\b/i.test(question)) {
    const cue = comparisonCue || questionCue
    if (!cue) return null
    return {
      kind: 'comparison',
      text: t('problemDetail.reinforcementComparisonLikelyConfusion', { cue }),
    }
  }

  if (answerType === 'boundary_clarification') {
    const cue = extractBoundaryCue(question, answer)
    if (!cue) return null
    return {
      kind: 'boundary',
      text: t('problemDetail.reinforcementBoundaryLikelyConfusion', { cue }),
    }
  }

  if (answerType === 'misconception_correction') {
    const cue = extractMisconceptionCue(question, answer)
    if (!cue) return null
    return {
      kind: 'misconception',
      text: t('problemDetail.reinforcementMisconceptionLikelyConfusion', { cue }),
    }
  }

  return null
}

const extractEvidenceCue = ({
  evidenceSnippet,
  concept,
  sourceCue,
  sourceClue,
  likelyConfusion,
  anchor,
}: {
  evidenceSnippet: string
  concept: string
  sourceCue: string
  sourceClue: string
  likelyConfusion: string
  anchor: string
}) => {
  const conceptKey = normalizeInlineText(concept).toLowerCase()
  const anchorKey = normalizeInlineText(anchor).toLowerCase()
  const seen = new Set<string>()
  const chunks = splitEvidenceChunks(evidenceSnippet).filter((chunk) => {
    const normalized = normalizeInlineText(chunk)
    const key = normalized.toLowerCase()
    if (!normalized || seen.has(key)) return false
    seen.add(key)
    if (isLowSignalAnswerCue(normalized)) return false
    if (key === normalizeInlineText(sourceCue).toLowerCase()) return false
    if (key === normalizeInlineText(sourceClue).toLowerCase()) return false
    if (key === normalizeInlineText(likelyConfusion).toLowerCase()) return false
    if (key === conceptKey || key === anchorKey) return false
    return true
  })

  if (!chunks.length) return ''

  const statementChunks = chunks.filter((chunk) => !isQuestionLike(chunk))
  const candidates = statementChunks.length ? statementChunks : chunks

  const conceptSpecific = candidates.find((chunk) => conceptKey && chunk.toLowerCase().includes(conceptKey))
  if (conceptSpecific) return conceptSpecific

  const evidenceSpecific = candidates.find((chunk) => /because|raises|lowers|drop|drops|rise|rises|tradeoff|instead|rather than|not|but|applies|fails|edge case|example|predicted positives|actual positives|false positives|false negatives/i.test(chunk))
  if (evidenceSpecific) return evidenceSpecific

  return ''
}

const buildEvidenceAwareStarter = (starter: string, evidenceCue: string) => {
  if (!evidenceCue) return starter
  return `${t('problemDetail.reinforcementStarterEvidencePrefix', { evidence: evidenceCue })}\n${starter}`
}
const focusedReinforcementCandidate = computed(() => {
  if (reinforcementFocusCandidateId.value) {
    const exactCandidate = conceptCandidates.value.find(
      (candidate: any) => String(candidate.id || '') === String(reinforcementFocusCandidateId.value)
    )
    if (exactCandidate) return exactCandidate
  }

  if (reinforcementFocusTurnId.value) {
    const turnMatches = conceptCandidates.value.filter(
      (candidate: any) => String(candidate.source_turn_id || '') === String(reinforcementFocusTurnId.value)
    )
    if (turnMatches.length === 1) return turnMatches[0]

    const targetConcept = String(activeReinforcementTarget.value?.concept_text || '').trim().toLowerCase()
    const conceptMatch = turnMatches.find(
      (candidate: any) => String(candidate.concept_text || '').trim().toLowerCase() === targetConcept
    )
    if (conceptMatch) return conceptMatch
    if (turnMatches.length) return turnMatches[0]
  }

  return null
})
const focusedReinforcementTurn = computed(() => {
  if (!reinforcementFocusTurnId.value) return null
  return qaHistory.value.find((turn: any) => String(turn.turn_id || '') === String(reinforcementFocusTurnId.value)) || null
})
const reinforcementFocusTitle = computed(() => {
  return focusedReinforcementCandidate.value?.concept_text
    || activeReinforcementTarget.value?.concept_text
    || t('problemDetail.derivedConceptsTitle')
})
const reinforcementFocusDescription = computed(() => {
  if (focusedReinforcementCandidate.value) {
    return t('problemDetail.reinforcementFocusCandidate', {
      status: formatCandidateStatus(focusedReinforcementCandidate.value.status),
      source: formatCandidateSource(focusedReinforcementCandidate.value.source),
    })
  }
  if (focusedReinforcementTurn.value?.answer_type) {
    return t('problemDetail.reinforcementFocusTurn', {
      answerType: formatAnswerType(focusedReinforcementTurn.value.answer_type),
    })
  }
  return t('problemDetail.reinforcementFocusFallback')
})
const reinforcementFocusTurnPreview = computed(() => {
  if (focusedReinforcementCandidate.value?.source_turn_preview) {
    return focusedReinforcementCandidate.value.source_turn_preview
  }
  if (activeReinforcementTarget.value?.source_turn_preview) {
    return activeReinforcementTarget.value.source_turn_preview
  }
  if (!focusedReinforcementTurn.value) return ''
  const question = String(focusedReinforcementTurn.value.question || '').trim()
  const answer = String(focusedReinforcementTurn.value.answer || '').trim()
  if (question && answer) return `${question.slice(0, 110)} -> ${answer.slice(0, 110)}`
  return question || answer
})
const reinforcementStarterContext = computed<ReinforcementStarterContext>(() => {
  const concept = reinforcementFocusTitle.value
  const sourceQuestion = normalizeInlineText(focusedReinforcementTurn.value?.question || '')
  const sourceAnswer = normalizeInlineText(focusedReinforcementTurn.value?.answer || '')
  const answerType = String(focusedReinforcementTurn.value?.answer_type || '').trim()
  const contextConcepts = uniqueContextConcepts([
    ...(focusedReinforcementTurn.value?.answered_concepts || []),
    ...(focusedReinforcementTurn.value?.related_concepts || []),
    focusedReinforcementTurn.value?.suggested_next_focus,
    focusedReinforcementTurn.value?.step_concept,
    activeReinforcementTarget.value?.resume_step_concept,
    currentStep.value?.concept,
    problem.value?.title,
  ], [concept])
  const questionCue = extractQuestionCue(sourceQuestion, answerType, contextConcepts)
  const answerCue = extractAnswerCue(sourceAnswer)
  const comparisonCue = answerType === 'comparison'
    ? questionCue || clipInlineText(contextConcepts.slice(0, 2).join(' vs '))
    : ''
  const primaryCue = questionCue
    || clipInlineText(reinforcementFocusTurnPreview.value, 110)
    || answerCue
    || clipInlineText(contextConcepts.join(', '), 90)

  return {
    questionCue,
    answerCue,
    comparisonCue,
    primaryCue,
  }
})
const reinforcementErrorHint = computed<ReinforcementErrorHint | null>(() => {
  if (!focusedReinforcementTurn.value) return null
  return deriveReinforcementErrorHint({
    answerType: String(focusedReinforcementTurn.value.answer_type || '').trim(),
    question: normalizeInlineText(focusedReinforcementTurn.value.question || ''),
    answer: normalizeInlineText(focusedReinforcementTurn.value.answer || ''),
    questionCue: reinforcementStarterContext.value.questionCue,
    comparisonCue: reinforcementStarterContext.value.comparisonCue,
  })
})
const reinforcementEvidenceCue = computed(() => {
  const evidenceSnippet = String(
    focusedReinforcementCandidate.value?.evidence_snippet
      || activeReinforcementEntry.value?.origin?.evidence_snippet
      || '',
  ).trim()
  if (!evidenceSnippet) return ''

  const concept = reinforcementFocusTitle.value
  const anchor = String(
    activeReinforcementTarget.value?.resume_step_concept
      || currentStep.value?.concept
      || problem.value?.title
      || concept
  ).trim()

  return extractEvidenceCue({
    evidenceSnippet,
    concept,
    sourceCue: reinforcementStarterContext.value.primaryCue,
    sourceClue: reinforcementStarterContext.value.answerCue,
    likelyConfusion: reinforcementErrorHint.value?.text || '',
    anchor,
  })
})
const reinforcementActionTemplate = computed<ReinforcementActionTemplate | null>(() => {
  if (!activeReinforcementEntry.value || !activeReinforcementTarget.value) return null

  const concept = reinforcementFocusTitle.value
  const anchor = String(
    activeReinforcementTarget.value?.resume_step_concept
      || currentStep.value?.concept
      || problem.value?.title
      || concept
  ).trim()
  const answerType = String(focusedReinforcementTurn.value?.answer_type || '').trim()
  const originMode = String(activeReinforcementEntry.value?.origin?.learning_mode || learningMode.value || 'socratic').trim()
  const sourceCue = reinforcementStarterContext.value.primaryCue
  const sourceClue = !isLowSignalAnswerCue(reinforcementStarterContext.value.answerCue)
    && reinforcementStarterContext.value.answerCue
    && reinforcementStarterContext.value.answerCue !== sourceCue
      ? reinforcementStarterContext.value.answerCue
      : ''
  const likelyConfusion = reinforcementErrorHint.value?.text || ''
  const evidenceCue = reinforcementEvidenceCue.value
  const withEvidence = (starter: string) => buildEvidenceAwareStarter(starter, evidenceCue)

  if (answerType === 'comparison' || activeReinforcementTarget.value?.resume_path_kind === 'comparison') {
    const comparisonCue = reinforcementStarterContext.value.comparisonCue || sourceCue
    return {
      key: 'compare',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateCompareTitle'),
      description: t('problemDetail.reinforcementTemplateCompareBody', { concept, anchor }),
      starter: withEvidence(likelyConfusion
        ? t('problemDetail.reinforcementTemplateCompareErrorStarter', { concept, error: likelyConfusion })
        : comparisonCue
        ? t('problemDetail.reinforcementTemplateCompareSourceStarter', { concept, cue: comparisonCue })
        : t('problemDetail.reinforcementTemplateCompareStarter', { concept, anchor })),
      sourceCue: comparisonCue || sourceCue,
      sourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (answerType === 'misconception_correction') {
    return {
      key: 'correct',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateCorrectTitle'),
      description: t('problemDetail.reinforcementTemplateCorrectBody', { concept, anchor }),
      starter: withEvidence(likelyConfusion
        ? t('problemDetail.reinforcementTemplateCorrectErrorStarter', { concept, error: likelyConfusion })
        : sourceCue
        ? t('problemDetail.reinforcementTemplateCorrectSourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplateCorrectStarter', { concept, anchor })),
      sourceCue,
      sourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (answerType === 'worked_example') {
    return {
      key: 'example',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateExampleTitle'),
      description: t('problemDetail.reinforcementTemplateExampleBody', { concept, anchor }),
      starter: withEvidence(sourceCue
        ? t('problemDetail.reinforcementTemplateExampleSourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplateExampleStarter', { concept, anchor })),
      sourceCue,
      sourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (answerType === 'boundary_clarification') {
    return {
      key: 'boundary',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateBoundaryTitle'),
      description: t('problemDetail.reinforcementTemplateBoundaryBody', { concept, anchor }),
      starter: withEvidence(likelyConfusion
        ? t('problemDetail.reinforcementTemplateBoundaryErrorStarter', { concept, error: likelyConfusion })
        : sourceCue
        ? t('problemDetail.reinforcementTemplateBoundarySourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplateBoundaryStarter', { concept, anchor })),
      sourceCue,
      sourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (answerType === 'prerequisite_explanation') {
    return {
      key: 'prerequisite',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplatePrerequisiteTitle'),
      description: t('problemDetail.reinforcementTemplatePrerequisiteBody', { concept, anchor }),
      starter: withEvidence(sourceCue
        ? t('problemDetail.reinforcementTemplatePrerequisiteSourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplatePrerequisiteStarter', { concept, anchor })),
      sourceCue,
      sourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (originMode === 'socratic') {
    return {
      key: 'probe',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateProbeTitle'),
      description: t('problemDetail.reinforcementTemplateProbeBody', { concept, anchor }),
      starter: withEvidence(sourceCue
        ? t('problemDetail.reinforcementTemplateProbeSourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplateProbeStarter', { concept, anchor })),
      sourceCue,
      sourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  return {
    key: 'restate',
    preferredMode: 'socratic',
    title: t('problemDetail.reinforcementTemplateRestateTitle'),
    description: t('problemDetail.reinforcementTemplateRestateBody', { concept, anchor }),
    starter: withEvidence(sourceCue
      ? t('problemDetail.reinforcementTemplateRestateSourceStarter', { concept, cue: sourceCue })
      : t('problemDetail.reinforcementTemplateRestateStarter', { concept, anchor })),
    sourceCue,
    sourceClue,
    likelyConfusion,
    evidenceCue,
  }
})

const formatConfidence = (value: number | string | undefined | null) => {
  const parsed = Number(value ?? 0)
  if (!Number.isFinite(parsed)) return '0%'
  const percent = Math.round(Math.max(0, Math.min(1, parsed)) * 100)
  return `${percent}%`
}

const formatDateTime = (dateValue: string | undefined | null) => {
  if (!dateValue) return '-'
  return new Date(dateValue).toLocaleString()
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

const formatReinforcementResume = (target: any) => {
  const rawStepIndex = Number(target?.resume_step_index)
  const hasStepIndex = Number.isFinite(rawStepIndex)
  const stepNumber = hasStepIndex ? rawStepIndex + 1 : null
  const stepConcept = String(target?.resume_step_concept || '').trim()

  if (stepNumber !== null && stepConcept) {
    return t('problemDetail.reinforcementResumeStepConcept', {
      step: stepNumber,
      concept: stepConcept,
    })
  }
  if (stepNumber !== null) {
    return t('problemDetail.reinforcementResumeStepOnly', { step: stepNumber })
  }
  if (stepConcept) {
    return t('problemDetail.reinforcementResumeConcept', { concept: stepConcept })
  }
  return t('problemDetail.reinforcementResumeCurrentWorkspace')
}

const hasReinforcementPath = (target: any) => {
  return Boolean(target?.resume_path_id || target?.resume_path_kind || target?.resume_path_title)
}

const formatReinforcementPath = (target: any) => {
  const title = String(target?.resume_path_title || '').trim()
  const kind = String(target?.resume_path_kind || '').trim()
  const kindLabel = kind ? formatLearningPathKind(kind) : ''
  if (kindLabel && title) return `${kindLabel} · ${title}`
  if (title) return title
  if (kindLabel) return kindLabel
  return t('problemDetail.reinforcementResumeCurrentWorkspace')
}

const formatReinforcementSummary = (entry: any) => {
  const target = entry?.reinforcement_target || {}
  const conceptLabel = target.concept_text || entry?.origin?.concept_text || entry?.title || t('problemDetail.derivedConceptsTitle')
  return t('problemDetail.reinforcementSummary', {
    concept: conceptLabel,
    state: formatRecallState(entry?.recall_state),
    action: formatRecommendedAction(entry?.recommended_action),
  })
}

const formatLearningMode = (mode: string | undefined | null) => {
  return mode === 'exploration'
    ? t('problemDetail.modeExploration')
    : t('problemDetail.modeSocratic')
}

const formatLearningPathKind = (kind: string | undefined | null) => {
  if (kind === 'prerequisite') return t('problemDetail.pathKindPrerequisite')
  if (kind === 'comparison') return t('problemDetail.pathKindComparison')
  if (kind === 'branch') return t('problemDetail.pathKindBranch')
  return t('problemDetail.pathKindMain')
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

const normalizeExplorationTurn = (turn: any) => ({
  turn_id: turn.turn_id || turn.id || null,
  learning_mode: turn.learning_mode || 'exploration',
  mode_metadata: turn.mode_metadata || {},
  question: turn.question ?? turn.user_text ?? '',
  answer: turn.answer ?? turn.assistant_text ?? '',
  answer_mode: turn.answer_mode ?? turn.mode_metadata?.answer_mode ?? 'direct',
  answer_type: turn.answer_type ?? turn.mode_metadata?.answer_type ?? 'concept_explanation',
  answered_concepts: turn.answered_concepts ?? turn.mode_metadata?.answered_concepts ?? [],
  related_concepts: turn.related_concepts ?? turn.mode_metadata?.related_concepts ?? [],
  derived_candidates: turn.derived_candidates ?? turn.mode_metadata?.derived_candidates ?? [],
  derived_path_candidates: turn.derived_path_candidates ?? turn.mode_metadata?.derived_path_candidates ?? [],
  next_learning_actions: turn.next_learning_actions ?? turn.mode_metadata?.next_learning_actions ?? [],
  path_suggestions: turn.path_suggestions ?? turn.mode_metadata?.path_suggestions ?? [],
  return_to_main_path_hint: turn.return_to_main_path_hint ?? turn.mode_metadata?.return_to_main_path_hint ?? true,
  step_index: Number(turn.step_index ?? turn.mode_metadata?.step_index ?? 0),
  step_concept: turn.step_concept ?? turn.mode_metadata?.step_concept ?? problem.value?.title ?? '',
  suggested_next_focus: turn.suggested_next_focus ?? turn.mode_metadata?.suggested_next_focus ?? null,
  accepted_concepts: turn.accepted_concepts ?? turn.mode_metadata?.accepted_concepts ?? [],
  pending_concepts: turn.pending_concepts ?? turn.mode_metadata?.pending_concepts ?? [],
  trace_id: turn.trace_id,
  llm_calls: turn.llm_calls,
  llm_latency_ms: turn.llm_latency_ms,
  fallback_reason: turn.fallback_reason,
  created_at: turn.created_at,
})

const fetchExplorationTurns = async () => {
  try {
    const response = await api.get(`/problems/${route.params.id}/turns`, {
      params: { learning_mode: 'exploration' },
    })
    qaHistory.value = (response.data || []).map(normalizeExplorationTurn)
  } catch (e) {
    console.error('Failed to fetch exploration turns:', e)
    qaHistory.value = []
  }
}

const fetchSocraticQuestion = async () => {
  try {
    const response = await api.get(`/problems/${route.params.id}/socratic-question`)
    socraticQuestion.value = response.data || null
  } catch (e) {
    console.error('Failed to fetch socratic question:', e)
    socraticQuestion.value = null
  }
}

const fetchConceptCandidates = async () => {
  candidateLoading.value = true
  try {
    const response = await api.get(`/problems/${route.params.id}/concept-candidates`)
    conceptCandidates.value = response.data || []
  } catch (e) {
    console.error('Failed to fetch concept candidates:', e)
    conceptCandidates.value = []
  } finally {
    candidateLoading.value = false
  }
}

const fetchPathCandidates = async () => {
  pathCandidateLoading.value = true
  try {
    const response = await api.get(`/problems/${route.params.id}/path-candidates`)
    pathCandidates.value = response.data || []
  } catch (e) {
    console.error('Failed to fetch path candidates:', e)
    pathCandidates.value = []
  } finally {
    pathCandidateLoading.value = false
  }
}

const fetchReviewSchedules = async () => {
  try {
    const response = await api.get('/srs/schedules')
    scheduledReviews.value = response.data || []
    scheduledModelCardIds.value = scheduledReviews.value.map((schedule: any) => String(schedule.model_card_id))
  } catch (e) {
    console.error('Failed to fetch review schedules:', e)
    scheduledReviews.value = []
    scheduledModelCardIds.value = []
  }
}

const fetchWorkspaceNotes = async () => {
  try {
    const response = await api.get('/notes/', {
      params: {
        problem_id: route.params.id,
      },
    })
    workspaceNotes.value = response.data || []
  } catch (e) {
    console.error('Failed to fetch workspace notes:', e)
    workspaceNotes.value = []
  }
}

const fetchWorkspaceResources = async () => {
  try {
    const response = await api.get('/resources/', {
      params: {
        problem_id: route.params.id,
      },
    })
    workspaceResources.value = response.data || []
  } catch (e) {
    console.error('Failed to fetch workspace resources:', e)
    workspaceResources.value = []
  }
}

const fetchLearningPath = async () => {
  const pathRes = await api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null }))
  learningPath.value = pathRes.data
}

const fetchLearningPaths = async () => {
  const response = await api.get(`/problems/${route.params.id}/learning-paths`).catch(() => ({ data: [] }))
  allLearningPaths.value = response.data || []
}

const fetchProblem = async () => {
  try {
    const [problemRes, pathRes, pathListRes, responsesRes, candidatesRes, pathCandidatesRes, turnsRes, socraticRes, schedulesRes, notesRes, resourcesRes] = await Promise.all([
      api.get(`/problems/${route.params.id}`),
      api.get(`/problems/${route.params.id}/learning-path`).catch(() => ({ data: null })),
      api.get(`/problems/${route.params.id}/learning-paths`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/responses`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/concept-candidates`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/path-candidates`).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/turns`, {
        params: { learning_mode: 'exploration' },
      }).catch(() => ({ data: [] })),
      api.get(`/problems/${route.params.id}/socratic-question`).catch(() => ({ data: null })),
      api.get('/srs/schedules').catch(() => ({ data: [] })),
      api.get('/notes/', {
        params: { problem_id: route.params.id },
      }).catch(() => ({ data: [] })),
      api.get('/resources/', {
        params: { problem_id: route.params.id },
      }).catch(() => ({ data: [] })),
    ])

    problem.value = problemRes.data
    learningMode.value = problemRes.data?.learning_mode || 'socratic'
    learningPath.value = pathRes.data
    allLearningPaths.value = pathListRes.data || []
    responses.value = responsesRes.data
    conceptCandidates.value = candidatesRes.data || []
    pathCandidates.value = pathCandidatesRes.data || []
    qaHistory.value = (turnsRes.data || []).map(normalizeExplorationTurn)
    socraticQuestion.value = socraticRes.data || null
    scheduledReviews.value = schedulesRes.data || []
    scheduledModelCardIds.value = scheduledReviews.value.map((schedule: any) => String(schedule.model_card_id))
    workspaceNotes.value = notesRes.data || []
    workspaceResources.value = resourcesRes.data || []
  } catch (e) {
    console.error('Failed to fetch problem:', e)
  } finally {
    loading.value = false
  }
}

const setLearningMode = async (mode: 'socratic' | 'exploration') => {
  if (switchingMode.value || learningMode.value === mode) return

  const previousMode = learningMode.value
  learningMode.value = mode
  if (problem.value) {
    problem.value.learning_mode = mode
  }

  switchingMode.value = true
  try {
    await api.put(`/problems/${route.params.id}`, { learning_mode: mode })
    if (mode === 'socratic') {
      await fetchSocraticQuestion()
    }
  } catch (e) {
    console.error('Failed to switch learning mode:', e)
    learningMode.value = previousMode
    if (problem.value) {
      problem.value.learning_mode = previousMode
    }
  } finally {
    switchingMode.value = false
  }
}

const submitResponse = async () => {
  submitting.value = true

  try {
    const response = await api.post(`/problems/${route.params.id}/responses`, {
      problem_id: route.params.id,
      user_response: responseText.value,
      learning_mode: learningMode.value,
      question_kind: socraticQuestion.value?.question_kind,
      socratic_question: socraticQuestion.value?.question,
    })
    responses.value.push(response.data)
    await Promise.all([
      fetchConceptCandidates(),
      fetchPathCandidates(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
    responseText.value = ''
    if (response.data?.auto_advanced) {
      await fetchLearningPath()
      autoAdvanceMessage.value = t('problemDetail.autoAdvanced')
      canUndoAutoAdvance.value = true
      const suggestedUndo = Number(response.data?.new_current_step ?? 0) - 1
      undoTargetStep.value = Number.isFinite(suggestedUndo) ? Math.max(0, suggestedUndo) : null
      if (problem.value && problem.value.status === 'new') {
        problem.value.status = 'in-progress'
      }
    } else {
      autoAdvanceMessage.value = ''
      canUndoAutoAdvance.value = false
      undoTargetStep.value = null
    }

    if (problem.value?.status === 'new' && !response.data?.auto_advanced) {
      problem.value.status = 'in-progress'
    }
    await fetchSocraticQuestion()
  } catch (e) {
    console.error('Failed to submit response:', e)
  } finally {
    submitting.value = false
  }
}

const updateCurrentStep = async (nextStep: number) => {
  if (!learningPath.value) return

  updatingPath.value = true
  try {
    const response = await api.put(`/problems/${route.params.id}/learning-path`, {
      current_step: nextStep,
    })
    learningPath.value = response.data
    await fetchLearningPaths()
    if (learningMode.value === 'socratic') {
      await fetchSocraticQuestion()
    }

    if (problem.value) {
      if (totalSteps.value > 0 && nextStep >= totalSteps.value) {
        problem.value.status = 'completed'
      } else if (nextStep > 0) {
        problem.value.status = 'in-progress'
      } else {
        problem.value.status = 'new'
      }
    }
  } catch (e) {
    console.error('Failed to update learning path:', e)
  } finally {
    updatingPath.value = false
  }
}

const prefillGuidedTemplate = () => {
  const buildLocalGuidedTemplate = () => {
    const concept = currentStep.value?.concept || problem.value?.title || ''
    return [
      t('problemDetail.guidedLine1', { concept }),
      t('problemDetail.guidedLine2'),
      t('problemDetail.guidedLine3'),
    ].join('\n')
  }

  hintLoading.value = true
  api.get(`/problems/${route.params.id}/learning-path/hint`)
    .then((response) => {
      stepHint.value = response.data?.structured_hint || null
      const starter = response.data?.structured_hint?.starter?.trim()
      if (starter) {
        responseText.value = `${starter}\n`
      } else {
        responseText.value = response.data?.hint?.trim() || buildLocalGuidedTemplate()
      }
    })
    .catch((e) => {
      console.error('Failed to fetch learning hint:', e)
      stepHint.value = null
      responseText.value = buildLocalGuidedTemplate()
    })
    .finally(() => {
      hintLoading.value = false
    })
}

const undoAutoAdvance = async () => {
  if (!learningPath.value) return

  const fallbackTarget = Math.max((learningPath.value.current_step || 1) - 1, 0)
  const targetStep = undoTargetStep.value ?? fallbackTarget
  await updateCurrentStep(targetStep)
  autoAdvanceMessage.value = t('problemDetail.autoAdvanceUndone')
  canUndoAutoAdvance.value = false
  undoTargetStep.value = null
}

const askLearningQuestion = async () => {
  if (!learningQuestion.value.trim() || askingQuestion.value) return

  askingQuestion.value = true
  try {
    await api.post(`/problems/${route.params.id}/ask`, {
      question: learningQuestion.value.trim(),
      learning_mode: learningMode.value,
      answer_mode: answerMode.value,
    })
    await Promise.all([
      fetchConceptCandidates(),
      fetchPathCandidates(),
      fetchExplorationTurns(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
    learningQuestion.value = ''
  } catch (e) {
    console.error('Failed to ask learning question:', e)
  } finally {
    askingQuestion.value = false
  }
}

const acceptCandidate = async (candidateId: string) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/accept`)
    await Promise.all([
      fetchConceptCandidates(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
  } catch (e) {
    console.error('Failed to accept concept candidate:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const rejectCandidate = async (candidateId: string) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/reject`)
    await fetchConceptCandidates()
  } catch (e) {
    console.error('Failed to reject concept candidate:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const postponeCandidate = async (candidateId: string) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/postpone`)
    await fetchConceptCandidates()
  } catch (e) {
    console.error('Failed to postpone concept candidate:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const mergeCandidate = async ({ candidateId, targetConcept }: { candidateId: string; targetConcept: string }) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/merge`, {
      target_concept_text: targetConcept,
    })
    await Promise.all([
      fetchConceptCandidates(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
  } catch (e) {
    console.error('Failed to merge concept candidate:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const rollbackConcept = async ({ candidateId, conceptText }: { candidateId: string; conceptText: string }) => {
  candidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concepts/rollback`, {
      concept_text: conceptText,
      reason: 'Manual rollback from UI',
    })
    await Promise.all([
      fetchConceptCandidates(),
      api.get(`/problems/${route.params.id}`).then((res) => {
        problem.value = res.data
        learningMode.value = res.data?.learning_mode || learningMode.value
      }).catch(() => null),
    ])
  } catch (e) {
    console.error('Failed to rollback concept:', e)
  } finally {
    candidateSubmittingId.value = null
  }
}

const promoteCandidateToModelCard = async (candidateId: string) => {
  handoffSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/promote`)
    await fetchConceptCandidates()
  } catch (e) {
    console.error('Failed to promote concept candidate to model card:', e)
  } finally {
    handoffSubmittingId.value = null
  }
}

const openModelCard = (modelCardId: string) => {
  if (!modelCardId) return
  router.push(`/model-cards/${modelCardId}`)
}

const scheduleCandidateReview = async (candidateId: string) => {
  handoffSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/concept-candidates/${candidateId}/schedule-review`)
    await Promise.all([
      fetchReviewSchedules(),
      fetchConceptCandidates(),
    ])
  } catch (e) {
    console.error('Failed to schedule concept candidate review:', e)
  } finally {
    handoffSubmittingId.value = null
  }
}

const saveWorkspaceNote = async ({ content, tags }: { content: string; tags: string[] }) => {
  noteSaving.value = true
  try {
    await api.post('/notes/', {
      content,
      source: 'text',
      tags,
      problem_id: route.params.id,
      source_turn_id: activeConceptTurnId.value || undefined,
    })
    await fetchWorkspaceNotes()
  } catch (e) {
    console.error('Failed to save workspace note:', e)
  } finally {
    noteSaving.value = false
  }
}

const deleteWorkspaceNote = async (noteId: string) => {
  try {
    await api.delete(`/notes/${noteId}`)
    workspaceNotes.value = workspaceNotes.value.filter((note) => note.id !== noteId)
  } catch (e) {
    console.error('Failed to delete workspace note:', e)
  }
}

const saveWorkspaceResource = async ({ url, title, linkType }: { url: string; title: string; linkType: string }) => {
  resourceSaving.value = true
  try {
    await api.post('/resources/', {
      url,
      title: title || null,
      link_type: linkType,
      problem_id: route.params.id,
      source_turn_id: activeConceptTurnId.value || undefined,
    })
    await fetchWorkspaceResources()
  } catch (e) {
    console.error('Failed to save workspace resource:', e)
  } finally {
    resourceSaving.value = false
  }
}

const deleteWorkspaceResource = async (resourceId: string) => {
  try {
    await api.delete(`/resources/${resourceId}`)
    workspaceResources.value = workspaceResources.value.filter((resource) => resource.id !== resourceId)
  } catch (e) {
    console.error('Failed to delete workspace resource:', e)
  }
}

const interpretWorkspaceResource = async (resourceId: string) => {
  resourceInterpretingId.value = resourceId
  try {
    const response = await api.post(`/resources/${resourceId}/interpret`)
    workspaceResources.value = workspaceResources.value.map((resource) =>
      resource.id === resourceId ? response.data : resource
    )
  } catch (e) {
    console.error('Failed to interpret workspace resource:', e)
  } finally {
    resourceInterpretingId.value = null
  }
}

const decidePathCandidate = async (candidateId: string, action: string) => {
  pathCandidateSubmittingId.value = candidateId
  try {
    await api.post(`/problems/${route.params.id}/path-candidates/${candidateId}/decide`, { action })
    await Promise.all([
      fetchPathCandidates(),
      fetchLearningPath(),
      fetchLearningPaths(),
    ])
  } catch (e) {
    console.error('Failed to decide path candidate:', e)
  } finally {
    pathCandidateSubmittingId.value = null
  }
}

const handlePathCandidateDecision = ({ candidateId, action }: { candidateId: string; action: string }) => {
  decidePathCandidate(candidateId, action)
}

const scrollToWorkspaceInput = async (targetMode: 'socratic' | 'exploration') => {
  await nextTick()
  const selector = targetMode === 'exploration'
    ? '[data-testid="exploration-question-input"]'
    : '[data-testid="socratic-response-input"]'
  const input = document.querySelector(selector) as HTMLTextAreaElement | null
  if (!input) return
  input.scrollIntoView({ behavior: 'smooth', block: 'center' })
  input.focus()
}

const applyReinforcementActionTemplate = async () => {
  const template = reinforcementActionTemplate.value
  if (!template) return

  if (canSwitchToReinforcementPath.value) {
    await activateLearningPathById(reinforcementTargetPathId.value)
  }
  if (template.preferredMode !== learningMode.value) {
    await setLearningMode(template.preferredMode)
  }

  if (template.preferredMode === 'exploration') {
    learningQuestion.value = template.starter
    responseText.value = ''
  } else {
    responseText.value = template.starter
    learningQuestion.value = ''
  }

  await scrollToWorkspaceInput(template.preferredMode)
}

const switchToReinforcementPath = async () => {
  if (!canSwitchToReinforcementPath.value) return
  await activateLearningPathById(reinforcementTargetPathId.value)
  await scrollToReinforcementFocus()
}

const activateLearningPathById = async (pathId: string) => {
  if (updatingPath.value) return

  updatingPath.value = true
  try {
    const response = await api.post(`/problems/${route.params.id}/learning-paths/${pathId}/activate`)
    learningPath.value = response.data
    await Promise.all([
      fetchLearningPaths(),
      learningMode.value === 'socratic' ? fetchSocraticQuestion() : Promise.resolve(),
    ])
  } catch (e) {
    console.error('Failed to activate learning path:', e)
  } finally {
    updatingPath.value = false
  }
}

const applyResumePathFromQuery = async () => {
  const resumePathId = String(route.query.resume_path || '')
  if (!resumePathId) return
  if (String(learningPath.value?.id || '') === resumePathId) return
  if (!allLearningPaths.value.some((path: any) => String(path.id) === resumePathId)) return
  await activateLearningPathById(resumePathId)
}

const scrollToReinforcementFocus = async () => {
  await nextTick()
  const target = document.querySelector('[data-testid="derived-concept-focus-target"]')
    || document.querySelector('[data-testid="workspace-reinforcement-focus"]')
    || document.querySelector('[data-testid="workspace-reinforcement-target"]')
  if (target && 'scrollIntoView' in target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const returnToParentPath = async () => {
  if (updatingPath.value || !canReturnToParent.value) return

  updatingPath.value = true
  try {
    const response = await api.post(`/problems/${route.params.id}/learning-path/return`)
    learningPath.value = response.data
    await Promise.all([
      fetchLearningPaths(),
      learningMode.value === 'socratic' ? fetchSocraticQuestion() : Promise.resolve(),
    ])
  } catch (e) {
    console.error('Failed to return to parent learning path:', e)
  } finally {
    updatingPath.value = false
  }
}

onMounted(async () => {
  await fetchProblem()
  await applyResumePathFromQuery()
  await scrollToReinforcementFocus()
})
</script>

<style scoped>
.problem-detail {
  max-width: 1180px;
  margin: 0 auto;
}

.back-link {
  display: inline-block;
  margin-bottom: 1rem;
  color: var(--text-muted);
  text-decoration: none;
}

.back-link:hover {
  color: var(--primary);
}

.problem-header {
  margin-bottom: 2rem;
}

.problem-header h1 {
  margin-bottom: 0.5rem;
}

.problem-header p {
  color: var(--text-muted);
}

.problem-meta {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}

.mode-badge {
  font-size: 0.78rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  background: rgba(96, 165, 250, 0.1);
  color: #bfdbfe;
}

.problem-content {
  display: grid;
  gap: 1rem;
}

.workspace-mode-toggle {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.workspace-stage {
  display: grid;
  gap: 1rem;
}

.workspace-main-stack {
  display: grid;
  gap: 1rem;
}

.workspace-main-column {
  min-width: 0;
}

.workspace-side-column {
  min-width: 0;
}

.workspace-side-stack {
  display: grid;
  gap: 1rem;
}

.workspace-overview-card {
  display: grid;
  gap: 1rem;
}

.workspace-overview-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  flex-wrap: wrap;
}

.workspace-overview-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.workspace-link-action {
  text-decoration: none;
}

.workspace-eyebrow,
.workspace-summary-label {
  color: var(--primary);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.workspace-summary-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
}

.workspace-summary-card {
  padding: 0.9rem 1rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
  display: grid;
  gap: 0.35rem;
}

.workspace-summary-card strong {
  line-height: 1.35;
}

.workspace-summary-card p {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.workspace-mode-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  flex-wrap: wrap;
  padding-top: 0.9rem;
  border-top: 1px solid var(--border);
}

.reinforcement-target-card {
  border-color: rgba(248, 113, 113, 0.28);
  background: rgba(120, 24, 24, 0.16);
}

.reinforcement-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  flex-wrap: wrap;
}

.reinforcement-priority {
  display: inline-flex;
  align-items: center;
  padding: 0.28rem 0.7rem;
  border-radius: 999px;
  border: 1px solid rgba(248, 113, 113, 0.32);
  color: #fecaca;
  background: rgba(248, 113, 113, 0.16);
  font-size: 0.8rem;
  font-weight: 700;
}

.reinforcement-priority.priority-medium {
  border-color: rgba(250, 204, 21, 0.28);
  color: #fde68a;
  background: rgba(250, 204, 21, 0.12);
}

.reinforcement-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.85rem;
  margin-top: 0.85rem;
}

.reinforcement-preview {
  margin-top: 0.85rem;
  color: var(--text-muted);
  white-space: pre-wrap;
}

.reinforcement-actions {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
  margin-top: 0.85rem;
}

.reinforcement-focus-card {
  margin-top: 0.85rem;
  border-color: rgba(248, 113, 113, 0.34);
}

.reinforcement-action-card {
  margin-top: 0.85rem;
  border-color: rgba(96, 165, 250, 0.26);
}

.reinforcement-action-source {
  margin-top: 0.35rem;
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  border: 1px solid rgba(96, 165, 250, 0.18);
  background: rgba(96, 165, 250, 0.05);
}

.reinforcement-action-source p {
  margin-top: 0.3rem;
}

.reinforcement-action-warning {
  border-color: rgba(248, 113, 113, 0.26);
  background: rgba(120, 24, 24, 0.14);
}

.reinforcement-action-starter {
  margin-top: 0.35rem;
  padding: 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(96, 165, 250, 0.08);
}

.reinforcement-action-starter p {
  margin-top: 0.35rem;
  white-space: pre-wrap;
}

.workspace-mode-copy {
  min-width: 0;
  display: grid;
  gap: 0.2rem;
}

.workspace-mode-toggle .btn.active {
  border-color: var(--primary);
  color: var(--primary);
}

.card h2 {
  margin-bottom: 0.75rem;
}

.progress-overview {
  display: grid;
  gap: 0.5rem;
  margin-bottom: 1rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.progress-track {
  height: 8px;
  border-radius: 999px;
  background: var(--bg-dark);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #22c55e, var(--primary));
  transition: width 0.2s ease;
}

.step-card {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--border);
  background: var(--bg-dark);
  border-radius: 10px;
}

.step-number {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--primary);
  color: var(--bg-dark);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.step-content h3 {
  margin-bottom: 0.5rem;
}

.step-content p {
  color: var(--text-muted);
  font-size: 0.92rem;
}

.resources {
  margin-top: 0.5rem;
  padding-left: 1.2rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.completion-banner {
  padding: 0.85rem 1rem;
  border-radius: 8px;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  color: #86efac;
}

.path-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: 1rem;
}

.completed-badge {
  color: var(--primary);
  font-size: 0.875rem;
  font-weight: 600;
}

.path-structure-panel {
  margin-bottom: 1rem;
  padding: 0.85rem 1rem;
  border-radius: 10px;
  border: 1px solid rgba(96, 165, 250, 0.2);
  background: rgba(96, 165, 250, 0.06);
}

.path-structure-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.path-nav-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.6rem 0 0.75rem;
}

.path-nav-button.active {
  border-color: var(--primary);
  color: var(--primary);
}

.completed-panel {
  margin-top: 1rem;
}

.completed-panel summary {
  cursor: pointer;
  color: var(--text-muted);
}

.completed-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.completed-item {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(34, 197, 94, 0.08);
}

.completed-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.35);
  color: #dcfce7;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
}

.section-subtitle {
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.response-form {
  margin-bottom: 1rem;
}

.socratic-question-panel {
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: 10px;
  background: rgba(96, 165, 250, 0.08);
}

.question-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.45rem;
}

.question-kind-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.6rem;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  color: #bfdbfe;
  font-size: 0.75rem;
  font-weight: 600;
}

.question-copy {
  margin: 0;
  color: var(--text);
  white-space: pre-wrap;
}

.response-actions {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
}

.auto-advance-notice {
  margin: 0.5rem 0 0.8rem;
  color: #86efac;
  font-size: 0.9rem;
}

.undo-auto-wrap {
  margin-bottom: 0.75rem;
}

.hint-panel {
  margin: 0.6rem 0 1rem;
  padding: 0.8rem;
  border: 1px solid var(--border);
  border-left: 3px solid #60a5fa;
  border-radius: 8px;
  background: rgba(96, 165, 250, 0.08);
}

.hint-panel h3 {
  margin-bottom: 0.5rem;
  font-size: 1rem;
}

.hint-panel ul {
  padding-left: 1.1rem;
  margin: 0.4rem 0;
}

.hint-panel li + li {
  margin-top: 0.2rem;
}

.qa-section {
  margin-top: 0.25rem;
}

.ask-mode-toggle {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.ask-mode-toggle .btn.active {
  border-color: var(--primary);
  color: var(--primary);
}

.qa-latest {
  margin-top: 0.8rem;
  padding: 0.85rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-dark);
}

.qa-latest h3 {
  margin-bottom: 0.35rem;
  font-size: 1rem;
}

.qa-meta {
  color: var(--text-muted);
  font-size: 0.82rem;
  margin-bottom: 0.6rem;
}

.qa-block + .qa-block {
  margin-top: 0.55rem;
}

.qa-actions-block {
  margin-top: 0.75rem;
}

.qa-actions-block ul {
  margin: 0.35rem 0 0;
  padding-left: 1.1rem;
}

.qa-actions-block li + li {
  margin-top: 0.25rem;
}

.path-suggestion-list {
  display: grid;
  gap: 0.55rem;
  margin-top: 0.45rem;
}

.path-suggestion-item {
  padding: 0.7rem 0.8rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(96, 165, 250, 0.06);
}

.path-suggestion-head {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
  margin-bottom: 0.25rem;
}

.qa-block p {
  margin-top: 0.25rem;
  white-space: pre-wrap;
}

.qa-focus-line {
  margin-top: 0.55rem;
  color: var(--text-muted);
}

.mode-line {
  margin-bottom: 0.45rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.system-feedback {
  margin-top: 0.5rem;
  padding: 0.9rem;
  border-radius: 8px;
  background: rgba(74, 222, 128, 0.12);
  border-left: 3px solid var(--primary);
}

.system-feedback h3 {
  margin-bottom: 0.5rem;
  font-size: 1rem;
}

.history-panel {
  margin-top: 1rem;
}

.history-panel summary {
  cursor: pointer;
  color: var(--text-muted);
}

.responses-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.response-item {
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-dark);
}

.user-response p {
  margin-top: 0.35rem;
}

.history-feedback {
  margin-top: 0.5rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.new-concepts-line {
  margin-top: 0.45rem;
  color: #86efac;
}

.pending-concepts-line {
  margin-top: 0.35rem;
  color: #facc15;
}

.ops-meta-line {
  margin-top: 0.35rem;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.ops-fallback-line {
  margin-top: 0.25rem;
  color: #fda4af;
  font-size: 0.82rem;
}

.concept-governance-section {
  margin-top: 0.25rem;
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
  color: var(--text-muted);
}

.candidate-confidence,
.candidate-source {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.candidate-evidence {
  margin-top: 0.45rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  white-space: pre-wrap;
}

.candidate-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.6rem;
}

.candidate-pending {
  border-color: rgba(250, 204, 21, 0.35);
}

.candidate-accepted {
  border-color: rgba(34, 197, 94, 0.35);
}

.candidate-planned {
  border-color: rgba(34, 197, 94, 0.35);
}

.candidate-bookmarked {
  border-color: rgba(96, 165, 250, 0.35);
}

.candidate-dismissed {
  border-color: rgba(148, 163, 184, 0.28);
  opacity: 0.8;
}

@media (min-width: 980px) {
  .workspace-stage {
    grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.85fr);
    align-items: start;
  }
}

@media (max-width: 900px) {
  .workspace-mode-row {
    display: grid;
  }
}

.status {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  text-transform: capitalize;
}

.status.new {
  background: #3b82f6;
  color: white;
}

.status.in-progress {
  background: #f59e0b;
  color: black;
}

.status.completed {
  background: var(--primary);
  color: var(--bg-dark);
}

.progress-text {
  color: var(--text-muted);
  font-size: 0.875rem;
}

.empty,
.loading {
  color: var(--text-muted);
  padding: 1rem 0;
}
</style>
