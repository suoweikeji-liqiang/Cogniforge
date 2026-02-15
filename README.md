# Learning Assistant System (LAS)

AI-powered learning system with Model OS cognitive framework.

## Tech Stack
- **Backend**: FastAPI + Agno + PostgreSQL + pgvector
- **Frontend**: Vue3 + Markdown-it + KaTeX

## Quick Start

### Backend
```bash
cd las_backend
cp .env.example .env
# Edit .env with your configuration
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd las_frontend
npm install
npm run dev
```

## Environment Variables

See `.env.example` for all configuration options.
