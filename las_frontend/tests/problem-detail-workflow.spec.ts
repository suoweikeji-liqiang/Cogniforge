import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'

type Session = {
  username: string
  password: string
  accessToken: string
  refreshToken: string
  problemId: string
  problemTitle: string
}

async function prepareAuthenticatedProblem(page: Page, request: APIRequestContext): Promise<Session> {
  const suffix = randomUUID().slice(0, 8)
  const username = `e2e_${suffix}`
  const password = 'password123'
  const email = `${username}@example.com`

  const registerResponse = await request.post('/api/auth/register', {
    data: {
      email,
      username,
      password,
      full_name: 'E2E User',
    },
  })
  expect(registerResponse.ok()).toBeTruthy()

  const loginResponse = await request.post('/api/auth/login', {
    form: {
      username,
      password,
    },
  })
  expect(loginResponse.ok()).toBeTruthy()
  const tokens = await loginResponse.json()

  const problemResponse = await request.post('/api/problems/', {
    headers: {
      Authorization: `Bearer ${tokens.access_token}`,
    },
    data: {
      title: `E2E Metrics ${suffix}`,
      description: 'Practice metric tradeoffs during the main workspace flow.',
      associated_concepts: ['precision', 'recall'],
      learning_mode: 'socratic',
    },
  })
  expect(problemResponse.ok()).toBeTruthy()
  const problem = await problemResponse.json()

  await page.addInitScript(
    ([accessToken, refreshToken]) => {
      window.localStorage.setItem('locale', 'en')
      window.localStorage.setItem('token', accessToken)
      window.localStorage.setItem('refresh_token', refreshToken)
    },
    [tokens.access_token, tokens.refresh_token],
  )

  return {
    username,
    password,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    problemId: problem.id,
    problemTitle: problem.title,
  }
}

async function openWorkspace(page: Page, problemId: string) {
  await page.goto(`/problems/${problemId}`)
  await expect(page.getByTestId('problem-detail-workspace')).toBeVisible()
  await expect(page.getByTestId('workspace-overview')).toBeVisible()
  await expect(page.getByTestId('workspace-mainline-focus')).toBeVisible()
  await expect(page.getByTestId('workspace-next-action')).toBeVisible()
  await expect(page.getByTestId('workspace-primary-action')).toBeVisible()
  await expect(page.getByTestId('workspace-path-summary')).toBeVisible()
  await expect(page.getByTestId('workspace-artifacts-panel')).toBeVisible()
  await expect(page.getByTestId('current-learning-path')).toContainText(/Main path/i)
  const actionBox = await page.getByTestId('workspace-primary-action').boundingBox()
  const viewport = page.viewportSize()
  expect(actionBox).not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(actionBox!.y).toBeLessThan((viewport!.height || 0) * 0.8)
}

function latestTurnOutcome(page: Page) {
  return page.getByTestId('turn-outcome-panel').last()
}

test.describe('ProblemDetail main workflow', () => {
  test('Scenario 1: Socratic probe then checkpoint progression', async ({ page, request }) => {
    // Contract Assertions:
    // - Critical Path: problem submission on the main learning workspace must remain operable.
    // - Base Button (.btn): mode switch and submit buttons stay clickable through the flow.
    // - Disabled State: async submit controls must remain stable while requests are in flight.
    const session = await prepareAuthenticatedProblem(page, request)
    await openWorkspace(page, session.problemId)

    await page.getByTestId('mode-switch-socratic').click()
    await expect(page.getByTestId('socratic-question-panel')).toContainText(/Probe/i)

    await page.getByTestId('socratic-response-input').fill(
      'First probe answer: precision matters when false positives are expensive, but I still need to sharpen the threshold tradeoff.',
    )
    await page.getByTestId('submit-socratic-response').click()
    await expect(page.getByTestId('socratic-response-stream-preview')).toBeVisible()
    await expect(page.getByTestId('socratic-response-stream-preview')).toContainText(/Assessing|Mastery preview/i)

    await expect(latestTurnOutcome(page)).toContainText(/Mastery Score/i)
    await expect(latestTurnOutcome(page)).toContainText(/Progression skipped/i)
    await expect(page.getByTestId('socratic-question-panel')).toContainText(/Checkpoint/i)

    await page.getByTestId('socratic-response-input').fill(
      'Checkpoint answer: lowering the threshold improves recall, raising it improves precision, and the choice depends on the cost of missing positives.',
    )
    await page.getByTestId('submit-socratic-response').click()
    await expect(page.getByTestId('socratic-response-stream-preview')).toBeVisible()

    await expect(latestTurnOutcome(page)).toContainText(/Advance/i)
    await expect(latestTurnOutcome(page)).toContainText(/Progression checked/i)
    await page.getByText(/History \(/i).click()
    await expect(page.getByTestId('socratic-history-item').first()).toContainText(/Checkpoint answer:/i)
    await expect(page.getByTestId('socratic-history-item').first()).toContainText(/Question:/i)
    await expect(page.getByTestId('problem-detail-workspace')).toContainText(/Threshold decisions/i)
  })

  test('Scenario 2: Exploration turn surfaces derived concepts and branch creation', async ({ page, request }) => {
    // Contract Assertions:
    // - Critical Path: data submission on the main workspace must stay protected.
    // - Base Button (.btn): exploration submit and branch-action buttons remain actionable.
    // - Disabled State: candidate decision buttons stay deterministic during async updates.
    const session = await prepareAuthenticatedProblem(page, request)
    await openWorkspace(page, session.problemId)

    await page.getByTestId('mode-switch-exploration').click()
    await page.getByTestId('exploration-question-input').fill('What is the difference between precision and recall?')
    await page.getByTestId('submit-exploration-question').click()

    await expect(page.getByTestId('exploration-stream-preview')).toBeVisible()
    await expect(page.getByTestId('exploration-stream-preview')).toContainText(/Streaming answer|drafting the explanation/i)
    await expect(latestTurnOutcome(page)).toContainText(/Comparison/i)
    await expect(latestTurnOutcome(page)).toContainText(/Precision measures/i)
    await expect(page.getByTestId('exploration-stream-preview')).toBeHidden()
    await expect(page.getByTestId('workspace-artifact-concept-count')).toContainText(/[1-9]/)
    await expect(page.getByTestId('derived-concepts-panel')).toBeVisible()
    await page.getByTestId('workspace-assets-toggle').click()
    await page.getByTestId('workspace-note-input').fill('Capture the precision and recall tradeoff before branching.')
    await page.getByTestId('save-workspace-note').click()
    await expect(page.getByTestId('workspace-notes-panel')).toContainText(/Current turn/i)
    await expect(page.getByTestId('workspace-notes-panel')).toContainText(/precision and recall tradeoff/i)
    await page.getByTestId('workspace-resource-url').fill('https://example.com/precision-recall')
    await page.getByTestId('save-workspace-resource').click()
    await expect(page.getByTestId('workspace-resources-panel')).toContainText(/Current turn/i)
    await expect(page.getByTestId('workspace-resources-panel')).toContainText(/precision-recall/i)
    await page.getByTestId('workspace-notes-panel').getByRole('button', { name: /Delete/i }).click()
    await expect(page.getByTestId('workspace-notes-panel')).not.toContainText(/precision and recall tradeoff/i)
    await page.getByTestId('workspace-resources-panel').getByRole('button', { name: /Delete/i }).click()
    await expect(page.getByTestId('workspace-resources-panel')).not.toContainText(/precision-recall/i)

    await page.getByTestId('path-candidates-panel').scrollIntoViewIfNeeded()
    await expect(page.getByTestId('path-candidate-card').first()).toBeVisible()
    await page.getByTestId('path-candidate-save-branch').first().click()
    await expect(page.getByTestId('current-learning-path')).toContainText(/Comparison branch/i)

    await page.getByTestId('exploration-question-input').fill('How should I compare precision and recall when the threshold moves?')
    await page.getByTestId('submit-exploration-question').click()
    await expect(latestTurnOutcome(page)).toContainText(/Comparison|Concept explanation/i)

    const branchCandidate = page.getByTestId('derived-concept-card').filter({
      hasText: /false negatives/i,
    }).first()
    await expect(branchCandidate).toBeVisible()
    await branchCandidate.getByTestId('accept-derived-concept').click()
    await expect(page.getByTestId('derived-concepts-panel')).toContainText(/Accepted/i)
    await page.getByTestId('promote-derived-concept').first().click()
    await expect(page.getByTestId('open-derived-concept-model-card').first()).toBeVisible()
    await page.getByTestId('schedule-derived-concept-review').first().click()
    await expect(page.getByTestId('derived-concept-review-scheduled').first()).toBeVisible()
    await expect(page.getByTestId('workspace-review-summary')).toContainText(/entered recall|in recall/i)
    await expect(page.getByTestId('workspace-review-summary')).toContainText(/next recall|last reviewed/i)

    const schedulesResponse = await request.get('/api/srs/schedules', {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    })
    expect(schedulesResponse.ok()).toBeTruthy()
    const schedules = await schedulesResponse.json()
    expect(schedules.length).toBeGreaterThan(0)

    const firstSchedule = schedules[0]
    const reviewResponse = await request.post(`/api/srs/review/${firstSchedule.schedule_id}?quality=0`, {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    })
    expect(reviewResponse.ok()).toBeTruthy()

    await page.goto(`/problems/${session.problemId}`)
    await expect(page.getByTestId('workspace-review-summary')).toContainText(/fragile|reinforcement/i)
    await expect(page.getByTestId('workspace-review-summary')).toContainText(/revisit|reinforce/i)
    await expect(page.getByTestId('derived-concepts-older')).toBeVisible()
    await expect(page.getByTestId('workspace-reinforcement-target')).toContainText(/Needs reinforcement|Reinforcement Target/i)
    await expect(page.getByTestId('workspace-reinforcement-target')).toContainText(/Comparison branch|Branch path/i)
    await page.getByTestId('reinforcement-details-toggle').click()
    await expect(page.getByTestId('workspace-reinforcement-focus')).toContainText(/Focus first|Focus target|false negatives/i)
    await expect(page.getByTestId('workspace-reinforcement-action')).toContainText(/Do this first|Compare/i)
    await expect(page.getByTestId('reinforcement-starter-source-cue')).toContainText(/precision and recall when the threshold moves/i)
    await expect(page.getByTestId('reinforcement-likely-confusion')).toContainText(/move together|tradeoff/i)
    await expect(page.getByTestId('reinforcement-starter-evidence')).toContainText(/false negatives usually drop while false positives rise/i)
    await expect(page.getByTestId('derived-concepts-panel')).toContainText(/Fragile|revisit the workspace/i)
    await expect(page.getByTestId('derived-concept-needs-reinforcement').first()).toContainText(/Needs reinforcement|Comparison branch/i)
    await expect(page.getByTestId('derived-concept-focus-target')).toContainText(/false negatives/i)

    await page.goto(`/model-cards/${firstSchedule.model_card_id}`)
    await expect(page.getByTestId('model-card-recall-status')).toContainText(/Fragile|rebuilding/i)
    await expect(page.getByTestId('model-card-recall-status')).toContainText(/revisit|reinforce/i)
    await expect(page.getByTestId('model-card-evolution-state')).toContainText(/Needs revision|Rebuilding/i)
    await expect(page.getByTestId('model-card-evolution-state')).toContainText(/before extending|workspace/i)
    await expect(page.getByTestId('model-card-revision-focus')).toContainText(/Revisit comparison|comparison/i)
    await expect(page.getByTestId('model-card-revision-focus')).toContainText(/threshold|tradeoff/i)
    await expect(page.getByTestId('model-card-reinforcement-target')).toContainText(/Needs reinforcement|Comparison branch/i)
    await page.getByRole('link', { name: 'Open Workspace' }).first().click()
    await expect(page.getByTestId('current-learning-path')).toContainText(/Comparison branch/i)
    await expect(page.getByTestId('workspace-reinforcement-target')).toContainText(/Comparison branch/i)
    await page.getByTestId('reinforcement-details-toggle').click()
    await expect(page.getByTestId('workspace-reinforcement-focus')).toContainText(/Focus first|Focus target/i)
    await expect(page.getByTestId('derived-concept-focus-target')).toContainText(/false negatives/i)
    await expect(page.getByTestId('workspace-reinforcement-action')).toContainText(/Compare/i)
    await page.getByTestId('apply-reinforcement-action-template').click()
    await expect(page.getByTestId('socratic-response-input')).toHaveValue(/false negatives usually drop while false positives rise/i)
    await expect(page.getByTestId('socratic-response-input')).toHaveValue(/false negatives/i)
    await expect(page.getByTestId('socratic-response-input')).toHaveValue(/move together|tradeoff/i)

    await page.goto('/model-cards')
    await expect(page.getByTestId('model-card-list-evolution-state').first()).toContainText(/Needs revision|Rebuilding/i)
    await expect(page.getByTestId('model-card-list-evolution-state').first()).toContainText(/before extending|workspace/i)

    await page.goto('/reviews')
    await expect(page.getByTestId('review-model-cards-panel')).toContainText(session.problemTitle)
    await expect(page.getByTestId('review-model-cards-panel')).toContainText(/exploration-derived concept|exploration/i)
  })

  test('Scenario 2b: Exploration stream refreshes auth and retries before falling back', async ({ page, request }) => {
    // Contract Assertions:
    // - Critical Path: exploration ask should survive a one-off 401 at the streaming boundary.
    // - Critical Path: auth refresh should restore the stream instead of silently dropping to the blocking endpoint.
    const session = await prepareAuthenticatedProblem(page, request)
    await openWorkspace(page, session.problemId)

    let streamAttempts = 0
    let refreshCalls = 0
    let fallbackAskCalls = 0

    await page.route(`**/api/problems/${session.problemId}/ask/stream`, async (route) => {
      streamAttempts += 1
      if (streamAttempts === 1) {
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Token expired during stream setup.' }),
        })
        return
      }
      await route.continue()
    })

    await page.route('**/api/auth/refresh', async (route) => {
      refreshCalls += 1
      await route.continue()
    })

    await page.route(`**/api/problems/${session.problemId}/ask`, async (route) => {
      fallbackAskCalls += 1
      await route.continue()
    })

    await page.getByTestId('mode-switch-exploration').click()
    await page.getByTestId('exploration-question-input').fill('Explain precision and recall with one concrete threshold example.')
    await page.getByTestId('submit-exploration-question').click()

    await expect(page.getByTestId('exploration-stream-preview')).toBeVisible()
    await expect(page.getByTestId('exploration-stream-preview')).toContainText(/Streaming answer|drafting the explanation/i)
    await expect(latestTurnOutcome(page)).toContainText(/Answered Concepts|Pending Concept Candidates|Path Suggestions/i)
    await expect(page.getByTestId('exploration-stream-preview')).toBeHidden()
    await expect(page.getByTestId('derived-concepts-panel')).toBeVisible()

    expect(streamAttempts).toBe(2)
    expect(refreshCalls).toBeGreaterThanOrEqual(1)
    expect(fallbackAskCalls).toBe(0)
  })

  test('Scenario 2c: Derived concept evidence renders markdown formatting', async ({ page, request }) => {
    const session = await prepareAuthenticatedProblem(page, request)

    await page.route(`**/api/problems/${session.problemId}/concept-candidates`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'candidate-markdown',
            problem_id: session.problemId,
            concept_text: '比例',
            normalized_text: '比例',
            source: 'ask',
            learning_mode: 'exploration',
            source_turn_id: 'turn-markdown',
            source_turn_preview: 'PID中的比例、微分和积分是什么',
            confidence: 0.74,
            status: 'pending',
            evidence_snippet:
              '1. **简洁定义**\n- **比例（P）**：根据当前误差大小成比例地调整控制输出。\n- **积分（I）**：累积过去所有误差。',
            merged_into_concept: null,
            linked_model_card_id: null,
            reviewed_at: null,
            created_at: new Date().toISOString(),
          },
        ]),
      })
    })

    await openWorkspace(page, session.problemId)
    await expect(page.getByTestId('derived-concepts-panel')).toBeVisible()

    const evidence = page.getByTestId('derived-concept-evidence').first()
    await expect(evidence).toBeVisible()
    await expect(evidence.locator('strong').first()).toHaveText('简洁定义')
    await expect(evidence.locator('strong').nth(1)).toHaveText('比例（P）')
    await expect(evidence).toContainText('积分（I）')
    await expect(evidence).not.toContainText('**简洁定义**')
  })

  test('Scenario 3: Branch path can return to the main path', async ({ page, request }) => {
    // Contract Assertions:
    // - Critical Path: branch navigation and return-to-main must remain visible and reversible.
    // - Base Button (.btn): branch navigation buttons remain interactive after path activation.
    // - Critical Path: step-completion on a branch must not strand the learner away from main flow.
    const session = await prepareAuthenticatedProblem(page, request)
    await openWorkspace(page, session.problemId)

    await page.getByTestId('mode-switch-exploration').click()
    await page.getByTestId('exploration-question-input').fill('What is the difference between precision and recall?')
    await page.getByTestId('submit-exploration-question').click()

    await page.getByTestId('path-candidates-panel').scrollIntoViewIfNeeded()
    await page.getByTestId('path-candidate-save-branch').first().click()
    await expect(page.getByTestId('current-learning-path')).toContainText(/Comparison branch/i)

    await page.getByTestId('mark-step-done').click()
    await expect(page.getByTestId('problem-detail-workspace')).toContainText(/Compare/i)

    await page.getByTestId('return-to-parent-path').click()
    await expect(page.getByTestId('current-learning-path')).toContainText(/Main path/i)
  })
})
