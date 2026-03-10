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

### v1.2 Learning Asset Evolution

This is the current major milestone for the repository.

It means the codebase now supports a stronger end-to-end learning loop where recall and reinforcement shape durable knowledge assets, not just review queues.

The milestone is functionally complete enough to close out. It does not mean every adaptive or editing workflow is finished, but it does mean the main Milestone 2 chain is present in the repository.

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
5. Accepted concepts can be promoted into model cards and scheduled into recall.
6. Review items are traceable back to their problem and turn origins.
7. Weak recall now produces durable reinforcement targets that point back to the right problem, path, and focus target.
8. `ProblemDetail` can resume the learner into the right branch context and suggest a concrete first reinforcement action.
9. Reinforcement starters are grounded by source-turn context, likely confusion, and focused candidate evidence when the signal is reliable.
10. Model cards now reflect recall and reinforcement as explicit knowledge-asset state and lightweight revision-focus hints.

In practical terms, the current repo already contains:

- focused primary navigation around `Learn`, `Problems`, `Model Cards`, and `Reviews`
- a unified `ProblemDetail` workspace
- explicit domain entities such as `ProblemTurn`, `LearningPath`, `ProblemConceptCandidate`, `ProblemPathCandidate`, and `ReviewSchedule`
- branch/return learning-path support
- model-card handoff and review scheduling from problem outcomes
- recall origin and recall consequence display in workspace and model-card surfaces
- path-precise reinforcement resume targeting
- target-precise reinforcement focus and starter guidance inside `ProblemDetail`
- explicit model-card evolution state and revision focus hints

What this milestone does not mean:

- the app is a generic AI chat product
- the app is a note manager or file manager
- recall automatically rewrites model-card content
- the system contains a broad adaptive tutoring engine
- the review system is fully mature or deeply adaptive

## Next Milestone

### v1.3 Guided Knowledge Revision

The next milestone should focus on turning the current guidance and state signals into lightweight, traceable revision workflows for durable knowledge assets.

In scope for that milestone:

1. make revision focus hints lead to small, explicit model-card revision actions
2. keep revision changes traceable to learning, recall, and reinforcement evidence
3. tighten the connection between revision outcomes and subsequent review / reinforcement behavior

Out of scope for that milestone:

- broad new product surfaces
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
