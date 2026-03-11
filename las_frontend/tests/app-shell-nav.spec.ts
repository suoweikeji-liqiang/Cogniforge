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
  await expect(primaryNav.getByTestId('primary-nav-item-problems')).toBeVisible()
  await expect(primaryNav.getByTestId('primary-nav-item-model-cards')).toBeVisible()
  await expect(primaryNav.getByTestId('primary-nav-item-review')).toBeVisible()

  await expect(primaryNav.getByTestId('primary-nav-item-practice')).toHaveCount(0)
  await expect(primaryNav.getByTestId('primary-nav-item-chat')).toHaveCount(0)
  await expect(primaryNav.getByTestId('primary-nav-item-srs-review')).toHaveCount(0)
  await expect(page.getByTestId('secondary-nav-toggle')).toHaveCount(0)
  await expect(page.getByTestId('secondary-nav')).toHaveCount(0)
  await expect(page.getByTestId('dashboard-focus-card')).toBeVisible()
  await expect(page.getByTestId('dashboard-problems-panel')).toBeVisible()
  await expect(page.getByTestId('dashboard-review-panel')).toBeVisible()
  await expect(page.getByTestId('dashboard-model-cards-panel')).toBeVisible()
  await expect(page.locator('.actions-grid a[href="/chat"]')).toHaveCount(0)
  await expect(page.locator('.actions-grid a[href="/practice"]')).toHaveCount(0)
  await expect(page.locator('.actions-grid a[href="/srs-review"]')).toHaveCount(0)
  await expect(page.locator('a[href="/notes"]')).toHaveCount(0)
  await expect(page.locator('a[href="/resources"]')).toHaveCount(0)
  await expect(page.getByTestId('dashboard-review-action')).toHaveAttribute('href', '/reviews')
  await expect(page.getByTestId('dashboard-exploration-action')).toHaveAttribute('href', /\/problems/)
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

test('manual model card creation stays draft-first before review scheduling', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: model card operations remain usable from draft creation to review-ready activation.
  // - Base Button (.btn): draft create, save, and activate controls stay visible and operable.
  // - Disabled State: review scheduling remains disabled while the asset is still a draft.
  await authenticate(page, request)
  const title = `Draft ${randomUUID().slice(0, 6)}`

  await page.goto('/model-cards')
  await page.getByRole('button', { name: /New Model Card/i }).click()
  await page.getByTestId('model-card-draft-form').getByLabel(/Asset title/i).fill(title)
  await page.getByTestId('model-card-draft-form').getByLabel(/Core note/i).fill('Draft note for durable review.')
  await page.getByTestId('model-card-draft-form').getByLabel(/Example seeds/i).fill('threshold sweep, precision tradeoff')
  await page.getByRole('button', { name: /Create Draft/i }).click()

  await expect(page).toHaveURL(/\/model-cards\/.+/)
  await expect(page.getByTestId('model-card-draft-panel')).toBeVisible()
  await expect(page.getByTestId('model-card-lifecycle-badge')).toContainText(/Draft/i)
  await expect(page.getByTestId('model-card-schedule-review')).toBeDisabled()

  await page.getByTestId('model-card-mark-ready').click()
  await expect(page.getByTestId('model-card-draft-panel')).toHaveCount(0)
  await expect(page.getByTestId('model-card-lifecycle-badge')).toContainText(/Active/i)

  await page.getByTestId('model-card-schedule-review').click()
  await expect(page.getByTestId('model-card-schedule-review')).toBeDisabled()
})

test('problem and model card libraries scale with load-more and search reset', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: browsing larger problem and model-card libraries remains usable without blocking the learning loop.
  // - Base Button (.btn): load-more controls remain visible and operable when a page has more results.
  // - Disabled State: load-more controls stay deterministic while additional pages are loading.
  const tokens = await authenticate(page, request)
  const suffix = randomUUID().slice(0, 6)
  const explorationProblemTitle = `Library Problem ${suffix}-01`
  const pagedProblemTitle = `Library Problem ${suffix}-02`
  const pagedCardTitle = `Library Card ${suffix}-01`
  const createdProblems: Array<{ id: string }> = []
  const createdCards: Array<{ id: string }> = []

  for (let index = 1; index <= 13; index += 1) {
    createdProblems.push(
      await createProblem(request, tokens.access_token, `Library Problem ${suffix}-${String(index).padStart(2, '0')}`),
    )
  }
  const updateProblemResponse = await request.put(`/api/problems/${createdProblems[0].id}`, {
    data: {
      learning_mode: 'exploration',
      status: 'completed',
    },
    headers: {
      Authorization: `Bearer ${tokens.access_token}`,
    },
  })
  expect(updateProblemResponse.ok()).toBeTruthy()
  for (let index = 1; index <= 13; index += 1) {
    createdCards.push(
      await createModelCard(request, tokens.access_token, `Library Card ${suffix}-${String(index).padStart(2, '0')}`),
    )
  }
  const scheduled = await scheduleReview(request, tokens.access_token, createdCards[0].id)
  const reinforcementReviewResponse = await request.post(`/api/srs/review/${scheduled.id}?quality=0`, {
    headers: {
      Authorization: `Bearer ${tokens.access_token}`,
    },
  })
  expect(reinforcementReviewResponse.ok()).toBeTruthy()

  await page.goto('/problems')
  await expect(page.getByTestId('problems-grid')).toBeVisible()
  await page.getByTestId('problems-mode-filter').selectOption('exploration')
  await page.getByTestId('problems-status-filter').selectOption('completed')
  await expect(page.getByText(explorationProblemTitle)).toBeVisible()
  await expect(page.getByText(pagedProblemTitle)).toHaveCount(0)
  await page.getByTestId('problems-mode-filter').selectOption('all')
  await page.getByTestId('problems-status-filter').selectOption('all')
  await expect(page.getByTestId('problems-load-more')).toBeVisible()
  await expect(page.getByText(pagedProblemTitle)).toHaveCount(0)
  await page.getByTestId('problems-load-more').click()
  await expect(page.getByText(pagedProblemTitle)).toBeVisible()
  await page.getByTestId('problems-search-input').fill(pagedProblemTitle)
  await expect(page.getByText(pagedProblemTitle)).toBeVisible()
  await page.getByTestId('problems-search-input').fill('')
  await expect(page.getByText(pagedProblemTitle)).toHaveCount(0)
  await expect(page.getByTestId('problems-load-more')).toBeVisible()

  await page.goto('/model-cards')
  await expect(page.getByTestId('model-cards-grid')).toBeVisible()
  const modelCardSearchBox = await page.getByTestId('model-cards-search-input').boundingBox()
  expect(modelCardSearchBox?.width ?? 0).toBeGreaterThan(180)
  await page.getByTestId('model-cards-attention-filter').selectOption('needs_reinforcement')
  await expect(page.getByText(pagedCardTitle)).toBeVisible()
  await expect(page.getByText(`Library Card ${suffix}-02`)).toHaveCount(0)
  await page.getByTestId('model-cards-attention-filter').selectOption('all')
  await expect(page.getByTestId('model-cards-load-more')).toBeVisible()
  await expect(page.getByText(pagedCardTitle)).toHaveCount(0)
  await page.getByTestId('model-cards-load-more').click()
  await expect(page.getByText(pagedCardTitle)).toBeVisible()
  await page.getByTestId('model-cards-search-input').fill(pagedCardTitle)
  await expect(page.getByText(pagedCardTitle)).toBeVisible()
  await page.getByTestId('model-cards-search-input').fill('')
  await expect(page.getByText(pagedCardTitle)).toHaveCount(0)
  await expect(page.getByTestId('model-cards-load-more')).toBeVisible()
})

test('revision focus becomes an editable workflow on model card detail', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: model card operations support a direct revision loop after weak recall.
  // - Base Button (.btn): revision actions remain visible and operable on the detail page.
  // - Disabled State: save controls stay deterministic while revision updates are in flight.
  const tokens = await authenticate(page, request)
  const card = await createModelCard(request, tokens.access_token, `Revision ${randomUUID().slice(0, 6)}`)
  const schedule = await scheduleReview(request, tokens.access_token, card.id)

  const reviewResponse = await request.post(`/api/srs/review/${schedule.id}?quality=0`, {
    headers: {
      Authorization: `Bearer ${tokens.access_token}`,
    },
  })
  expect(reviewResponse.ok()).toBeTruthy()

  await page.goto(`/model-cards/${card.id}`)
  await expect(page.getByTestId('model-card-revision-focus')).toBeVisible()
  await page.getByRole('button', { name: /Revise Card Now/i }).click()
  await expect(page.getByTestId('model-card-revision-editor')).toBeVisible()
  await page.getByLabel(/Revised note/i).fill('Tightened after weak recall.')
  await page.getByLabel(/Counter-examples/i).fill('Fails when the threshold is fixed too early.')
  await page.getByRole('button', { name: /Save Revision/i }).click()

  await expect(page.getByTestId('model-card-revision-editor')).toHaveCount(0)
  await expect(page.getByText('Tightened after weak recall.')).toBeVisible()
  await expect(page.getByText(/Revision workflow:/i)).toBeVisible()
})

test('notes and references are framed as supporting archives', async ({ page, request }) => {
  await authenticate(page, request)

  await page.goto('/notes')
  const notesBanner = page.getByTestId('notes-secondary-banner')
  await expect(notesBanner).toBeVisible()
  await expect(notesBanner).toContainText(/supporting archive/i)
  await expect(page.getByRole('heading', { name: /Annotation Archive/i })).toBeVisible()
  await expect(page.getByText(/secondary archive/i)).toBeVisible()
  await expect(notesBanner.getByRole('link', { name: /Annotate in ProblemDetail/i })).toBeVisible()
  await expect(page.getByTestId('notes-add-form')).toHaveCount(0)
  await page.getByTestId('notes-toggle-add').click()
  await expect(page.getByTestId('notes-add-form')).toBeVisible()

  await page.goto('/resources')
  const resourcesBanner = page.getByTestId('resources-secondary-banner')
  await expect(resourcesBanner).toBeVisible()
  await expect(resourcesBanner).toContainText(/supporting archive/i)
  await expect(page.getByRole('heading', { name: /Reference Archive/i })).toBeVisible()
  await expect(page.getByText(/secondary archive/i)).toBeVisible()
  await expect(resourcesBanner.getByRole('link', { name: /Attach in ProblemDetail/i })).toBeVisible()
  await expect(page.getByTestId('resources-add-form')).toHaveCount(0)
  await expect(page.getByTestId('resources-toggle-add')).toContainText(/Add Reference/i)
})

test('practice and srs review are framed as supporting subflows', async ({ page, request }) => {
  await authenticate(page, request)

  await page.goto('/practice')
  await expect(page.getByTestId('practice-secondary-banner')).toBeVisible()
  await expect(page.getByTestId('practice-secondary-banner')).toContainText(/supporting drill surface/i)

  await page.goto('/srs-review')
  await expect(page.getByTestId('srs-secondary-banner')).toBeVisible()
  await expect(page.getByTestId('srs-secondary-banner')).toContainText(/review subflow/i)
})

test('core pages explain their role in the learning loop', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: Problems, ProblemDetail, and Model Cards must explain how they connect in the learning loop.
  // - Base Button (.btn): primary entry actions remain visible while framing copy is present.
  const tokens = await authenticate(page, request)
  const problem = await createProblem(request, tokens.access_token, `Problem ${randomUUID().slice(0, 6)}`)

  await page.goto('/problems')
  await expect(page.getByText(/entry point into the learning loop/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /New Problem/i })).toBeVisible()

  await page.goto(`/problems/${problem.id}`)
  await expect(page.getByText(/evaluated learning turn|exploration turn/i)).toBeVisible()

  await page.goto('/model-cards')
  await expect(page.getByText(/durable knowledge assets/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /New Model Card/i })).toBeVisible()
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
