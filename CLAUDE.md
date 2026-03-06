# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cogniforge is a cognitive learning engine that transforms understanding into structured models. It combines interactive AI dialogue with structured model abstraction, boundary testing, and cross-domain mapping. The system focuses on model construction and iterative refinement rather than simple information acquisition.

Core concepts:
- **Model Cards**: Structured cognitive models
- **Problems**: Learning challenges with associated concepts
- **Learning Paths**: Step-by-step guidance for problem-solving
- **Concept Governance**: Dynamic concept expansion and validation
- **Practice & SRS**: Spaced repetition system for knowledge retention

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector) + Alembic
- **Frontend**: Vue 3 + Pinia + Vue Router + TypeScript + Vite
- **LLM Integration**: OpenAI and Anthropic APIs via `llm_service`
- **Database**: PostgreSQL with pgvector extension for embeddings

## Development Commands

### Backend (las_backend/)

```bash
# Setup
cd las_backend
cp .env.example .env
# Edit .env with LLM API keys and DATABASE_URL
pip install -r requirements.txt

# Database migrations
alembic upgrade head

# Backfill embeddings (after schema changes)
python3 scripts/backfill_model_card_embeddings.py

# Run development server
uvicorn app.main:app --reload

# Run tests
pytest
pytest tests/test_api_smoke.py  # API integration tests
pytest tests/test_problem_learning_flow.py  # Learning flow tests
```

### Frontend (las_frontend/)

```bash
cd las_frontend
npm install
npm run dev          # Development server
npm run build        # Production build
npm run preview      # Preview production build
npm run smoke:ui     # UI smoke tests with Playwright
```

### Docker

```bash
# Full stack with PostgreSQL
docker compose up --build

# Services: postgres (port 5432), backend (port 8000), frontend (port 5173)
```

### Production Deployment

```bash
# Standard deployment
./deploy.sh

# With SQLite migration
./deploy.sh --migrate-sqlite /data/legacy/las.db

# With table truncation before migration
./deploy.sh --migrate-sqlite /data/legacy/las.db --truncate-target
```

## Architecture

### Backend Structure

- `app/main.py`: FastAPI application entry point
- `app/api/routes/`: API endpoints organized by domain
  - `problems.py`: Problem CRUD and learning flow (largest, ~51KB)
  - `model_cards.py`: Model card management
  - `conversations.py`: Chat interface
  - `practice.py`: Practice submissions and reviews
  - `auth.py`: Authentication and user management
  - `admin_*.py`: Admin configuration endpoints
  - `cog_test.py`: Cognitive testing system
- `app/services/`: Business logic layer
  - `model_os_service.py`: Core learning engine (~51KB) - handles learning paths, concept extraction, problem analysis
  - `llm_service.py`: LLM provider abstraction (OpenAI/Anthropic)
  - `cog_test_engine.py`: Cognitive test execution
  - `review_service.py`: SRS review scheduling
- `app/models/entities/`: SQLAlchemy ORM models
  - `user.py`: User, Problem, ModelCard, LearningPath, Concept, etc.
- `app/core/`: Core utilities
  - `config.py`: Settings management via pydantic-settings
  - `database.py`: Async SQLAlchemy engine
  - `vector.py`: Embedding utilities and cosine similarity
  - `security.py`: JWT and password hashing
- `alembic/versions/`: Database migrations

### Frontend Structure

- `src/main.ts`: Vue app entry point
- `src/router/index.ts`: Vue Router configuration with auth guards
- `src/stores/`: Pinia state management
  - `auth.ts`: Authentication state and token management
  - `cogTest.ts`: Cognitive test state
- `src/views/`: Page components
  - Main views: Dashboard, Problems, ModelCards, Practice, Chat, Reviews
  - Admin views: UserManagement, LLMConfig, EmailConfig
- `src/api/index.ts`: Axios API client with interceptors
- `src/i18n/`: Vue I18n internationalization (Chinese/English)

### Key Data Flow

1. **Problem Creation**: User creates problem → Backend generates embedding → Stores in PostgreSQL with pgvector
2. **Learning Path**: Problem → `model_os_service.generate_learning_path()` → LLM generates structured steps → Stored as JSON
3. **Concept Extraction**: Problem response → LLM extracts concepts → Candidate concepts → User approval → Linked to problem
4. **Practice Flow**: User submits practice → Review service schedules next review → SRS algorithm determines intervals

## Database

- **Primary DB**: PostgreSQL with pgvector extension
- **Migrations**: Alembic (run `alembic upgrade head`)
- **Embeddings**: 64-dimensional vectors (configurable via `MODEL_CARD_EMBEDDING_DIMENSIONS`)
- **Key tables**: users, problems, model_cards, learning_paths, concepts, learning_events, practice_submissions, reviews

### Migration from SQLite

Use `scripts/migrate_sqlite_to_postgres.py` or `deploy.sh --migrate-sqlite` to migrate legacy SQLite databases.

## Environment Configuration

Backend requires `.env` file (see `.env.example`):
- `DATABASE_URL`: PostgreSQL connection string (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/las_db`)
- `SECRET_KEY`: JWT secret (MUST be changed in production, app refuses to start with default in production)
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`: LLM provider keys
- `DEFAULT_LLM_PROVIDER`: "openai" or "anthropic"
- `FRONTEND_URL`: CORS configuration
- `PROBLEM_*`: Learning flow tuning parameters

## LLM Integration

The `llm_service` provides a unified interface for OpenAI and Anthropic:
- Automatically detects language (CJK vs. non-CJK) and instructs LLM to respond in matching language
- Handles JSON parsing with fallback extraction from markdown blocks
- Configurable timeouts per operation type
- Used by `model_os_service` for all cognitive operations

## Testing

- Backend: pytest with async support (`pytest.ini` configures `asyncio_default_fixture_loop_scope`)
- Frontend: Playwright for UI smoke tests (`npm run smoke:ui`)
- Test fixtures in `tests/conftest.py` provide test database and authenticated clients

## API Documentation

After starting backend: http://localhost:8000/docs (FastAPI auto-generated Swagger UI)

## Important Notes

- Production deployments MUST set non-default `SECRET_KEY` or backend will refuse to start
- Login rate limiting is enabled by default (5 attempts per 5 minutes)
- The system uses language detection to respond in Chinese or English based on user input
- Concept governance system limits concepts per problem (`PROBLEM_MAX_ASSOCIATED_CONCEPTS=16`)
- Learning paths have timeout protection (`LEARNING_PATH_TIMEOUT_SECONDS=8`)
