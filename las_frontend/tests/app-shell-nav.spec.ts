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
  return response.json()
}

async function scheduleReview(request: APIRequestContext, accessToken: string, modelCardId: string) {
  const response = await request.post(`/api/srs/schedule/${modelCardId}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(response.ok()).toBeTruthy()
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
  await expect(primaryNav.getByTestId('primary-nav-item-problems')).toBeVisible()
  await expect(primaryNav.getByTestId('primary-nav-item-model-cards')).toBeVisible()
  await expect(primaryNav.getByTestId('primary-nav-item-review')).toBeVisible()

  await expect(primaryNav.getByTestId('primary-nav-item-practice')).toHaveCount(0)
  await expect(primaryNav.getByTestId('primary-nav-item-chat')).toHaveCount(0)
  await expect(primaryNav.getByTestId('primary-nav-item-srs-review')).toHaveCount(0)

  await page.getByTestId('secondary-nav-toggle').click()
  const secondaryNav = page.getByTestId('secondary-nav')
  await expect(secondaryNav.getByTestId('secondary-nav-section-tools')).toBeVisible()
  await expect(secondaryNav.getByTestId('secondary-nav-section-experiments')).toBeVisible()
  await expect(secondaryNav.getByTestId('secondary-nav-item-srs-review')).toBeVisible()
  await expect(secondaryNav.getByTestId('secondary-nav-item-practice')).toBeVisible()
  await expect(secondaryNav.getByTestId('secondary-nav-item-chat')).toBeVisible()
  await expect(secondaryNav.getByTestId('secondary-nav-item-graph')).toBeVisible()
  await expect(secondaryNav.getByTestId('secondary-nav-item-challenges')).toBeVisible()
  await expect(secondaryNav.getByTestId('secondary-nav-item-cog-test')).toBeVisible()
  await expect(page.getByTestId('dashboard-focus-card')).toBeVisible()
  await expect(page.getByTestId('dashboard-problems-panel')).toBeVisible()
  await expect(page.getByTestId('dashboard-review-panel')).toBeVisible()
  await expect(page.getByTestId('dashboard-model-cards-panel')).toBeVisible()
  await expect(page.locator('.actions-grid a[href="/chat"]')).toHaveCount(0)
  await expect(page.locator('.actions-grid a[href="/practice"]')).toHaveCount(0)
  await expect(page.getByTestId('dashboard-exploration-action')).toHaveAttribute('href', /\/problems/)
})

test('standalone chat is marked as a secondary legacy surface', async ({ page, request }) => {
  await authenticate(page, request)
  await page.goto('/chat')

  await expect(page.getByTestId('legacy-chat-banner')).toBeVisible()
  await expect(page.getByText(/secondary surface/i)).toBeVisible()
  await expect(page.getByRole('link', { name: /Go to Problems/i })).toBeVisible()
})

test('reviews page centers model-card review and evolution work', async ({ page, request }) => {
  const tokens = await authenticate(page, request)
  const card = await createModelCard(request, tokens.access_token, 'Review Hub Card')
  await scheduleReview(request, tokens.access_token, card.id)
  await createReview(request, tokens.access_token)

  await page.goto('/reviews')

  await expect(page.getByTestId('review-lifecycle-page')).toBeVisible()
  await expect(page.getByTestId('reviews-focus-card')).toHaveAttribute('href', /\/model-cards\//)
  await expect(page.getByTestId('review-queue-panel')).toContainText('No due reviews right now.')
  await expect(page.getByTestId('review-model-cards-panel')).toContainText('Review Hub Card')
  await expect(page.getByTestId('review-archive-panel')).toContainText('Review archive summary')
})

test('graph, challenges, and cog test are framed as secondary surfaces', async ({ page, request }) => {
  await authenticate(page, request)

  await page.goto('/knowledge-graph')
  await expect(page.getByTestId('graph-secondary-banner')).toBeVisible()
  await expect(page.getByTestId('graph-secondary-banner')).toContainText(/secondary tool/i)

  await page.goto('/challenges')
  await expect(page.getByTestId('challenges-secondary-banner')).toBeVisible()
  await expect(page.getByTestId('challenges-secondary-banner')).toContainText(/experimental surface/i)

  await page.goto('/cog-test')
  await expect(page.getByTestId('cog-test-secondary-banner')).toBeVisible()
  await expect(page.getByTestId('cog-test-secondary-banner')).toContainText(/experimental surface/i)
})
