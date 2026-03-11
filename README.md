# Cogniforge

Cogniforge is a problem-centered learning system for structured cognition building.

The current product surface is organized around the learning loop:

- `Problems` as the entry point
- `ProblemDetail` as the main learning workspace
- dual learning modes: `socratic` and `exploration`
- derived concepts and derived learning path candidates
- model cards as long-term knowledge artifacts
- review / recall as reinforcement of learning outcomes

This repository is not currently centered on generic chat, note-taking, or PKM-style workflows. Those surfaces may still exist in the codebase, but the main product direction is the structured learning loop above.

## Current Major Milestone

### v1.3 Guided Knowledge Revision + Hardening

This is the active milestone for the repository. `P0` is complete and `P1` is in final closeout.

It means the codebase has already closed the first revision-oriented gap in the learning loop and is now hardening the main workflow before broader expansion.

The current codebase now has all of the following:

1. `ProblemDetail` is the main place for active learning.
2. Learning modes are explicit first-class concepts:
   - `socratic`: the system asks, the learner answers, mastery/progression is evaluated
   - `exploration`: the learner asks, the system explains, concepts and next learning actions are derived
3. Learning turns can produce structured outputs:
   - mastery/progression signals
   - derived concept candidates
   - derived learning path candidates
   - review handoff signals
4. Main path and branch path relationships are navigable and traceable.
5. Model cards now carry explicit provenance and lifecycle metadata, including manual vs problem-derived origins.
6. Manual model-card creation now follows a draft-first path before activation and review scheduling.
7. `ModelCardDetail` can turn revision-focus signals into a lightweight guided revision action.
8. Provider-native structured outputs now back the core learning artifacts and the remaining major `ModelOSService` JSON chains.
9. `ProblemDetail` now streams key AI interactions for exploration ask, Socratic question generation, and Socratic response evaluation while keeping blocking fallbacks.
10. `Problems` and `Model Cards` now scale better for larger libraries through database-backed pagination, debounced search, higher-signal filters, and lighter review-summary fetching.
11. Core workflow modules have been materially split into support files so the main learning loop can now be iterated on without the earlier concentration risk hotspots.

In practical terms, the current repo already contains:

- focused primary navigation around `Learn`, `Problems`, `Model Cards`, and `Reviews`
- a unified `ProblemDetail` workspace
- explicit domain entities such as `ProblemTurn`, `LearningPath`, `ProblemConceptCandidate`, `ProblemPathCandidate`, and `ReviewSchedule`
- branch/return learning-path support
- model-card handoff, provenance tracking, and review scheduling from problem outcomes
- recall origin and recall consequence display in workspace and model-card surfaces
- path-precise reinforcement resume targeting
- target-precise reinforcement focus and starter guidance inside `ProblemDetail`
- explicit model-card evolution state, revision focus hints, and lightweight guided revision

What this milestone does not mean:

- the app is a generic AI chat product
- the app is a note manager or file manager
- recall automatically rewrites model-card content
- the system contains a broad adaptive tutoring engine
- the review system is fully mature or deeply adaptive

## Current Hardening Focus

The remaining work in this cycle is intentionally narrower than a new product-surface expansion:

1. finish the remaining `Problems` / `Model Cards` list-closeout decisions without opening graph scope
2. keep full regression healthy while the hardening pass is being closed out
3. keep warning/debt cleanup as follow-up work instead of reopening milestone scope

Still out of scope while this hardening pass remains open:

- broad new product surfaces
- graph-oriented knowledge navigation
- automatic model-card rewriting
- generic analytics expansion
- unrelated admin or tooling work

---

## Tech Stack

- **Backend**: FastAPI + multi-provider LLM integrations (OpenAI-compatible / Qwen, Anthropic, Ollama) + PostgreSQL
- **Frontend**: Vue3 + Pinia + Vue Router

## Quick Start

### Docker

```bash
cp .env.example .env
# Edit .env before server deploy:
# - SECRET_KEY
# - POSTGRES_PASSWORD
# - BACKEND_CORS_ORIGINS
# - FRONTEND_URL
# Optional:
# - FRONTEND_PORT=80
docker compose up -d --build
```

默认容器环境现在使用 PostgreSQL（`pgvector/pgvector` 镜像）作为数据库。
后端容器启动时会先自动执行 `alembic upgrade head`，然后再启动 API，所以直接 `docker compose up -d` 不会漏掉 schema migration。

部署前至少需要准备根目录 `.env`：

```env
APP_ENV=production
SECRET_KEY=replace-with-a-long-random-secret
POSTGRES_PASSWORD=replace-with-a-strong-password
BACKEND_CORS_ORIGINS=https://your-domain.example
FRONTEND_URL=https://your-domain.example
FRONTEND_PORT=80
```

### Deploy Script

生产环境可直接使用根目录的 `deploy.sh`：

```bash
cp .env.example .env
# edit .env first
./deploy.sh
```

如需在部署时把旧 SQLite 数据导入当前 PostgreSQL，并自动补 embedding：

```bash
./deploy.sh --migrate-sqlite /data/legacy/las.db
```

如需先清空目标表再导入：

```bash
./deploy.sh --migrate-sqlite /data/legacy/las.db --truncate-target
```

### Backend

```bash
cd las_backend
cp .env.example .env
# Edit .env with your runtime configuration (DATABASE_URL / SECRET_KEY / CORS)
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

LLM provider credentials are no longer expected in backend `.env`.
Configure provider API keys, base URLs, and default models in `Admin -> LLM Configuration`.

如需把旧 SQLite 数据迁移到 PostgreSQL：

```bash
python3 scripts/migrate_sqlite_to_postgres.py \
  --source-sqlite ./las.db \
  --target-url postgresql+asyncpg://postgres:postgres@localhost:5432/las_db
```

本地默认配置推荐使用 PostgreSQL：

```env
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/las_db
AUTO_CREATE_TABLES=false
```

生产环境必须显式设置非默认 `SECRET_KEY`，否则后端会在启动时拒绝运行。
登录接口现在默认启用基础限流，可通过 `LOGIN_RATE_LIMIT_*` 环境变量调整窗口、次数和封禁时间。

如需临时回退到 SQLite 开发模式，可显式设置：

```env
DATABASE_FILE=./las.db
AUTO_CREATE_TABLES=true
```

### Frontend

```bash
cd las_frontend
npm install
npm run dev
```

## Environment Variables

- Docker / deploy variables: root `.env.example`
- Local backend variables: `las_backend/.env.example`
- Provider credentials: `Admin -> LLM Configuration` (stored in DB, not in `.env`)

## API Documentation

After starting the backend, visit:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
