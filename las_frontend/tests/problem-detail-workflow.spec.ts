import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'

type Session = {
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
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    problemId: problem.id,
  }
}

async function openWorkspace(page: Page, problemId: string) {
  await page.goto(`/problems/${problemId}`)
  await expect(page.getByTestId('problem-detail-workspace')).toBeVisible()
  await expect
    .poll(
      async () => {
        if (await page.getByTestId('problem-detail-error-state').count()) return 'error'
        if (await page.getByTestId('problem-learning-header').count()) return 'ready'
        return 'loading'
      },
      { timeout: 20000 },
    )
    .toBe('ready')
  await expect(page.getByTestId('problem-learning-header')).toBeVisible()
  await expect(page.getByTestId('problem-learning-contract')).toBeVisible()
  await expect(page.getByTestId('problem-turn-area')).toBeVisible()
  await expect(page.getByTestId('problem-turn-result')).toBeVisible()
  await expect(page.getByTestId('problem-postturn-decisions')).toBeVisible()
  await expect(page.getByTestId('problem-secondary-tools')).toBeVisible()
}

async function waitForSocraticTurnToSettle(page: Page) {
  await expect
    .poll(
      async () => {
        const processing = await page.getByTestId('turn-result-processing').count()
        if (!processing && await page.getByTestId('turn-result-status-card').count()) {
          const result = ((await page.getByTestId('problem-turn-result').textContent()) || '').trim()
          if (result.length > 0) return result
        }
        const preview = page.getByTestId('socratic-response-stream-preview')
        if (await preview.count()) {
          const text = ((await preview.first().textContent()) || '').trim()
          if (text.length > 0) return text
        }
        return ''
      },
      { timeout: 10000 },
    )
    .not.toBe('')
}

async function waitForExplorationTurnToSettle(page: Page) {
  await expect
    .poll(
      async () => {
        const processing = await page.getByTestId('turn-result-processing').count()
        const stillEmpty = await page.getByTestId('workspace-current-output-empty').count()
        if (!processing && !stillEmpty && await page.getByTestId('turn-result-status-card').count()) {
          const result = ((await page.getByTestId('problem-turn-result').textContent()) || '').trim()
          if (result.length > 0) return result
        }
        const preview = page.getByTestId('exploration-stream-preview')
        if (await preview.count()) {
          const text = ((await preview.first().textContent()) || '').trim()
          if (text.length > 0) return text
        }
        return ''
      },
      { timeout: 10000 },
    )
    .not.toBe('')
}

async function delayRoute(route: any, ms = 700) {
  await new Promise((resolve) => setTimeout(resolve, ms))
  await route.continue()
}

test.describe('ProblemDetail main workflow', () => {
  test('Scenario 1: Socratic flow keeps contract, action, and result in one rail', async ({ page, request }) => {
    // Contract Assertions:
    // - Critical Path: problem submission on the main learning workspace must remain operable.
    // - Base Button (.btn): mode switch and submit buttons stay clickable through the flow.
    // - Disabled State: async submit controls must remain stable while requests are in flight.
    const session = await prepareAuthenticatedProblem(page, request)
    await openWorkspace(page, session.problemId)
    await page.route(`**/api/problems/${session.problemId}/responses*`, (route) => delayRoute(route))

    await page.getByTestId('mode-switch-exploration').click()
    await expect(page.getByTestId('workspace-current-output-empty')).toBeVisible()
    await page.getByTestId('mode-switch-socratic').click()
    await expect(page.getByTestId('socratic-question-panel')).toContainText(/Probe/i)
    await expect(page.getByTestId('mark-step-done')).toHaveCount(0)
    await expect(page.getByTestId('socratic-protocol-note')).toBeVisible()

    await page.getByTestId('socratic-response-input').fill(
      'First probe answer: precision matters when false positives are expensive, but I still need to sharpen the threshold tradeoff.',
    )
    await page.getByTestId('submit-socratic-response').click()
    await expect(page.getByTestId('turn-result-processing')).toBeVisible()
    await waitForSocraticTurnToSettle(page)
    await expect(page.getByTestId('turn-result-status-card')).toBeVisible()
    await expect(page.getByTestId('turn-result-gap-card')).toBeVisible()
    await expect(page.getByTestId('turn-result-next-card')).toBeVisible()
    await expect(page.getByTestId('problem-postturn-decisions')).toContainText(/concept|path|review/i)

    await page.getByTestId('socratic-response-input').fill(
      'Checkpoint answer: lowering the threshold improves recall, raising it improves precision, and the choice depends on the cost of missing positives.',
    )
    await page.getByTestId('submit-socratic-response').click()
    await expect(page.getByTestId('turn-result-processing')).toBeVisible()
    await waitForSocraticTurnToSettle(page)
    const undoAutoAdvance = page.getByRole('button', { name: /Undo Auto-Advance/i })
    if (await undoAutoAdvance.count()) {
      await expect(undoAutoAdvance).toBeVisible()
    } else {
      await expect(page.getByTestId('turn-result-status-card')).toBeVisible()
    }

    const history = page.getByTestId('problem-secondary-tools')
    await history.getByText(/History \(/i).click()
    await expect(page.getByTestId('socratic-history-item').first()).toContainText(/Checkpoint answer:|Question:/i)
  })

  test('Scenario 2: Exploration turn shows result before concept and path governance', async ({ page, request }) => {
    // Contract Assertions:
    // - Critical Path: exploration submission must keep result and follow-up decisions on the same page.
    // - Base Button (.btn): exploration submit and post-turn decision buttons remain operable.
    const session = await prepareAuthenticatedProblem(page, request)
    await openWorkspace(page, session.problemId)
    await page.route(`**/api/problems/${session.problemId}/ask*`, (route) => delayRoute(route))

    await page.getByTestId('mode-switch-exploration').click()
    await expect(page.getByTestId('workspace-current-output-empty')).toBeVisible()
    await page.getByTestId('exploration-question-input').fill('What is the difference between precision and recall?')
    await page.getByTestId('submit-exploration-question').click()

    await expect(page.getByTestId('turn-result-processing')).toBeVisible()
    await waitForExplorationTurnToSettle(page)
    await expect(page.getByTestId('workspace-current-output-empty')).toHaveCount(0)
    await expect(page.getByTestId('turn-result-status-card')).toBeVisible()
    await expect(page.getByTestId('turn-result-gap-card')).toBeVisible()
    await expect(page.getByTestId('turn-result-next-card')).toBeVisible()
    await expect(page.getByTestId('problem-postturn-decisions')).toBeVisible()

    const conceptDetails = page.getByTestId('problem-postturn-decisions').locator('details').nth(0)
    if (!(await conceptDetails.evaluate((node) => (node as HTMLDetailsElement).open))) {
      await conceptDetails.locator('summary').click()
    }

    const visibleAcceptButton = page.getByTestId('accept-derived-concept').locator(':visible').first()
    if (await visibleAcceptButton.count()) {
      await visibleAcceptButton.click()
      await expect(page.getByTestId('problem-postturn-decisions')).toContainText(/Accepted/i)
    }

    const pathDetails = page.getByTestId('problem-postturn-decisions').locator('details').nth(1)
    if (!(await pathDetails.evaluate((node) => (node as HTMLDetailsElement).open))) {
      await pathDetails.locator('summary').click()
    }
    const visiblePathCard = page.getByTestId('path-candidate-card').locator(':visible').first()
    if (await visiblePathCard.count()) {
      await expect(visiblePathCard).toBeVisible()
    }

    await page.getByTestId('workspace-assets-toggle').click()
    await page.getByTestId('workspace-note-input').fill('Capture the precision and recall tradeoff before branching.')
    await page.getByTestId('save-workspace-note').click()
    await expect(page.getByTestId('workspace-assets-panel')).toContainText('precision and recall tradeoff')
  })
})
