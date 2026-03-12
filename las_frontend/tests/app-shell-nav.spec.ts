import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'

async function authenticate(page: Page, request: APIRequestContext) {
  const suffix = randomUUID().slice(0, 8)
  const username = `nav_${suffix}`
  const password = 'password123'
  const email = `${username}@example.com`

  const registerResponse = await request.post('/api/auth/register', {
    data: {
      email,
      username,
      password,
      full_name: 'Nav E2E User',
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

async function createModelCard(request: APIRequestContext, accessToken: string, title: string) {
  const response = await request.post('/api/model-cards/', {
    data: {
      title,
      user_notes: 'Model card review context',
      examples: ['example'],
    },
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(response.ok()).toBeTruthy()
  const card = await response.json()

  const activateResponse = await request.post(`/api/model-cards/${card.id}/activate`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(activateResponse.ok()).toBeTruthy()
  return activateResponse.json()
}

async function createProblem(request: APIRequestContext, accessToken: string, title: string) {
  const response = await request.post('/api/problems/', {
    data: {
      title,
      description: 'Problem detail framing context',
      associated_concepts: ['threshold'],
      learning_mode: 'exploration',
    },
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function scheduleReview(request: APIRequestContext, accessToken: string, modelCardId: string) {
  const response = await request.post(`/api/srs/schedule/${modelCardId}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function createReview(request: APIRequestContext, accessToken: string) {
  const response = await request.post('/api/reviews/', {
    data: {
      review_type: 'weekly',
      period: 'Week 1',
      content: {
        summary: 'Review archive summary',
        insights: 'Review archive insight',
        next_steps: 'Review archive next steps',
        misconceptions: ['Review archive misconception'],
      },
    },
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(response.ok()).toBeTruthy()
}

test('primary navigation stays focused on the learning loop', async ({ page, request }) => {
  await authenticate(page, request)
  await page.goto('/dashboard')

  await expect(page.getByTestId('resume-dashboard')).toBeVisible()
  const primaryNav = page.getByTestId('primary-nav')
  await expect(primaryNav.getByTestId('primary-nav-item-home')).toBeVisible()
  await expect(primaryNav.getByTestId('primary-nav-item-home')).toContainText(/Continue Learning/i)
  await expect(primaryNav.getByTestId('primary-nav-item-problems')).toBeVisible()
  await expect(primaryNav.getByTestId('primary-nav-item-review')).toBeVisible()
  await expect(primaryNav.getByTestId('primary-nav-item-model-cards')).toHaveCount(0)

  await expect(primaryNav.getByTestId('primary-nav-item-practice')).toHaveCount(0)
  await expect(primaryNav.getByTestId('primary-nav-item-chat')).toHaveCount(0)
  await expect(primaryNav.getByTestId('primary-nav-item-srs-review')).toHaveCount(0)
  await expect(page.getByTestId('continue-focus-card')).toBeVisible()
  await expect(page.getByTestId('dashboard-problems-panel')).toBeVisible()
  await expect(page.getByTestId('dashboard-review-panel')).toBeVisible()
  await expect(page.getByTestId('dashboard-model-cards-panel')).toHaveCount(0)
  await expect(page.locator('a[href="/model-cards"]').first()).toHaveCount(0)
})

test('admin llm config stays on the admin route after a hard refresh', async ({ page, request }) => {
  await authenticate(page, request)

  await page.route('**/api/auth/me', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 250))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'admin-test-user',
        email: 'admin@example.com',
        username: 'admin-test',
        full_name: 'Admin Test',
        role: 'admin',
        is_active: true,
      }),
    })
  })

  await page.route('**/api/admin/llm-config/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  })

  await page.route('**/api/admin/llm-config/routes', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        interactive: { provider_id: null, model_record_id: null },
        structured_heavy: { provider_id: null, model_record_id: null },
        fallback: { provider_id: null, model_record_id: null },
      }),
    })
  })

  await page.goto('/admin/llm-config')
  await expect(page).toHaveURL(/\/admin\/llm-config$/)
  await expect(page.getByRole('heading', { name: /LLM Configuration|LLM 配置/i })).toBeVisible()
  await expect(page.getByTestId('primary-nav-item-admin')).toBeVisible()

  await page.reload()

  await expect(page).toHaveURL(/\/admin\/llm-config$/)
  await expect(page.getByRole('heading', { name: /LLM Configuration|LLM 配置/i })).toBeVisible()
  await expect(page.getByTestId('primary-nav-item-admin')).toBeVisible()
})

test('standalone chat is marked as a secondary legacy surface', async ({ page, request }) => {
  await authenticate(page, request)
  await page.goto('/chat')

  await expect(page.getByTestId('legacy-chat-banner')).toBeVisible()
  await expect(page.getByText(/outside the primary learning loop/i)).toBeVisible()
  await expect(page.getByRole('link', { name: /Go to Problems/i })).toBeVisible()
})

test('login and register pages keep auth controls compact and avoid shell overflow', async ({ page }) => {
  // Contract Assertions:
  // - Critical Path: login/signup must remain usable as an entry point into the learning loop.
  // - Base Button (.btn): primary auth submit buttons remain visible and operable on first load.
  await page.goto('/login')

  await expect(page.getByRole('heading', { name: /Login|登录/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /Login|登录/i })).toBeVisible()

  const loginOverflow = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)
  expect(loginOverflow).toBeLessThanOrEqual(4)

  const checkboxes = page.locator('input[type="checkbox"]')
  await expect(checkboxes).toHaveCount(2)
  for (let index = 0; index < 2; index += 1) {
    const box = await checkboxes.nth(index).boundingBox()
    expect(box?.width ?? 0).toBeLessThan(24)
    expect(box?.height ?? 0).toBeLessThan(24)
  }

  await page.goto('/register')

  await expect(page.getByRole('heading', { name: /Register|注册/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /Register|注册/i })).toBeVisible()

  const registerOverflow = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)
  expect(registerOverflow).toBeLessThanOrEqual(4)
})

test('reviews page centers review execution and workspace return', async ({ page, request }) => {
  const tokens = await authenticate(page, request)
  const problem = await createProblem(request, tokens.access_token, 'Review Hub Problem')
  const card = await createModelCard(request, tokens.access_token, 'Review Hub Card')
  await scheduleReview(request, tokens.access_token, card.id)
  await createReview(request, tokens.access_token)

  await page.route('**/api/srs/due', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          schedule_id: 'due-card-review-hub',
          model_card_id: card.id,
          title: card.title,
          user_notes: card.user_notes,
          next_review_at: new Date().toISOString(),
          origin: {
            problem_id: problem.id,
            problem_title: 'Review Hub Problem',
            concept_text: card.title,
            learning_mode: 'exploration',
          },
        },
      ]),
    })
  })

  await page.route('**/api/srs/schedules', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          schedule_id: 'reinforcement-review-hub',
          model_card_id: card.id,
          title: card.title,
          needs_reinforcement: true,
          recall_state: 'fragile',
          recommended_action: 'revisit_workspace',
          last_reviewed_at: new Date().toISOString(),
          origin: {
            problem_id: problem.id,
            problem_title: 'Review Hub Problem',
            concept_text: card.title,
            learning_mode: 'exploration',
          },
        },
      ]),
    })
  })

  await page.goto('/reviews')

  await expect(page.getByTestId('review-lifecycle-page')).toBeVisible()
  await expect(page.getByTestId('reviews-focus-card')).toHaveAttribute('href', '/srs-review')
  await expect(page.getByTestId('reviews-due-queue')).toContainText('Review Hub Card')
  await expect(page.getByTestId('reviews-reinforcement-panel')).toContainText(/Source:|Current state:|Suggested action:/)
  await expect(page.getByRole('button', { name: /New Review/i })).toHaveCount(0)
  await expect(page.getByText(/Generate with AI/i)).toHaveCount(0)
  await page.getByTestId('review-archive-toggle').click()
  await expect(page.getByTestId('review-archive-panel')).toContainText('Review archive summary')
})
