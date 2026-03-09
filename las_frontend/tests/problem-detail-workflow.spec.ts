import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'

type Session = {
  username: string
  password: string
  accessToken: string
  refreshToken: string
  problemId: string
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
  }
}

async function openWorkspace(page: Page, problemId: string) {
  await page.goto(`/problems/${problemId}`)
  await expect(page.getByTestId('problem-detail-workspace')).toBeVisible()
  await expect(page.getByTestId('workspace-overview')).toBeVisible()
  await expect(page.getByTestId('workspace-path-summary')).toBeVisible()
  await expect(page.getByTestId('current-learning-path')).toContainText(/Main path/i)
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

    await expect(latestTurnOutcome(page)).toContainText(/Mastery Score/i)
    await expect(latestTurnOutcome(page)).toContainText(/Progression skipped/i)
    await expect(page.getByTestId('socratic-question-panel')).toContainText(/Checkpoint/i)

    await page.getByTestId('socratic-response-input').fill(
      'Checkpoint answer: lowering the threshold improves recall, raising it improves precision, and the choice depends on the cost of missing positives.',
    )
    await page.getByTestId('submit-socratic-response').click()

    await expect(latestTurnOutcome(page)).toContainText(/Advance/i)
    await expect(latestTurnOutcome(page)).toContainText(/Progression checked/i)
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

    await expect(latestTurnOutcome(page)).toContainText(/Comparison/i)
    await expect(latestTurnOutcome(page)).toContainText(/Precision measures/i)
    await expect(page.getByTestId('derived-concepts-panel')).toBeVisible()
    await page.getByTestId('workspace-note-input').fill('Capture the precision and recall tradeoff before branching.')
    await page.getByTestId('save-workspace-note').click()
    await expect(page.getByTestId('workspace-notes-panel')).toContainText(/Current turn/i)
    await expect(page.getByTestId('workspace-notes-panel')).toContainText(/precision and recall tradeoff/i)
    await page.getByTestId('workspace-resource-url').fill('https://example.com/precision-recall')
    await page.getByTestId('save-workspace-resource').click()
    await expect(page.getByTestId('workspace-resources-panel')).toContainText(/Current turn/i)
    await expect(page.getByTestId('workspace-resources-panel')).toContainText(/precision-recall/i)

    await page.getByTestId('accept-derived-concept').first().click()
    await expect(page.getByTestId('derived-concepts-panel')).toContainText(/Accepted/i)
    await page.getByTestId('promote-derived-concept').first().click()
    await expect(page.getByTestId('open-derived-concept-model-card').first()).toBeVisible()
    await page.getByTestId('schedule-derived-concept-review').first().click()
    await expect(page.getByTestId('derived-concept-review-scheduled').first()).toBeVisible()

    await page.getByTestId('path-candidates-panel').scrollIntoViewIfNeeded()
    await expect(page.getByTestId('path-candidate-card').first()).toBeVisible()
    await page.getByTestId('path-candidate-save-branch').first().click()

    await expect(page.getByTestId('current-learning-path')).toContainText(/Comparison branch/i)
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
