import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'

import { chromium } from 'playwright'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendDir = path.resolve(__dirname, '..')
const repoRoot = path.resolve(frontendDir, '..')
const artifactDir = path.join(repoRoot, 'output', 'playwright')
const baseUrl = 'http://127.0.0.1:4173'

const encodePayload = (payload) =>
  Buffer.from(JSON.stringify(payload)).toString('base64url')

const buildToken = (payload) => `stub.${encodePayload(payload)}.sig`

const makeId = (prefix, index) => `${prefix}-${String(index).padStart(4, '0')}`

const mockUser = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'user@example.com',
  username: 'tester',
  full_name: 'Test User',
  role: 'admin',
  is_active: true,
}

const previewEnv = {
  ...process.env,
  BROWSER: 'none',
}

const waitForServer = async (url, timeoutMs = 15000) => {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // Server not ready yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error(`Preview server did not start within ${timeoutMs}ms`)
}

const startPreview = () =>
  spawn(
    'npm',
    ['run', 'preview', '--', '--host', '127.0.0.1', '--port', '4173', '--strictPort'],
    {
      cwd: frontendDir,
      env: previewEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

const stopProcess = async (child) => {
  if (!child || child.exitCode !== null) return
  child.kill('SIGTERM')
  await new Promise((resolve) => child.once('exit', resolve))
}

const fulfillJson = (route, payload, status = 200) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  })

const fulfillText = (route, body, contentType = 'text/plain') =>
  route.fulfill({
    status: 200,
    contentType,
    body,
  })

const getJsonBody = (request) => {
  const body = request.postData()
  return body ? JSON.parse(body) : {}
}

const nowIso = () => new Date().toISOString()

const buildState = () => ({
  problems: [
    {
      id: makeId('problem', 1),
      user_id: mockUser.id,
      title: 'Refine retrieval prompts',
      description: 'Decide when to pull in model cards versus reviews.',
      associated_concepts: ['retrieval', 'prompting'],
      status: 'in-progress',
      created_at: nowIso(),
      updated_at: nowIso(),
    },
  ],
  learningPaths: {
    [makeId('problem', 1)]: {
      id: makeId('path', 1),
      problem_id: makeId('problem', 1),
      current_step: 1,
      path_data: [
        {
          step: 1,
          concept: 'Prompt routing',
          description: 'Separate retrieval-worthy prompts from generic chat.',
          resources: ['Prompt routing notes'],
        },
        {
          step: 2,
          concept: 'Context ranking',
          description: 'Pull the highest-signal memory into the answer.',
          resources: ['Ranking heuristics'],
        },
      ],
    },
  },
  problemResponses: {
    [makeId('problem', 1)]: [],
  },
  modelCards: [
    {
      id: makeId('card', 1),
      user_id: mockUser.id,
      title: 'Retrieval Model',
      user_notes: 'Use model cards before reviews when signal is stable.',
      concept_maps: { nodes: [], edges: [] },
      examples: ['stable concept recall'],
      counter_examples: ['fresh exploratory chat'],
      migration_attempts: [],
      version: 2,
      created_at: nowIso(),
      updated_at: nowIso(),
    },
  ],
  evolutionLogs: {
    [makeId('card', 1)]: [
      {
        id: makeId('elog', 1),
        action_taken: 'refined',
        reason_for_change: 'Added better context routing guidance.',
        snapshot: {
          version: 2,
          title: 'Retrieval Model',
        },
        created_at: nowIso(),
      },
    ],
  },
  reviews: [],
  schedules: [],
  retrievalLogs: [
    {
      id: makeId('retrieval', 1),
      user_id: mockUser.id,
      source: 'problem_response',
      query: 'Refine the prompt with prior model cards.',
      retrieval_context: '...',
      items: [
        { entity_type: 'model_card', entity_id: makeId('card', 1), title: 'Retrieval Model', score: 0.82 },
        { entity_type: 'review', entity_id: makeId('review', 9), title: 'weekly / 2026-W10', score: 0.44 },
      ],
      result_count: 2,
      created_at: nowIso(),
    },
    {
      id: makeId('retrieval', 2),
      user_id: mockUser.id,
      source: 'conversation_chat',
      query: 'Use my prior knowledge before answering.',
      retrieval_context: '...',
      items: [
        { entity_type: 'model_card', entity_id: makeId('card', 1), title: 'Retrieval Model', score: 0.77 },
      ],
      result_count: 1,
      created_at: nowIso(),
    },
  ],
})

const buildRetrievalSummary = (logs) => {
  const total_events = logs.length
  const total_hits = logs.reduce((sum, item) => sum + (item.result_count || 0), 0)
  const zero_hit_events = logs.filter((item) => (item.result_count || 0) === 0).length
  const poor_hit_events = logs.filter((item) => (item.result_count || 0) <= 1).length
  const source_breakdown = {}
  for (const log of logs) {
    source_breakdown[log.source] = (source_breakdown[log.source] || 0) + 1
  }
  const average_hits = total_events ? Number((total_hits / total_events).toFixed(2)) : 0
  const zero_hit_rate = total_events ? Number((zero_hit_events / total_events).toFixed(2)) : 0
  const health_status =
    zero_hit_events > 0 || average_hits < 1.5 ? 'needs_attention' : 'healthy'

  return {
    total_events,
    total_hits,
    average_hits,
    zero_hit_events,
    poor_hit_events,
    zero_hit_rate,
    health_status,
    source_breakdown,
  }
}

const matchesSearch = (text, query) =>
  !query || text.toLowerCase().includes(query.toLowerCase())

const main = async () => {
  await mkdir(artifactDir, { recursive: true })
  const preview = startPreview()

  preview.stdout.on('data', (chunk) => process.stdout.write(chunk))
  preview.stderr.on('data', (chunk) => process.stderr.write(chunk))

  let browser
  try {
    await waitForServer(baseUrl)
    const state = buildState()

    browser = await chromium.launch({ headless: true })
    const context = await browser.newContext()
    const page = await context.newPage()

    const accessToken = buildToken({
      sub: mockUser.id,
      exp: Math.floor(Date.now() / 1000) + 3600,
    })
    const refreshToken = buildToken({
      sub: mockUser.id,
      exp: Math.floor(Date.now() / 1000) + 86400,
    })

    await page.route('**/api/**', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const pathname = url.pathname
      const method = request.method()

      if (pathname === '/api/auth/login' && method === 'POST') {
        return fulfillJson(route, {
          access_token: accessToken,
          refresh_token: refreshToken,
          token_type: 'bearer',
        })
      }

      if (pathname === '/api/auth/me' && method === 'GET') {
        return fulfillJson(route, mockUser)
      }

      if (pathname === '/api/auth/refresh' && method === 'POST') {
        return fulfillJson(route, {
          access_token: accessToken,
          refresh_token: refreshToken,
          token_type: 'bearer',
        })
      }

      if (pathname === '/api/auth/logout' && method === 'POST') {
        return fulfillJson(route, { message: 'Logged out successfully' })
      }

      if (pathname === '/api/problems/' && method === 'GET') {
        const query = url.searchParams.get('q') || ''
        const problems = state.problems.filter((item) =>
          matchesSearch(`${item.title} ${item.description}`, query)
        )
        return fulfillJson(route, problems)
      }

      if (pathname === '/api/problems/' && method === 'POST') {
        const body = getJsonBody(request)
        const id = makeId('problem', state.problems.length + 1)
        const created = {
          id,
          user_id: mockUser.id,
          title: body.title,
          description: body.description || '',
          associated_concepts: body.associated_concepts || [],
          status: 'new',
          created_at: nowIso(),
          updated_at: nowIso(),
        }
        state.problems.unshift(created)
        state.learningPaths[id] = {
          id: makeId('path', Object.keys(state.learningPaths).length + 1),
          problem_id: id,
          current_step: 0,
          path_data: [
            {
              step: 1,
              concept: `${body.title} basics`,
              description: body.description || 'Learn the basics',
              resources: [],
            },
          ],
        }
        state.problemResponses[id] = []
        return fulfillJson(route, created, 201)
      }

      if (/^\/api\/problems\/[^/]+$/.test(pathname) && method === 'GET') {
        const id = pathname.split('/').pop()
        const problem = state.problems.find((item) => item.id === id)
        return fulfillJson(route, problem || {}, problem ? 200 : 404)
      }

      if (/^\/api\/problems\/[^/]+\/learning-path$/.test(pathname) && method === 'GET') {
        const id = pathname.split('/')[3]
        return fulfillJson(route, state.learningPaths[id] || null)
      }

      if (/^\/api\/problems\/[^/]+\/learning-path$/.test(pathname) && method === 'PUT') {
        const id = pathname.split('/')[3]
        const body = getJsonBody(request)
        const pathState = state.learningPaths[id]
        if (pathState) {
          pathState.current_step = body.current_step
          const problem = state.problems.find((item) => item.id === id)
          if (problem) {
            problem.status =
              body.current_step >= pathState.path_data.length
                ? 'completed'
                : body.current_step > 0
                  ? 'in-progress'
                  : 'new'
          }
        }
        return fulfillJson(route, pathState || {}, pathState ? 200 : 404)
      }

      if (/^\/api\/problems\/[^/]+\/responses$/.test(pathname) && method === 'GET') {
        const id = pathname.split('/')[3]
        return fulfillJson(route, state.problemResponses[id] || [])
      }

      if (/^\/api\/problems\/[^/]+\/responses$/.test(pathname) && method === 'POST') {
        const id = pathname.split('/')[3]
        const body = getJsonBody(request)
        const entry = {
          id: makeId('response', (state.problemResponses[id] || []).length + 1),
          problem_id: id,
          user_response: body.user_response,
          system_feedback: 'Structured feedback generated.',
          structured_feedback: {
            correctness: 'partially correct',
            misconceptions: ['Need a clearer retrieval threshold'],
            suggestions: ['Use the latest model card before broad context'],
            next_question: 'When should reviews outrank model cards?',
          },
          created_at: nowIso(),
        }
        state.problemResponses[id].push(entry)
        state.retrievalLogs.unshift({
          id: makeId('retrieval', state.retrievalLogs.length + 1),
          user_id: mockUser.id,
          source: 'problem_response',
          query: body.user_response,
          retrieval_context: 'Problem context',
          items: [
            { entity_type: 'model_card', entity_id: makeId('card', 1), title: 'Retrieval Model', score: 0.91 },
          ],
          result_count: 1,
          created_at: nowIso(),
        })
        return fulfillJson(route, entry)
      }

      if (pathname === '/api/model-cards/' && method === 'GET') {
        const query = url.searchParams.get('q') || ''
        const scheduled = url.searchParams.get('scheduled')
        const scheduledIds = new Set(state.schedules.map((item) => item.model_card_id))
        let cards = state.modelCards.filter((item) =>
          matchesSearch(`${item.title} ${item.user_notes}`, query)
        )
        if (scheduled === 'true') {
          cards = cards.filter((item) => scheduledIds.has(item.id))
        } else if (scheduled === 'false') {
          cards = cards.filter((item) => !scheduledIds.has(item.id))
        }
        return fulfillJson(route, cards)
      }

      if (pathname === '/api/model-cards/' && method === 'POST') {
        const body = getJsonBody(request)
        const created = {
          id: makeId('card', state.modelCards.length + 1),
          user_id: mockUser.id,
          title: body.title,
          user_notes: body.user_notes || '',
          concept_maps: { nodes: [], edges: [] },
          examples: body.examples || [],
          counter_examples: [],
          migration_attempts: [],
          version: 1,
          created_at: nowIso(),
          updated_at: nowIso(),
        }
        state.modelCards.unshift(created)
        state.evolutionLogs[created.id] = []
        return fulfillJson(route, created, 201)
      }

      if (/^\/api\/model-cards\/[^/]+$/.test(pathname) && method === 'GET') {
        const id = pathname.split('/')[3]
        const card = state.modelCards.find((item) => item.id === id)
        return fulfillJson(route, card || {}, card ? 200 : 404)
      }

      if (/^\/api\/model-cards\/[^/]+\/evolution$/.test(pathname) && method === 'GET') {
        const id = pathname.split('/')[3]
        return fulfillJson(route, state.evolutionLogs[id] || [])
      }

      if (/^\/api\/model-cards\/[^/]+\/compare$/.test(pathname) && method === 'GET') {
        const id = pathname.split('/')[3]
        const card = state.modelCards.find((item) => item.id === id)
        return fulfillJson(route, card ? {
          old_version: null,
          new_version: { version: card.version },
          changes_summary: `Latest summary for ${card.title}`,
        } : null)
      }

      if (/^\/api\/model-cards\/[^/]+\/similar$/.test(pathname) && method === 'GET') {
        const id = pathname.split('/')[3]
        return fulfillJson(route, state.modelCards.filter((item) => item.id !== id).slice(0, 2))
      }

      if (pathname === '/api/reviews/' && method === 'GET') {
        return fulfillJson(route, state.reviews)
      }

      if (pathname === '/api/reviews/' && method === 'POST') {
        const body = getJsonBody(request)
        const created = {
          id: makeId('review', state.reviews.length + 1),
          user_id: mockUser.id,
          review_type: body.review_type,
          period: body.period,
          content: body.content,
          created_at: nowIso(),
        }
        state.reviews.unshift(created)
        return fulfillJson(route, created, 201)
      }

      if (pathname === '/api/reviews/generate' && method === 'POST') {
        const body = getJsonBody(request)
        return fulfillJson(route, {
          review_type: body.review_type,
          period: body.period,
          content: {
            summary: 'Generated review summary',
            insights: 'Generated retrieval insight',
            next_steps: 'Tighten the retrieval threshold',
            misconceptions: ['Review noise can swamp signal'],
          },
        })
      }

      if (/^\/api\/reviews\/[^/]+\/export$/.test(pathname) && method === 'GET') {
        return fulfillText(route, '# Review Export\n\nGenerated export.', 'text/markdown')
      }

      if (pathname === '/api/srs/schedules' && method === 'GET') {
        return fulfillJson(route, state.schedules)
      }

      if (pathname === '/api/srs/due' && method === 'GET') {
        const due = state.schedules
          .filter((item) => new Date(item.next_review_at).getTime() <= Date.now())
          .map((schedule) => {
            const card = state.modelCards.find((item) => item.id === schedule.model_card_id)
            return {
              schedule_id: schedule.id,
              model_card_id: schedule.model_card_id,
              title: card?.title || 'Untitled',
              user_notes: card?.user_notes || '',
              examples: card?.examples || [],
              counter_examples: card?.counter_examples || [],
            }
          })
        return fulfillJson(route, due)
      }

      if (/^\/api\/srs\/schedule\/[^/]+$/.test(pathname) && method === 'POST') {
        const modelCardId = pathname.split('/').pop()
        const existing = state.schedules.find((item) => item.model_card_id === modelCardId)
        if (existing) {
          return fulfillJson(route, { detail: 'Already scheduled' }, 400)
        }
        const card = state.modelCards.find((item) => item.id === modelCardId)
        const schedule = {
          id: makeId('schedule', state.schedules.length + 1),
          model_card_id: modelCardId,
          title: card?.title || 'Untitled',
          interval_days: 1,
          repetitions: 0,
          ease_factor: 2500,
          next_review_at: nowIso(),
          last_reviewed_at: null,
        }
        state.schedules.push(schedule)
        return fulfillJson(route, schedule)
      }

      if (/^\/api\/srs\/review\/[^/]+$/.test(pathname) && method === 'POST') {
        const scheduleId = pathname.split('/').pop()
        const schedule = state.schedules.find((item) => item.id === scheduleId)
        if (schedule) {
          schedule.repetitions += 1
          schedule.last_reviewed_at = nowIso()
          schedule.next_review_at = new Date(Date.now() + 86400000).toISOString()
        }
        return fulfillJson(route, schedule || {}, schedule ? 200 : 404)
      }

      if (pathname === '/api/conversations/' && method === 'GET') {
        return fulfillJson(route, [{ id: makeId('conversation', 1), title: 'Recent chat' }])
      }

      if (pathname === '/api/practice/tasks' && method === 'GET') {
        return fulfillJson(route, [{ id: makeId('task', 1), title: 'Practice retrieval' }])
      }

      if (pathname === '/api/statistics/overview' && method === 'GET') {
        const dueReviews = state.schedules.filter((item) => new Date(item.next_review_at).getTime() <= Date.now()).length
        return fulfillJson(route, {
          problems: state.problems.length,
          model_cards: state.modelCards.length,
          conversations: 1,
          reviews: state.reviews.length,
          due_reviews: dueReviews,
        })
      }

      if (pathname === '/api/statistics/heatmap' && method === 'GET') {
        return fulfillJson(route, {
          days: 90,
          activity: {
            '2026-03-01': 2,
            '2026-03-02': 1,
            '2026-03-03': 4,
          },
        })
      }

      if (pathname === '/api/retrieval/summary' && method === 'GET') {
        return fulfillJson(route, buildRetrievalSummary(state.retrievalLogs))
      }

      if (pathname === '/api/retrieval/logs' && method === 'GET') {
        const source = url.searchParams.get('source')
        const limit = Number(url.searchParams.get('limit') || '20')
        const logs = state.retrievalLogs
          .filter((item) => !source || item.source === source)
          .slice(0, limit)
        return fulfillJson(route, logs)
      }

      return fulfillJson(route, {}, 404)
    })

    await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' })
    await page.locator('input[type="text"]').fill('tester')
    await page.locator('input[type="password"]').fill('secret123')
    await page.getByRole('button', { name: 'Login' }).click()

    await page.waitForURL(`${baseUrl}/dashboard`)
    await page.getByText('RAG Retrieval Activity').waitFor()
    await page.getByText('Refine the prompt with prior model cards.').waitFor()

    await page.goto(`${baseUrl}/problems`, { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'New Problem' }).click()
    await page.locator('.modal input[type="text"]').first().fill('Trace retrieval gaps')
    await page.locator('.modal textarea').fill('Track why some prompts miss the right context.')
    await page.locator('.modal input[type="text"]').nth(1).fill('retrieval, observability')
    await page.locator('.modal .btn.btn-primary').click()
    await page.waitForURL(/\/problems\/problem-/)
    await page.getByRole('heading', { name: 'Trace retrieval gaps', exact: true }).waitFor()
    await page.locator('textarea').fill('Use the highest-signal card before pulling reviews.')
    await page.getByRole('button', { name: 'Submit' }).click()
    await page.getByText('partially correct').waitFor()

    await page.goto(`${baseUrl}/model-cards`, { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'New Model Card' }).click()
    await page.locator('.modal input[type="text"]').first().fill('Observation Loop')
    await page.locator('.modal textarea').fill('Keep retrieval logs and qualitative checks together.')
    await page.locator('.modal input[type="text"]').nth(1).fill('dashboard observer, zero-hit alerts')
    await page.locator('.modal .btn.btn-primary').click()
    await page.getByText('Observation Loop').waitFor()
    const cardRow = page.locator('.model-card', { hasText: 'Observation Loop' })
    await cardRow.getByRole('button', { name: 'Add to Review' }).click()
    await cardRow.getByRole('button', { name: 'Scheduled' }).waitFor()

    await page.goto(`${baseUrl}/reviews`, { waitUntil: 'networkidle' })
    const reviewModal = page.locator('.modal')
    await page.getByRole('button', { name: 'New Review' }).click()
    await reviewModal.locator('input[type="text"]').fill('2026-03-04')
    await reviewModal.getByRole('button', { name: 'Generate with AI' }).click()
    await page.waitForFunction(
      () => {
        const el = document.querySelector('.modal textarea')
        return Boolean(el && el.value.includes('Generated review summary'))
      }
    )
    await reviewModal.locator('.modal-actions .btn.btn-primary').click()
    await page.locator('.review-card', { hasText: '2026-03-04' }).waitFor()

    await page.goto(`${baseUrl}/srs-review`, { waitUntil: 'networkidle' })
    await page.getByText('Observation Loop').waitFor()
    await page.getByRole('button', { name: 'Show Answer' }).click()
    await page.getByText('Keep retrieval logs and qualitative checks together.').waitFor()
    await page.getByRole('button', { name: /5 - Perfect/ }).click()
    await page.getByText('All reviews done for today!').waitFor()

    await page.goto(`${baseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByText('View Review History').waitFor()
    await page.getByText('Use the highest-signal card before pulling reviews.').waitFor()

    await page.screenshot({
      path: path.join(artifactDir, 'dashboard-smoke.png'),
      fullPage: true,
    })

    console.log('Dashboard smoke passed')
  } finally {
    if (browser) await browser.close()
    await stopProcess(preview)
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
