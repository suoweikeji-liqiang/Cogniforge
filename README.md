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

- **Backend**: FastAPI + LLM (OpenAI/Anthropic) + SQLite
- **Frontend**: Vue3 + Pinia + Vue Router

## Quick Start

### Backend

```bash
cd las_backend
cp .env.example .env
# Edit .env with your configuration (LLM API keys)
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

## API Documentation

After starting the backend, visit:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
