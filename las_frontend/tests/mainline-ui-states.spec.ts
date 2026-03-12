import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page, Route } from '@playwright/test'
import { randomUUID } from 'node:crypto'

async function authenticate(page: Page, request: APIRequestContext) {
  const suffix = randomUUID().slice(0, 8)
  const username = `mainline_${suffix}`
  const password = 'password123'
  const email = `${username}@example.com`

  const registerResponse = await request.post('/api/auth/register', {
    data: {
      email,
      username,
      password,
      full_name: 'Mainline E2E User',
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

  await page.addInitScript(
    ([accessToken, refreshToken]) => {
      window.localStorage.setItem('locale', 'en')
      window.localStorage.setItem('token', accessToken)
      window.localStorage.setItem('refresh_token', refreshToken)
    },
    [tokens.access_token, tokens.refresh_token],
  )

  return tokens as { access_token: string; refresh_token: string }
}

async function createProblem(request: APIRequestContext, accessToken: string, title: string) {
  const response = await request.post('/api/problems/', {
    data: {
      title,
      description: 'Problem detail framing context',
      associated_concepts: ['threshold'],
    },
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function failOnce(route: Route, attempts: { value: number }) {
  attempts.value += 1
  if (attempts.value === 1) {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Injected mainline failure.' }),
    })
    return true
  }
  return false
}

async function openCreateProblemModal(page: Page, title: string) {
  await page.getByRole('button', { name: /New Problem/i }).click()
  const modal = page.locator('.modal').first()
  await modal.locator('.form-group').nth(0).locator('input').fill(title)
  await modal.locator('.form-group').nth(1).locator('textarea').fill('Created from the Problems library flow.')
  await modal.locator('.form-group').nth(2).locator('input').fill('precision, recall')
  await modal.getByRole('button', { name: /^Add$/i }).click()
}

test('dashboard shows a retryable error state during init failure', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: dashboard navigation must fail visibly instead of collapsing into an empty state.
  // - Base Button (.btn): retry controls remain visible and operable on the error surface.
  const attempts = { value: 0 }
  await authenticate(page, request)
  await page.route('**/api/srs/due', async (route) => {
    if (await failOnce(route, attempts)) return
    await route.continue()
  })

  await page.goto('/dashboard')
  await expect(page.getByTestId('dashboard-error-state')).toBeVisible()
  await page.getByTestId('dashboard-error-retry').click()
  await expect(page.getByTestId('dashboard-focus-card')).toBeVisible()
})

test('problem list shows a retryable error state during init failure', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: problem-library browsing must fail visibly instead of pretending there are no problems.
  // - Base Button (.btn): retry controls remain visible and operable on the error surface.
  const attempts = { value: 0 }
  await authenticate(page, request)
  await page.route('**/api/problems/**', async (route) => {
    if (!route.request().url().includes('/api/problems/') || route.request().method() !== 'GET') {
      await route.continue()
      return
    }
    if (await failOnce(route, attempts)) return
    await route.continue()
  })

  await page.goto('/problems')
  await expect(page.getByTestId('problems-error-state')).toBeVisible()
  await page.getByTestId('problems-error-retry').click()
  await expect(page.getByRole('button', { name: /New Problem/i })).toBeVisible()
  await expect(page.getByTestId('problems-error-state')).toHaveCount(0)
})

test('reviews show a retryable error state during init failure', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: review planning must fail visibly instead of misreporting an empty queue.
  // - Base Button (.btn): retry controls remain visible and operable on the error surface.
  const attempts = { value: 0 }
  await authenticate(page, request)
  await page.route('**/api/reviews/', async (route) => {
    if (await failOnce(route, attempts)) return
    await route.continue()
  })

  await page.goto('/reviews')
  await expect(page.getByTestId('reviews-error-state')).toBeVisible()
  await page.getByTestId('reviews-error-retry').click()
  await expect(page.getByTestId('reviews-focus-card')).toBeVisible()
})

test('srs review shows a retryable error state during init failure', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: active recall must fail visibly instead of presenting a false completion state.
  // - Base Button (.btn): retry controls remain visible and operable on the error surface.
  const attempts = { value: 0 }
  await authenticate(page, request)
  await page.route('**/api/srs/due', async (route) => {
    if (await failOnce(route, attempts)) return
    await route.continue()
  })

  await page.goto('/srs-review')
  await expect(page.getByTestId('srs-error-state')).toBeVisible()
  await expect(page.getByText(/All reviews done for today!/i)).toHaveCount(0)
  await page.getByTestId('srs-error-retry').click()
  await expect(page.getByText(/Due Today/i)).toBeVisible()
})

test('problem detail shows a retryable error state during init failure', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: opening the main learning workspace must fail visibly instead of rendering a blank shell.
  // - Base Button (.btn): retry controls remain visible and operable on the error surface.
  const attempts = { value: 0 }
  const tokens = await authenticate(page, request)
  const problem = await createProblem(request, tokens.access_token, `Failure ${randomUUID().slice(0, 6)}`)

  await page.route(`**/api/problems/${problem.id}`, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue()
      return
    }
    if (await failOnce(route, attempts)) return
    await route.continue()
  })

  await page.goto(`/problems/${problem.id}`)
  await expect(page.getByTestId('problem-detail-error-state')).toBeVisible()
  await page.getByTestId('problem-detail-error-retry').click()
  await expect(page.getByTestId('workspace-overview')).toBeVisible()
})

test('problem creation can pause at the mode chooser and keep the user on the list', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: problem creation must preserve a clear next decision before entering the workspace.
  // - Base Button (.btn): chooser actions remain visible and operable after problem creation.
  const title = `Chooser ${randomUUID().slice(0, 6)}`
  await authenticate(page, request)
  await page.goto('/problems')

  await openCreateProblemModal(page, title)
  await expect(page.getByTestId('problem-start-mode-chooser')).toBeVisible()
  await page.getByRole('button', { name: /Close/i }).click()

  await expect(page).toHaveURL(/\/problems$/)
  await expect(page.getByTestId('problem-start-mode-chooser')).toHaveCount(0)
  await expect(page.getByText(title)).toBeVisible()
})

test('problem creation can enter the workspace directly in exploration mode', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: problem creation must support choosing the exploration protocol before workspace entry.
  // - Base Button (.btn): chooser actions remain visible and operable after problem creation.
  const title = `Exploration ${randomUUID().slice(0, 6)}`
  await authenticate(page, request)
  await page.goto('/problems')

  await openCreateProblemModal(page, title)
  await expect(page.getByTestId('problem-start-mode-chooser')).toBeVisible()
  await page.getByTestId('problem-start-mode-exploration').click()

  await expect(page).toHaveURL(/\/problems\/.+/)
  await expect(page.getByTestId('problem-start-mode-chooser')).toHaveCount(0)
  await expect(page.getByTestId('mode-switch-exploration')).toHaveClass(/active/)
})
