<template>
  <div class="problem-detail" data-testid="problem-detail-workspace">
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <template v-else-if="problem">
      <div class="problem-header">
        <router-link to="/problems" class="back-link">&larr; {{ t('common.back') }}</router-link>
        <p class="problem-kicker">{{ t('problemDetail.workspaceKicker') }}</p>
        <h1>{{ problem.title }}</h1>
        <p>{{ problem.description }}</p>
        <p class="problem-frame-copy">
          {{ learningMode === 'exploration' ? t('problemDetail.workspaceFrameExploration') : t('problemDetail.workspaceFrameSocratic') }}
        </p>
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
import { useAuthStore } from '@/stores/auth'
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
const workspaceNotes = ref<any[]>([])
const noteSaving = ref(false)
const workspaceResources = ref<any[]>([])
const resourceSaving = ref(false)
const resourceInterpretingId = ref<string | null>(null)
const latestQA = computed(() => {
  if (latestExplorationTurnId.value) {
    const exactTurn = qaHistory.value.find((turn: any) => String(turn.turn_id || '') === String(latestExplorationTurnId.value))
    if (exactTurn) return exactTurn
  }
  return qaHistory.value[0] || null
})

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
    return latestExplorationTurnId.value || latestQA.value?.turn_id || null
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
  reinforcementFocusDescription,
  reinforcementFocusTurnPreview,
  reinforcementActionTemplate,
  formatConfidence,
  formatRecommendedAction,
  formatReinforcementResume,
  hasReinforcementPath,
  formatReinforcementPath,
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

.problem-kicker {
  margin-bottom: 0.35rem;
  color: var(--primary);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.problem-frame-copy {
  color: var(--text-muted);
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
