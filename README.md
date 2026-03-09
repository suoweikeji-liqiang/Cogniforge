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

### v1.1 Problem-Centered Learning Loop Core

This is the current major milestone for the repository.

It means the codebase now supports an end-to-end core learning loop with these properties:

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
7. Recall outcomes now feed back into workspace and model-card state as visible stability and next-action signals.

In practical terms, the current repo already contains:

- focused primary navigation around `Learn`, `Problems`, `Model Cards`, and `Reviews`
- a unified `ProblemDetail` workspace
- explicit domain entities such as `ProblemTurn`, `LearningPath`, `ProblemConceptCandidate`, `ProblemPathCandidate`, and `ReviewSchedule`
- branch/return learning-path support
- model-card handoff and review scheduling from problem outcomes
- recall origin and recall consequence display in workspace and model-card surfaces

What this milestone does not mean:

- the app is a generic AI chat product
- the app is a note manager or file manager
- recall automatically rewrites model-card content
- the review system is fully mature or deeply adaptive

## Next Milestone

### v1.2 Learning Asset Evolution

The next milestone should focus on tightening how learning and recall update durable knowledge assets.

In scope for that milestone:

1. make weak recall route learners back to the right problem/path context more precisely
2. use learning and recall evidence to drive model-card evolution more deliberately
3. improve how review priority and follow-up actions are derived from recent outcomes

Out of scope for that milestone:

- broad new product surfaces
- generic analytics expansion
- unrelated admin or tooling work

---

## Tech Stack

- **Backend**: FastAPI + LLM (OpenAI/Anthropic) + PostgreSQL
- **Frontend**: Vue3 + Pinia + Vue Router

## Quick Start

### Docker

```bash
docker compose up --build
```

默认容器环境现在使用 PostgreSQL（`pgvector/pgvector` 镜像）作为数据库。

### Deploy Script

生产环境可直接使用根目录的 `deploy.sh`：

```bash
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
# Edit .env with your configuration (LLM API keys, DATABASE_URL if needed)
pip install -r requirements.txt
alembic upgrade head
python3 scripts/backfill_model_card_embeddings.py
uvicorn app.main:app --reload
```

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

See `.env.example` for all configuration options.

## API Documentation

After starting the backend, visit:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
