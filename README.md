# Cogniforge

**Cogniforge is a cognitive learning engine designed to turn understanding into structured models.**

Most learning tools focus on consuming information.
Cogniforge focuses on forging cognition.

It helps users:

* Transform ideas into structured models
* Stress-test assumptions through contradiction
* Discover cross-domain structural similarities
* Track cognitive evolution over time
* Close the loop between theory and real-world practice

Instead of storing notes, Cogniforge builds:

* Model Cards
* Contradiction Logs
* Cross-domain Transfers
* Cognitive Evolution Records

The system operates on a simple principle:

> Learning is not information acquisition —
> it is model construction and iterative refinement.

Cogniforge combines:

* Interactive AI dialogue
* Structured model abstraction
* Boundary testing (model collision)
* Cross-domain mapping
* Evolution-aware version tracking

This project aims to build a reusable cognitive operating framework for engineers, researchers, and deep learners who want more than answers — they want mental architecture.

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
