import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'

async function authenticateZh(page: Page, request: APIRequestContext) {
  const suffix = randomUUID().slice(0, 8)
  const username = `zhmain_${suffix}`
  const password = 'password123'
  const email = `${username}@example.com`

  const registerResponse = await request.post('/api/auth/register', {
    data: {
      email,
      username,
      password,
      full_name: '中文主线验收用户',
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
      window.localStorage.setItem('locale', 'zh')
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
      description: '验证中文主工作区在较长文案下仍能保持主次清晰。',
      associated_concepts: ['精确率', '召回率'],
      learning_mode: 'socratic',
    },
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function createModelCard(request: APIRequestContext, accessToken: string, title: string) {
  const response = await request.post('/api/model-cards/', {
    data: {
      title,
      user_notes: '用于检查中文生命周期文案是否仍然可扫读。',
      examples: ['当阈值升高时，精确率常常上升，召回率可能下降。'],
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
      period: '中文验收周报',
      content: {
        summary: '归档区应该退到次级位置，不抢占当前学习主线。',
        insights: '三段式生命周期文案在中文下也要保持可扫读。',
        next_steps: '继续检查中文页面的主 CTA 和结构化产物。',
        misconceptions: ['把精确率和召回率当成完全同义的指标'],
      },
    },
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  expect(response.ok()).toBeTruthy()
}

test('zh mainline surfaces stay localized across continue reviews and workspace outputs', async ({ page, request }) => {
  // Contract Assertions:
  // - Critical Path: the zh mainline must keep core navigation and workspace decisions localized.
  // - Base Button (.btn): longer zh CTA labels must remain visible and operable in the primary flow.
  const suffix = randomUUID().slice(0, 8)
  const tokens = await authenticateZh(page, request)
  const problem = await createProblem(request, tokens.access_token, `中文验收问题 ${suffix}：精确率与召回率的边界理解`)
  const modelCard = await createModelCard(request, tokens.access_token, `中文验收知识卡 ${suffix}：精确率与召回率`)

  await scheduleReview(request, tokens.access_token, modelCard.id)
  await createReview(request, tokens.access_token)

  await page.goto('/dashboard')
  await expect(page.getByTestId('primary-nav-item-home')).toContainText('继续学习')
  await expect(page.getByTestId('continue-focus-card')).toContainText(/继续最近的问题|打开学习工作区/)
  await expect(page.getByTestId('continue-focus-card')).not.toContainText(/Continue Learning|Open Workspace/i)

  await page.goto('/reviews')
  await expect(page.getByRole('heading', { level: 1, name: '复习' })).toBeVisible()
  const reinforcementPanel = page.getByTestId('reviews-reinforcement-panel')
  await expect(reinforcementPanel).toContainText(/需要强化|回到工作区/)
  await expect(reinforcementPanel).not.toContainText(/Source:|Current state:|Suggested action:/i)

  await page.goto(`/problems/${problem.id}`)
  await expect(page.getByTestId('problem-detail-workspace')).toBeVisible()
  await expect(page.getByTestId('problem-learning-header')).toContainText(/精确率与召回率/)
  await expect(page.getByTestId('problem-learning-contract')).toContainText(/当前任务|完成标准/)

  await page.getByTestId('mode-switch-exploration').click()
  await expect(page.getByTestId('workspace-current-output-empty')).toBeVisible()
  await page.getByTestId('mode-switch-socratic').click()
  await expect(page.getByTestId('socratic-question-panel')).toBeVisible()
  await page.getByTestId('socratic-response-input').fill('第一次回答：阈值越严格，通常精确率会上升，但召回率可能下降。')
  await page.getByTestId('submit-socratic-response').click()
  await expect(page.getByTestId('problem-turn-result')).toContainText(/掌握度|误区|建议|Mastery/i)

  await page.getByTestId('mode-switch-exploration').click()
  await page.getByTestId('exploration-question-input').fill('精确率和召回率有什么区别？请给一个阈值变化的具体例子。')
  await page.getByTestId('submit-exploration-question').click()
  await expect(page.getByTestId('problem-turn-result')).toContainText(/精确率|召回率/)
  await expect(page.getByTestId('problem-postturn-decisions')).toContainText(/处理概念候选|处理路径建议/)
})
