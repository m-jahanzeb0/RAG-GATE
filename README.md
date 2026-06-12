# 🚀 RAG-Gate

**AI API Gateway — Rate-limited, multi-provider proxy with Redis-backed quota enforcement and a glassmorphism React dashboard.**

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/m-jahanzeb0/RAG-GATE/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-95%25-green.svg)](https://github.com/m-jahanzeb0/RAG-GATE)

---

## Architecture

```mermaid
flowchart LR
    Client[Client / Dashboard] -->|Api-Key Auth| Gateway[DRF Gateway]
    Gateway -->|Atomic INCR| Redis[(Redis)]
    Gateway -->|Quota Check| Q{Quota OK?}
    Q -->|No - 429| Client
    Q -->|Yes| LLM[LLM Provider]
    LLM -->|OpenAI| OpenAI
    LLM -->|Anthropic| Anthropic
    LLM -->|OpenAI-Compatible| Compat[Groq / OpenRouter]
    LLM -->|Response| Gateway
    Gateway -->|SSE or JSON| Client
    Gateway -.->|Async| Celery[Celery Worker]
    Celery -->|Log + Persist| DB[(PostgreSQL)]
    Celery -.->|Midnight Reset| Beat[Celery Beat]

    style Redis fill:#ffd700,color:#000
    style Celery fill:#6366f1,color:#fff
    style Beat fill:#6366f1,color:#fff
    style DB fill:#2563eb,color:#fff
    style OpenAI fill:#10a37f,color:#fff
    style Anthropic fill:#d97706,color:#fff
    style Compat fill:#22d3ee,color:#000
```

## Features

- ⚡ **Dual-mode Proxy** — Unary (JSON) or Streaming (SSE) responses from the same endpoint
- 🔒 **Redis-backed Quota** — Atomic `INCR` prevents race conditions under concurrent load (30 req/day default)
- 🔑 **API Key Auth** — Header-based `Authorization: Api-Key <key>` authentication
- 🧩 **Multi-Provider** — OpenAI, Anthropic, and any OpenAI-compatible API (Groq, OpenRouter, Together, vLLM)
- 📊 **React Dashboard** — Glassmorphism UI with real-time metrics, usage charts, and provider distribution
- 🧵 **Async Logging** — Celery workers handle DB persistence and request logging without blocking
- 🐳 **Docker Ready** — PostgreSQL + Redis + Celery workers via `docker-compose.yml`
- ✅ **95% Test Coverage** — Comprehensive pytest suite with Redis mocks and SDK-level mocking

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker Desktop (for PostgreSQL + Redis)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/your-username/RAG-GATE.git
cd RAG-GATE

# Copy environment variables
cp .env.example rag_gate/.env
# Edit rag_gate/.env and add your API keys:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...

# Start infrastructure (PostgreSQL + Redis)
cd rag_gate
docker compose up -d db redis

# Install Python dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create a superuser (for API key management)
python manage.py createsuperuser
# Then create an API key via the admin at http://localhost:8000/admin/

# Start the development server
python manage.py runserver
```

### Frontend Setup

```bash
# In a separate terminal, from the project root
cd rag_gate-ui

# Install dependencies
npm install

# Start the dev server
npm run dev
# → Dashboard at http://localhost:5173
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Django secret key |
| `DATABASE_URL` | ✅ | `postgres://raggate:raggate_secret@localhost:5432/raggate` | PostgreSQL connection string |
| `REDIS_URL` | ✅ | `redis://localhost:6379/0` | Redis connection for quota enforcement |
| `CELERY_BROKER_URL` | ✅ | `redis://localhost:6379/1` | Celery broker (Redis) |
| `CELERY_RESULT_BACKEND` | ✅ | `redis://localhost:6379/2` | Celery result backend (Redis) |
| `OPENAI_API_KEY` | ✅ | — | [OpenAI API key](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | — | — | [Anthropic API key](https://console.anthropic.com/settings/keys) |
| `DEFAULT_OPENAI_COMPATIBLE_BASE_URL` | — | — | Default base URL for compatible providers (e.g., `https://api.groq.com/openai/v1`) |
| `DEFAULT_OPENAI_COMPATIBLE_API_KEY` | — | — | Default API key for compatible provider |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/` | Proxy chat completion (unary or streaming) |
| `GET` | `/api/v1/quota/` | Check remaining daily quota |
| `GET` | `/api/v1/analytics/` | Aggregated usage analytics for the dashboard |

All endpoints require `Authorization: Api-Key <key>` header.

## Testing

```bash
cd rag_gate
python -m pytest tests/ --ds=core.test_settings -v

# With coverage report
python -m pytest tests/ --ds=core.test_settings --cov=. --cov-report=term-missing
```

## License

[MIT](LICENSE)