<template>
  <div class="problem-detail" data-testid="problem-detail-workspace">
    <PrimaryAsyncStateCard
      v-if="pageState === 'error'"
      kind="error"
      :title="t('problemDetail.errorTitle')"
      :message="pageError || t('problemDetail.errorMessage')"
      :retry-label="t('common.retry')"
      test-id="problem-detail-error-state"
      retry-test-id="problem-detail-error-retry"
      @retry="loadWorkspace"
    />

    <div v-else-if="loading" class="loading">{{ t('common.loading') }}</div>

    <template v-else-if="problem">
      <section class="problem-learning-header card" data-testid="problem-learning-header">
        <div class="learning-header-copy">
          <router-link to="/problems" class="back-link">&larr; {{ t('common.back') }}</router-link>
          <p class="problem-kicker">{{ t('problemDetail.learningHeaderKicker') }}</p>
          <h1>{{ problem.title }}</h1>
          <p>{{ problem.description }}</p>
        </div>

        <div class="learning-header-status">
          <article class="header-pill">
            <span class="workspace-summary-label">{{ t('problemDetail.currentPath') }}</span>
            <strong>{{ workspacePathSummary }}</strong>
            <p v-if="learningPath?.branch_reason">{{ learningPath.branch_reason }}</p>
            <p v-else-if="learningPath?.parent_path_id && learningPath?.return_step_id !== null && learningPath?.return_step_id !== undefined">
              {{ t('problemDetail.returnStepLabel', { step: Number(learningPath.return_step_id) + 1 }) }}
            </p>
          </article>
          <article class="header-pill">
            <span class="workspace-summary-label">{{ t('problemDetail.currentMode') }}</span>
            <strong>{{ formatLearningMode(learningMode) }}</strong>
            <p>{{ modeSummary }}</p>
          </article>
          <article class="header-pill">
            <span class="workspace-summary-label">{{ t('problemDetail.progress') }}</span>
            <strong>{{ progressSummary }}</strong>
            <p>{{ currentStepSummary }}</p>
          </article>
        </div>

        <div class="learning-header-controls">
          <span class="workspace-summary-label">{{ t('problemDetail.modeSwitchTitle') }}</span>
          <div class="workspace-mode-toggle compact-mode-toggle">
            <button
              type="button"
              class="btn btn-secondary"
              :class="{ active: learningMode === 'socratic' }"
              :disabled="switchingMode || submitting || askingQuestion || fetchingSocraticQuestion"
              data-testid="mode-switch-socratic"
              @click="setLearningMode('socratic')"
            >
              {{ t('problemDetail.modeSocratic') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              :class="{ active: learningMode === 'exploration' }"
              :disabled="switchingMode || submitting || askingQuestion || fetchingSocraticQuestion"
              data-testid="mode-switch-exploration"
              @click="setLearningMode('exploration')"
            >
              {{ t('problemDetail.modeExploration') }}
            </button>
          </div>
        </div>
      </section>

      <section class="card learning-contract-card" data-testid="problem-learning-contract">
        <div class="section-heading">
          <div>
            <p class="workspace-eyebrow">{{ t('problemDetail.contractTitle') }}</p>
            <h2>{{ t('problemDetail.contractHeading') }}</h2>
            <p class="section-subtitle">{{ t('problemDetail.contractSubtitle') }}</p>
          </div>
        </div>

        <div class="contract-grid">
          <article class="workspace-summary-card">
            <span class="workspace-summary-label">{{ t('problemDetail.contractTaskLabel') }}</span>
            <strong>{{ contractTask }}</strong>
            <p>{{ currentStepSummary }}</p>
          </article>
          <article class="workspace-summary-card">
            <span class="workspace-summary-label">{{ t('problemDetail.contractReasonLabel') }}</span>
            <strong>{{ contractReason }}</strong>
            <p>{{ workspaceNextAction }}</p>
          </article>
          <article class="workspace-summary-card">
            <span class="workspace-summary-label">{{ t('problemDetail.contractDoneLabel') }}</span>
            <strong>{{ contractDone }}</strong>
            <p>{{ contractDoneSupport }}</p>
          </article>
        </div>

        <details v-if="showContractControls" class="path-options-panel contract-controls-panel">
          <summary>{{ t('problemDetail.pathControlsTitle') }}</summary>
          <p class="section-subtitle contract-controls-copy">{{ t('problemDetail.pathControlsSubtitle') }}</p>

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

          <div class="contract-action-row">
            <button
              type="button"
              class="btn btn-secondary"
              :disabled="updatingPath || completedSteps === 0"
              @click="updateCurrentStep(completedSteps - 1)"
            >
              {{ t('problemDetail.previousStep') }}
            </button>
            <button
              v-if="!isPathCompleted && learningMode !== 'socratic'"
              type="button"
              class="btn btn-primary"
              :disabled="updatingPath"
              data-testid="mark-step-done"
              @click="updateCurrentStep(completedSteps + 1)"
            >
              {{ t('problemDetail.markStepDone') }}
            </button>
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
        </details>
      </section>

      <section
        v-if="activeReinforcementTarget && activeReinforcementEntry"
        class="card reinforcement-strip"
        data-testid="workspace-reinforcement-target"
      >
        <div class="reinforcement-strip-copy">
          <p class="workspace-eyebrow">{{ t('problemDetail.reinforcementStripTitle') }}</p>
          <strong>{{ reinforcementFocusTitle }}</strong>
          <p>{{ formatReinforcementSummary(activeReinforcementEntry) }}</p>
          <p class="section-subtitle">{{ formatReinforcementResume(activeReinforcementTarget) }}</p>
          <router-link
            v-if="activeReinforcementEntry.model_card_id"
            :to="`/model-cards/${activeReinforcementEntry.model_card_id}`"
            class="reinforcement-context-link"
          >
            {{ t('problemDetail.openModelCard') }}
          </router-link>
        </div>
        <div class="reinforcement-strip-actions">
          <button
            v-if="reinforcementActionTemplate"
            type="button"
            class="btn btn-primary"
            data-testid="apply-reinforcement-action-template"
            @click="applyReinforcementActionTemplate"
          >
            {{ t('problemDetail.useReinforcementStarter') }}
          </button>
          <button
            v-else-if="canSwitchToReinforcementPath"
            type="button"
            class="btn btn-primary"
            data-testid="switch-to-reinforcement-path"
            @click="switchToReinforcementPath"
          >
            {{ t('problemDetail.switchToReinforcementPath') }}
          </button>
        </div>
      </section>

      <section class="card primary-turn-card" data-testid="problem-turn-area">
        <div class="section-heading">
          <div>
            <p class="workspace-eyebrow">{{ learningMode === 'socratic' ? t('problemDetail.progressSectionTitle') : t('problemDetail.askTitle') }}</p>
            <h2>{{ learningMode === 'socratic' ? t('problemDetail.currentQuestionTitle') : t('problemDetail.askTitle') }}</h2>
            <p class="section-subtitle">
              {{ learningMode === 'socratic' ? t('problemDetail.modeSocraticHint') : t('problemDetail.askSubtitle') }}
            </p>
          </div>
        </div>

        <div v-if="currentStep" class="turn-step-card">
          <div class="step-number">{{ currentStepNumber }}</div>
          <div class="step-content">
            <p class="workspace-summary-label">{{ t('problemDetail.currentStepTitle') }}</p>
            <h3>{{ currentStep.concept }}</h3>
            <p>{{ currentStep.description }}</p>
          </div>
        </div>
        <div v-else-if="isPathCompleted && totalSteps" class="completion-banner">
          {{ t('problemDetail.completedAll') }}
        </div>
        <p v-else class="empty">{{ t('problemDetail.noLearningPath') }}</p>

        <p v-if="workspaceActionError" class="workspace-action-error" data-testid="workspace-action-error">
          {{ workspaceActionError }}
        </p>

        <template v-if="learningMode === 'socratic'">
          <p class="protocol-note" data-testid="socratic-protocol-note">{{ t('problemDetail.socraticProgressControlled') }}</p>

          <div v-if="socraticQuestion" class="socratic-question-panel" data-testid="socratic-question-panel">
            <div class="question-head">
              <strong>{{ t('problemDetail.currentQuestionTitle') }}</strong>
              <span class="question-kind-badge">{{ formatQuestionKind(socraticQuestion.question_kind) }}</span>
            </div>
            <p class="question-copy">{{ socraticQuestion.question }}</p>
          </div>
          <div
            v-else-if="fetchingSocraticQuestion && streamingSocraticQuestion"
            class="socratic-question-panel"
            data-testid="socratic-question-panel"
          >
            <div class="question-head">
              <strong>{{ t('problemDetail.currentQuestionTitle') }}</strong>
              <span class="question-kind-badge">{{ t('common.loading') }}</span>
            </div>
            <p class="question-copy" data-testid="socratic-question-stream-preview">
              {{ streamingSocraticQuestion }}<span class="streaming-cursor">|</span>
            </p>
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
          <div
            v-if="submitting && (streamingSocraticStatus || streamingSocraticPreview)"
            class="streaming-answer-panel"
            data-testid="socratic-response-stream-preview"
          >
            <strong>{{ t('problemDetail.socraticStreamTitle') }}</strong>
            <p class="section-subtitle">{{ streamingSocraticStatus || t('common.loading') }}</p>
            <p v-if="streamingSocraticPreview" class="streaming-answer-copy">
              {{ streamingSocraticPreview }}<span class="streaming-cursor">|</span>
            </p>
          </div>
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
        </template>

        <template v-else>
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

          <div
            v-if="askingQuestion && streamingExplorationAnswer"
            class="streaming-answer-panel"
            data-testid="exploration-stream-preview"
          >
            <strong>{{ t('problemDetail.askStreamingTitle') }}</strong>
            <p class="section-subtitle">{{ t('problemDetail.askStreamingHint') }}</p>
            <p class="streaming-answer-copy">
              {{ streamingExplorationAnswer }}<span class="streaming-cursor">|</span>
            </p>
          </div>
        </template>
      </section>

      <section class="card turn-result-card" data-testid="problem-turn-result">
        <div class="section-heading">
          <div>
            <p class="workspace-eyebrow">{{ t('problemDetail.turnResultTitle') }}</p>
            <h2>{{ turnResultHeading }}</h2>
            <p class="section-subtitle">
              {{ turnResultSubtitle }}
            </p>
          </div>
        </div>

        <div
          v-if="isTurnProcessing"
          class="turn-result-processing"
          data-testid="turn-result-processing"
        >
          <strong>{{ turnProcessingTitle }}</strong>
          <p>{{ turnProcessingDescription }}</p>
          <p v-if="turnProcessingSupport" class="turn-processing-support">{{ turnProcessingSupport }}</p>
        </div>

        <div
          v-else-if="!hasContextualInteractionOutput"
          class="workspace-current-output-empty"
          data-testid="workspace-current-output-empty"
        >
          <strong>{{ t('problemDetail.currentOutputEmptyTitle') }}</strong>
          <p>
            {{
              learningMode === 'socratic'
                ? t('problemDetail.currentOutputEmptyDescriptionSocratic')
                : t('problemDetail.currentOutputEmptyDescriptionExploration')
            }}
          </p>
        </div>

        <ProblemTurnOutcomePanel
          v-if="hasContextualInteractionOutput"
          embedded
          :learning-mode="learningMode"
          :latest-response="latestResponse"
          :latest-feedback="latestFeedback"
          :latest-qa="latestQA"
        />
      </section>

      <section class="card postturn-card" data-testid="problem-postturn-decisions">
        <div class="section-heading">
          <div>
            <p class="workspace-eyebrow">{{ t('problemDetail.postTurnTitle') }}</p>
            <h2>{{ t('problemDetail.postTurnHeading') }}</h2>
            <p class="section-subtitle">{{ t('problemDetail.postTurnSubtitle') }}</p>
          </div>
        </div>

        <div class="postturn-summary-strip">
          <article class="workspace-summary-card">
            <span class="workspace-summary-label">{{ t('problemDetail.derivedConceptsTitle') }}</span>
            <strong>{{ currentTurnConceptCandidates.length }}</strong>
            <p>{{ t('problemDetail.postTurnConceptSummary') }}</p>
          </article>
          <article class="workspace-summary-card">
            <span class="workspace-summary-label">{{ t('problemDetail.pathCandidatesTitle') }}</span>
            <strong>{{ currentTurnPathCandidates.length }}</strong>
            <p>{{ t('problemDetail.postTurnPathSummary') }}</p>
          </article>
          <article class="workspace-summary-card" data-testid="workspace-review-summary">
            <span class="workspace-summary-label">{{ t('problemDetail.postTurnFollowThroughLabel') }}</span>
            <strong>{{ workspaceReviewSummary }}</strong>
            <p>{{ workspaceReviewDescription }}</p>
          </article>
        </div>

        <details class="postturn-details" :open="Boolean(hasContextualInteractionOutput && currentTurnConceptCandidates.length)">
          <summary>{{ t('problemDetail.postTurnConceptActions') }}</summary>
          <ProblemDerivedConceptsPanel
            embedded
            collapse-older
            :older-only="!hasContextualInteractionOutput"
            :candidates="conceptCandidates"
            :loading="candidateLoading"
            :current-turn-id="artifactFocusTurnId"
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
        </details>

        <details class="postturn-details" :open="Boolean(hasContextualInteractionOutput && currentTurnPathCandidates.length)">
          <summary>{{ t('problemDetail.postTurnPathActions') }}</summary>
          <ProblemDerivedPathsPanel
            embedded
            collapse-older
            :older-only="!hasContextualInteractionOutput"
            :candidates="pathCandidates"
            :current-turn-id="artifactFocusTurnId"
            :loading="pathCandidateLoading"
            :submitting-id="pathCandidateSubmittingId"
            @decide="handlePathCandidateDecision"
          />
        </details>
      </section>

      <section class="card secondary-tools-card" data-testid="problem-secondary-tools">
        <div class="section-heading">
          <div>
            <p class="workspace-eyebrow">{{ t('problemDetail.secondaryToolsTitle') }}</p>
            <h2>{{ t('problemDetail.secondaryToolsHeading') }}</h2>
            <p class="section-subtitle">{{ t('problemDetail.secondaryToolsSubtitle') }}</p>
          </div>
        </div>

        <div class="secondary-tools-grid">
          <details class="secondary-detail">
            <summary>{{ learningMode === 'socratic' ? t('problemDetail.historyTitle', { count: responses.length }) : t('problemDetail.qaHistoryTitle', { count: qaHistory.length }) }}</summary>
            <div v-if="learningMode === 'socratic'">
              <div v-if="responses.length" class="responses-list">
                <div v-for="response in responseHistory" :key="response.id" class="response-item" data-testid="socratic-history-item">
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
                    <p v-if="response.structured_feedback.misconceptions?.length">
                      <strong>{{ t('feedback.misconceptions') }}:</strong> {{ response.structured_feedback.misconceptions.join(' / ') }}
                    </p>
                  </div>
                </div>
              </div>
              <p v-else class="empty">{{ t('problemDetail.noProgressRecords') }}</p>
            </div>
            <div v-else>
              <div v-if="qaHistory.length" class="responses-list">
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
              <p v-else class="empty">{{ t('problemDetail.noTurnResultExploration') }}</p>
            </div>
          </details>

          <details class="secondary-detail" data-testid="workspace-assets-panel">
            <summary data-testid="workspace-assets-toggle">{{ t('problemDetail.workspaceAssetsTitle') }}</summary>
            <div class="workspace-assets-stack">
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
            </div>
          </details>

          <details class="secondary-detail">
            <summary>{{ t('nav.more') }}</summary>
            <div class="secondary-actions-block">
              <button
                type="button"
                class="btn btn-secondary"
                :disabled="exportingLearningRecord"
                data-testid="export-learning-record"
                @click="exportLearningRecord"
              >
                {{ t('problemDetail.exportLearningRecord') }}
              </button>

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
            </div>
          </details>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import PrimaryAsyncStateCard from '@/components/PrimaryAsyncStateCard.vue'
import ProblemTurnOutcomePanel from '@/components/problem-workspace/ProblemTurnOutcomePanel.vue'
import ProblemDerivedConceptsPanel from '@/components/problem-workspace/ProblemDerivedConceptsPanel.vue'
import ProblemDerivedPathsPanel from '@/components/problem-workspace/ProblemDerivedPathsPanel.vue'
import ProblemWorkspaceNotesPanel from '@/components/problem-workspace/ProblemWorkspaceNotesPanel.vue'
import ProblemWorkspaceResourcesPanel from '@/components/problem-workspace/ProblemWorkspaceResourcesPanel.vue'
import { createProblemDetailLearningActions } from '@/views/problem-detail/learningActions'
import { createProblemDetailKnowledgeAssetActions } from '@/views/problem-detail/knowledgeAssetActions'
import { createProblemDetailPathActions } from '@/views/problem-detail/pathActions'
import { createProblemDetailDataSupport } from '@/views/problem-detail/problemDetailDataSupport'
import { createProblemDetailWorkspaceAssetActions } from '@/views/problem-detail/workspaceAssetActions'
import { createProblemDetailWorkspaceSummarySupport } from '@/views/problem-detail/workspaceSummarySupport'
import type { AsyncPageState } from '@/types/ui'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const problem = ref<any>(null)
const learningPath = ref<any>(null)
const allLearningPaths = ref<any[]>([])
const responses = ref<any[]>([])
const learningMode = ref<'socratic' | 'exploration'>('socratic')
const loading = ref(true)
const pageState = ref<AsyncPageState>('loading')
const pageError = ref('')
const submitting = ref(false)
const updatingPath = ref(false)
const switchingMode = ref(false)
const hintLoading = ref(false)
const workspaceActionError = ref('')
const responseText = ref('')
const autoAdvanceMessage = ref('')
const canUndoAutoAdvance = ref(false)
const undoTargetStep = ref<number | null>(null)
const stepHint = ref<any | null>(null)
const socraticQuestion = ref<any | null>(null)
const fetchingSocraticQuestion = ref(false)
const streamingSocraticQuestion = ref('')
const streamingSocraticStatus = ref('')
const streamingSocraticPreview = ref('')
const learningQuestion = ref('')
const askingQuestion = ref(false)
const streamingExplorationAnswer = ref('')
const latestExplorationTurnId = ref<string | null>(null)
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
const exportingLearningRecord = ref(false)
const workspaceNotes = ref<any[]>([])
const noteSaving = ref(false)
const workspaceResources = ref<any[]>([])
const resourceSaving = ref(false)
const resourceInterpretingId = ref<string | null>(null)
const artifactsExpanded = ref(false)
const currentInteractionTurnId = ref<string | null>(null)
const currentInteractionMode = ref<'socratic' | 'exploration' | null>(null)
const currentInteractionStepKey = ref<string | null>(null)
const hasCurrentInteractionOutput = ref(false)

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
const completedStepList = computed(() => (learningPath.value?.path_data || []).slice(0, completedSteps.value))
const progressSummary = computed(() => (
  totalSteps.value
    ? t('problemDetail.stepIndicator', { current: currentStepNumber.value, total: totalSteps.value })
    : t('problemDetail.noLearningPath')
))
const currentStepSummary = computed(() => {
  if (currentStep.value?.description) return currentStep.value.description
  if (isPathCompleted.value) return t('problemDetail.completedAll')
  return t('problemDetail.noLearningPath')
})
const modeSummary = computed(() => (
  learningMode.value === 'exploration'
    ? t('problemDetail.modeExplorationHint')
    : t('problemDetail.modeSocraticHint')
))
const contractTask = computed(() => {
  if (isPathCompleted.value) return t('problemDetail.completedAll')
  if (currentStep.value?.concept) {
    return t('problemDetail.contractTaskConcept', { concept: currentStep.value.concept })
  }
  return t('problemDetail.contractTaskProblem', { title: problem.value?.title || t('problemDetail.title') })
})
const contractReason = computed(() => (
  learningPath.value?.branch_reason
    || currentStep.value?.description
    || (
      learningMode.value === 'exploration'
        ? t('problemDetail.workspaceFrameExploration')
        : t('problemDetail.workspaceFrameSocratic')
    )
))
const contractDone = computed(() => {
  if (isPathCompleted.value) return t('problemDetail.completedAll')
  if (
    learningPath.value?.kind === 'prerequisite'
    && learningPath.value?.return_step_id !== null
    && learningPath.value?.return_step_id !== undefined
  ) {
    return t('problemDetail.contractDonePrerequisite', {
      step: Number(learningPath.value.return_step_id) + 1,
      target: problem.value?.title || t('problemDetail.title'),
    })
  }
  return learningMode.value === 'exploration'
    ? t('problemDetail.contractDoneExploration')
    : t('problemDetail.contractDoneSocratic')
})
const contractDoneSupport = computed(() => {
  if (isPathCompleted.value) return t('problemDetail.contractDoneSupportCompleted')
  if (learningPath.value?.kind === 'prerequisite') {
    return t('problemDetail.contractDoneSupportPrerequisite')
  }
  return learningMode.value === 'exploration'
    ? t('problemDetail.contractDoneSupportExploration')
    : t('problemDetail.contractDoneSupportSocratic')
})
const showContractControls = computed(() => (
  allLearningPaths.value.length > 1
  || completedSteps.value > 0
  || (!isPathCompleted.value && learningMode.value !== 'socratic')
  || canReturnToParent.value
))

const buildCurrentInteractionStepKey = (mode: 'socratic' | 'exploration' = learningMode.value) => {
  return `${mode}:${String(learningPath.value?.id || 'no-path')}:${completedSteps.value}`
}

const clearActionError = () => {
  workspaceActionError.value = ''
}

const onActionError = (message: string) => {
  workspaceActionError.value = message
}

const resolveExportFilename = (contentDisposition?: string) => {
  const match = String(contentDisposition || '').match(/filename=\"?([^\";]+)\"?/)
  if (match?.[1]) return match[1]
  return `${String(problem.value?.title || 'learning-record').trim().replace(/\s+/g, '-') || 'learning-record'}.md`
}

const exportLearningRecord = async () => {
  clearActionError()
  exportingLearningRecord.value = true
  try {
    const response = await api.get(`/problems/${route.params.id}/export`, {
      responseType: 'blob',
    })
    const filename = resolveExportFilename(response.headers['content-disposition'])
    const url = URL.createObjectURL(new Blob([response.data], { type: 'text/markdown' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to export learning record:', error)
    onActionError(t('problemDetail.exportLearningFailed'))
  } finally {
    exportingLearningRecord.value = false
  }
}

const clearCurrentInteractionContext = (mode: 'socratic' | 'exploration' = learningMode.value) => {
  responseText.value = ''
  learningQuestion.value = ''
  stepHint.value = null
  socraticQuestion.value = null
  streamingSocraticQuestion.value = ''
  streamingSocraticStatus.value = ''
  streamingSocraticPreview.value = ''
  streamingExplorationAnswer.value = ''
  latestExplorationTurnId.value = null
  currentInteractionTurnId.value = null
  currentInteractionMode.value = mode
  currentInteractionStepKey.value = buildCurrentInteractionStepKey(mode)
  hasCurrentInteractionOutput.value = false
  artifactsExpanded.value = false
}

const captureCurrentInteractionOutput = (
  turnId: string | null,
  mode: 'socratic' | 'exploration' = learningMode.value,
) => {
  currentInteractionTurnId.value = turnId
  currentInteractionMode.value = mode
  currentInteractionStepKey.value = buildCurrentInteractionStepKey(mode)
  hasCurrentInteractionOutput.value = Boolean(turnId)
  if (mode === 'exploration') {
    latestExplorationTurnId.value = turnId
  }
  artifactsExpanded.value = false
}

const latestResponseRecord = computed(() => responses.value[responses.value.length - 1] || null)
const latestExplorationTurn = computed(() => {
  if (latestExplorationTurnId.value) {
    const exactTurn = qaHistory.value.find((turn: any) => String(turn.turn_id || '') === String(latestExplorationTurnId.value))
    if (exactTurn) return exactTurn
  }
  return qaHistory.value[0] || null
})
const currentInteractionContextKey = computed(() => (
  buildCurrentInteractionStepKey(currentInteractionMode.value || learningMode.value)
))
const currentInteractionStepMatchesContext = computed(() => (
  Boolean(currentInteractionTurnId.value)
  && currentInteractionMode.value === learningMode.value
  && Boolean(currentInteractionStepKey.value)
  && currentInteractionStepKey.value === currentInteractionContextKey.value
))
const currentInteractionMatchesContext = computed(() => (
  hasCurrentInteractionOutput.value && currentInteractionStepMatchesContext.value
))
const hasContextualInteractionOutput = computed(() => (
  hasCurrentInteractionOutput.value && currentInteractionStepMatchesContext.value
))
const latestResponse = computed(() => {
  if (!currentInteractionMatchesContext.value || currentInteractionMode.value !== 'socratic') return null
  return responses.value.find(
    (response: any) => String(response.turn_id || '') === String(currentInteractionTurnId.value),
  ) || null
})
const latestQA = computed(() => {
  if (!currentInteractionMatchesContext.value || currentInteractionMode.value !== 'exploration') return null
  return qaHistory.value.find(
    (turn: any) => String(turn.turn_id || '') === String(currentInteractionTurnId.value),
  ) || null
})
const responseHistory = computed(() => [...responses.value].reverse())
const latestFeedback = computed(() => latestResponse.value?.structured_feedback || null)
const isTurnProcessing = computed(() => submitting.value || askingQuestion.value)
const turnResultHeading = computed(() => (
  isTurnProcessing.value
    ? t('problemDetail.turnResultProcessingHeading')
    : workspaceTurnSummary.value
))
const turnResultSubtitle = computed(() => {
  if (isTurnProcessing.value) {
    return learningMode.value === 'socratic'
      ? t('problemDetail.turnResultProcessingSubtitleSocratic')
      : t('problemDetail.turnResultProcessingSubtitleExploration')
  }
  return learningMode.value === 'socratic'
    ? t('problemDetail.turnResultSubtitleSocratic')
    : t('problemDetail.turnResultSubtitleExploration')
})
const turnProcessingTitle = computed(() => {
  if (learningMode.value === 'socratic') {
    return streamingSocraticStatus.value || t('problemDetail.turnResultProcessingTitleSocratic')
  }
  return t('problemDetail.turnResultProcessingTitleExploration')
})
const truncateInline = (value: unknown, max = 160) => {
  const normalized = String(value || '').replace(/\s+/g, ' ').trim()
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, max - 1).trimEnd()}…`
}
const turnProcessingDescription = computed(() => {
  if (learningMode.value === 'socratic') {
    return t('problemDetail.turnResultProcessingDescriptionSocratic')
  }
  return t('problemDetail.turnResultProcessingDescriptionExploration')
})
const turnProcessingSupport = computed(() => {
  if (learningMode.value === 'socratic') {
    if (streamingSocraticPreview.value) return truncateInline(streamingSocraticPreview.value)
    if (responseText.value.trim()) return truncateInline(responseText.value)
    return ''
  }
  if (streamingExplorationAnswer.value) return truncateInline(streamingExplorationAnswer.value)
  if (learningQuestion.value.trim()) return truncateInline(learningQuestion.value)
  return ''
})
const activeConceptTurnId = computed(() => (
  currentInteractionMatchesContext.value ? currentInteractionTurnId.value : null
))
const artifactFocusTurnId = computed(() => activeConceptTurnId.value)
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
const currentTurnConceptCandidates = computed(() => {
  if (!artifactFocusTurnId.value) return []
  return conceptCandidates.value.filter((candidate: any) => String(candidate.source_turn_id || '') === String(artifactFocusTurnId.value))
})
const currentTurnPathCandidates = computed(() => {
  if (!artifactFocusTurnId.value) return []
  return pathCandidates.value.filter((candidate: any) => String(candidate.source_turn_id || '') === String(artifactFocusTurnId.value))
})
const {
  workspacePathSummary,
  workspaceTurnSummary,
  workspaceNextAction,
  workspaceReviewSummary,
  workspaceReviewDescription,
  conceptMergeTargets,
  scheduledReviewsByModelCardId,
  activeReinforcementEntry,
  activeReinforcementTarget,
  reinforcementFocusCandidateId,
  reinforcementFocusTurnId,
  reinforcementTargetPathId,
  canSwitchToReinforcementPath,
  reinforcementFocusTitle,
  reinforcementActionTemplate,
  formatConfidence,
  formatReinforcementResume,
  formatReinforcementSummary,
  formatLearningMode,
  formatLearningPathKind,
  formatQuestionKind,
  formatAnswerType,
} = createProblemDetailWorkspaceSummarySupport({
  t,
  route,
  problem,
  learningPath,
  allLearningPaths,
  learningMode,
  totalSteps,
  currentStepNumber,
  currentStep,
  latestQA,
  latestResponse,
  latestFeedback,
  latestPathArtifacts,
  latestDerivedConceptCount,
  activeConceptTurnId,
  socraticQuestion,
  qaHistory,
  conceptCandidates,
  pathCandidates,
  scheduledReviews,
})
const {
  fetchReviewSchedules,
  hydrateWorkspaceSnapshot,
  saveWorkspaceNote,
  deleteWorkspaceNote,
  saveWorkspaceResource,
  deleteWorkspaceResource,
  interpretWorkspaceResource,
} = createProblemDetailWorkspaceAssetActions({
  api,
  problemId: String(route.params.id),
  activeConceptTurnId,
  scheduledModelCardIds,
  scheduledReviews,
  workspaceNotes,
  noteSaving,
  workspaceResources,
  resourceSaving,
  resourceInterpretingId,
})

const {
  fetchExplorationTurns,
  fetchSocraticQuestion,
  fetchConceptCandidates,
  fetchPathCandidates,
  fetchLearningPath,
  fetchLearningPaths,
  fetchProblem,
} = createProblemDetailDataSupport({
  api,
  t,
  problemId: String(route.params.id),
  ensureFreshToken: () => authStore.ensureFreshToken(),
  refreshToken: () => authStore.refreshToken(),
  getToken: () => authStore.token,
  problem,
  learningMode,
  loading,
  responses,
  learningPath,
  allLearningPaths,
  qaHistory,
  conceptCandidates,
  pathCandidates,
  socraticQuestion,
  fetchingSocraticQuestion,
  streamingSocraticQuestion,
  candidateLoading,
  pathCandidateLoading,
  hydrateWorkspaceSnapshot,
  onActionError,
  clearActionError,
})

const {
  syncProblemSnapshot,
  setLearningMode,
  submitResponse,
  prefillGuidedTemplate,
  askLearningQuestion,
} = createProblemDetailLearningActions({
  api,
  problemId: String(route.params.id),
  t,
  ensureFreshToken: () => authStore.ensureFreshToken(),
  refreshToken: () => authStore.refreshToken(),
  getToken: () => authStore.token,
  problem,
  learningMode,
  switchingMode,
  submitting,
  hintLoading,
  askingQuestion,
  responses,
  responseText,
  learningQuestion,
  answerMode,
  socraticQuestion,
  stepHint,
  autoAdvanceMessage,
  canUndoAutoAdvance,
  undoTargetStep,
  streamingSocraticStatus,
  streamingSocraticPreview,
  streamingExplorationAnswer,
  latestExplorationTurnId,
  currentStep,
  clearCurrentInteractionContext,
  captureCurrentInteractionOutput,
  onActionError,
  clearActionError,
  fetchConceptCandidates,
  fetchPathCandidates,
  fetchExplorationTurns,
  fetchLearningPath,
  fetchSocraticQuestion,
})

const {
  acceptCandidate,
  rejectCandidate,
  postponeCandidate,
  mergeCandidate,
  rollbackConcept,
  promoteCandidateToModelCard,
  openModelCard,
  scheduleCandidateReview,
} = createProblemDetailKnowledgeAssetActions({
  api,
  problemId: String(route.params.id),
  router,
  candidateSubmittingId,
  handoffSubmittingId,
  fetchConceptCandidates,
  fetchReviewSchedules,
  syncProblemSnapshot,
})

const {
  updateCurrentStep,
  undoAutoAdvance,
  activateLearningPathById,
  returnToParentPath,
} = createProblemDetailPathActions({
  api,
  problemId: String(route.params.id),
  t,
  learningPath,
  learningMode,
  updatingPath,
  problem,
  totalSteps,
  autoAdvanceMessage,
  canUndoAutoAdvance,
  undoTargetStep,
  clearCurrentInteractionContext,
  onActionError,
  clearActionError,
  fetchLearningPath,
  fetchLearningPaths,
  fetchSocraticQuestion,
})

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

const hydrateCurrentInteractionFromWorkspace = () => {
  if (learningMode.value === 'exploration') {
    const turnId = String(latestExplorationTurn.value?.turn_id || '').trim()
    if (turnId) {
      captureCurrentInteractionOutput(turnId, 'exploration')
      return
    }
  }

  if (learningMode.value === 'socratic') {
    const turnId = String(latestResponseRecord.value?.turn_id || '').trim()
    if (turnId) {
      captureCurrentInteractionOutput(turnId, 'socratic')
      return
    }
  }

  clearCurrentInteractionContext(learningMode.value)
}

const loadWorkspace = async () => {
  pageError.value = ''
  pageState.value = 'loading'
  clearActionError()
  const loaded = await fetchProblem()
  if (!loaded) {
    pageError.value = t('problemDetail.errorMessage')
    pageState.value = 'error'
    return
  }

  hydrateCurrentInteractionFromWorkspace()
  pageState.value = 'ready'
  await applyResumePathFromQuery()
  await scrollToReinforcementFocus()
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

onMounted(loadWorkspace)
</script>

<style scoped>
.problem-detail {
  max-width: 1180px;
  margin: 0 auto;
}

.back-link {
  display: inline-block;
  margin-bottom: 0;
  color: var(--text-muted);
  text-decoration: none;
}

.back-link:hover {
  color: var(--primary);
}

.problem-header {
  display: grid;
  gap: 0.35rem;
  margin-bottom: 0.9rem;
}

.problem-kicker {
  margin-bottom: 0;
  color: var(--primary);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.problem-frame-copy {
  margin-top: 0.15rem;
  color: var(--text-muted);
}

.problem-header h1 {
  margin: 0;
}

.problem-header p {
  margin: 0;
  color: var(--text-muted);
}

.problem-meta {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 0.35rem;
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

.workspace-primary-action-card {
  order: 1;
  border-color: rgba(96, 165, 250, 0.22);
  background: rgba(96, 165, 250, 0.06);
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
  order: 2;
  display: grid;
  gap: 1rem;
}

.workspace-context-card {
  order: 3;
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

.workspace-mainline-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
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

.workspace-mainline-card {
  background: rgba(255, 255, 255, 0.035);
}

.workspace-mainline-card strong {
  font-size: 1.02rem;
}

.workspace-next-action-card {
  border-color: rgba(74, 222, 128, 0.2);
  background: rgba(74, 222, 128, 0.06);
}

.workspace-status-strip {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.workspace-status-pill {
  padding: 0.75rem 0.85rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.015);
  display: grid;
  gap: 0.22rem;
}

.workspace-status-pill strong {
  line-height: 1.3;
}

.workspace-status-pill p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.84rem;
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

.workspace-action-error {
  margin: 0;
  padding: 0.8rem 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(248, 113, 113, 0.26);
  background: rgba(120, 24, 24, 0.14);
  color: #fecaca;
}

.protocol-note {
  margin: 0 0 1rem;
  padding: 0.75rem 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(96, 165, 250, 0.2);
  background: rgba(96, 165, 250, 0.08);
  color: var(--text-muted);
}

.workspace-artifacts-head {
  display: grid;
  gap: 0.35rem;
}

.workspace-artifacts-strip {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.workspace-current-output-empty {
  display: grid;
  gap: 0.35rem;
  padding: 0.9rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(96, 165, 250, 0.16);
  background: rgba(255, 255, 255, 0.03);
}

.workspace-current-output-empty p {
  color: var(--text-muted);
}

.turn-result-processing {
  display: grid;
  gap: 0.35rem;
  padding: 0.95rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(250, 204, 21, 0.24);
  background: rgba(250, 204, 21, 0.08);
}

.turn-result-processing p {
  margin: 0;
  color: var(--text-muted);
}

.turn-processing-support {
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.workspace-artifacts-actions {
  display: flex;
  justify-content: flex-start;
}

.workspace-artifacts-sections {
  display: grid;
  gap: 0.9rem;
}

.reinforcement-target-card {
  order: 4;
  border-color: rgba(248, 113, 113, 0.28);
  background: rgba(120, 24, 24, 0.16);
}

.current-step-section {
  order: 5;
}

.reinforcement-details {
  display: grid;
  gap: 0.9rem;
}

.reinforcement-summary {
  list-style: none;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  cursor: pointer;
}

.reinforcement-summary::-webkit-details-marker {
  display: none;
}

.reinforcement-details-body {
  display: grid;
  gap: 0.9rem;
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

.workspace-assets-details {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  padding: 0.9rem 1rem;
}

.workspace-assets-summary {
  list-style: none;
  cursor: pointer;
}

.workspace-assets-summary::-webkit-details-marker {
  display: none;
}

.workspace-assets-summary strong {
  display: block;
  line-height: 1.35;
}

.workspace-assets-summary p {
  margin-top: 0.25rem;
}

.workspace-assets-stack {
  display: grid;
  gap: 1rem;
  margin-top: 0.9rem;
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

.streaming-answer-panel {
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 10px;
  border: 1px solid rgba(251, 191, 36, 0.28);
  background: rgba(251, 191, 36, 0.08);
}

.streaming-answer-copy {
  margin: 0;
  white-space: pre-wrap;
}

.streaming-cursor {
  display: inline-block;
  margin-left: 0.12rem;
  animation: blink-cursor 0.9s steps(1) infinite;
}

@keyframes blink-cursor {
  0%,
  49% {
    opacity: 1;
  }

  50%,
  100% {
    opacity: 0;
  }
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

.problem-detail {
  display: grid;
  gap: 1rem;
}

.problem-learning-header,
.learning-contract-card,
.primary-turn-card,
.turn-result-card,
.postturn-card,
.secondary-tools-card,
.reinforcement-strip {
  display: grid;
  gap: 1rem;
}

.problem-learning-header {
  padding: 1.4rem;
}

.learning-header-copy {
  display: grid;
  gap: 0.35rem;
}

.learning-header-copy h1,
.learning-header-copy p {
  margin: 0;
}

.learning-header-status,
.contract-grid,
.postturn-summary-strip,
.secondary-tools-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.header-pill {
  padding: 0.9rem 1rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.03);
  display: grid;
  gap: 0.35rem;
}

.header-pill p {
  color: var(--text-muted);
}

.learning-header-controls {
  display: grid;
  gap: 0.45rem;
  justify-items: end;
}

.compact-mode-toggle {
  justify-content: flex-end;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.contract-grid .workspace-summary-card,
.postturn-summary-strip .workspace-summary-card {
  min-height: 100%;
}

.path-options-panel,
.postturn-details,
.secondary-detail {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  padding: 0.9rem 1rem;
}

.path-options-panel summary,
.postturn-details summary,
.secondary-detail summary {
  cursor: pointer;
  font-weight: 700;
  color: var(--text);
}

.path-options-panel[open],
.postturn-details[open],
.secondary-detail[open] {
  display: grid;
  gap: 0.85rem;
}

.contract-controls-panel {
  margin-top: 0.1rem;
}

.contract-controls-copy {
  margin: 0;
}

.contract-action-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.reinforcement-strip {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  padding: 1rem 1.1rem;
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(245, 158, 11, 0.06);
}

.reinforcement-strip-copy {
  display: grid;
  gap: 0.3rem;
}

.reinforcement-context-link {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}

.reinforcement-strip-actions {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.turn-step-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.9rem;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(74, 222, 128, 0.2);
  background: rgba(74, 222, 128, 0.05);
}

.turn-step-card h3,
.turn-step-card p {
  margin: 0;
}

.step-content {
  display: grid;
  gap: 0.35rem;
}

.secondary-actions-block {
  display: grid;
  gap: 0.85rem;
}

@media (max-width: 900px) {
  .learning-header-controls,
  .reinforcement-strip {
    grid-template-columns: 1fr;
    display: grid;
  }

  .learning-header-controls {
    justify-items: start;
  }

  .compact-mode-toggle {
    justify-content: flex-start;
  }

  .reinforcement-strip-actions {
    justify-content: flex-start;
  }
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
