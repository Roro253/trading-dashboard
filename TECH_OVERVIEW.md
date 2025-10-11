# Tech Overview

## Backend
- **Framework:** FastAPI `0.110.0` (`server/pyproject.toml`).
- **Entry point:** `server/app/main.py` builds the FastAPI application and configures middleware/logging.
- **API router:** `server/app/api/routes.py` exposes `/api/run/{ticker}`, `/api/ensemble/{ticker}`, `/api/performance`, `/api/history`, `/api/stream/{ticker}` (SSE stream).
- **Settings:** `app.core.config.get_settings()` loads env vars (CORS defaults to `http://localhost:3000`, `EVENT_BLACKOUT_ISO` parsed for risk windows); Structlog config lives in `app/core/logging.py`.
- **Streaming:** `ticker_event_stream()` (SSE via `sse-starlette`) fans out pub/sub data using Redis when available, falling back to in-memory queues.
- **Polygon client:** Async wrapper in `server/app/services/polygon_client.py` (httpx with retry/fallbacks).
- **Decision pipeline:** `StrategyOrchestrator` composes agents, risk, portfolio, and auditor; `_persist_decisions()` persists results, snapshots, and publishes stream events.

## Frontend
- **Framework:** Next.js `14.1.0` App Router (`web/app`).
- **Root layout/page:** `web/app/layout.tsx` and `web/app/page.tsx` mount the dashboard shell.
- **Dashboard UI:** `web/components/Dashboard.tsx` renders sidebar/main panels (`AlertDraftPanel`, `AuditTrail`, `HistoryTable`, `PerformancePanel`).
- **Data access:** `web/lib/api.ts` wraps `fetch` using `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000`) for `/api/ensemble`, `/api/history`, `/api/performance`.
- **Styling:** CSS Modules in `web/styles/*.module.css`.

## Database & Storage
- **Engine:** PostgreSQL via SQLAlchemy 2.x async (`postgresql+asyncpg`), connection assembled in `server/app/db/session.py`.
- **Migrations:** Alembic managed under `server/alembic/versions/` (e.g., `202402160001_create_core_tables.py`, `202402160002_add_eval_ts_to_agent_signals.py`).
- **Core tables (`server/app/db/models.py`):**
  - `alerts`: overall decisions, confidence, risk flags, portfolio snapshots, auditor notes, RTH ticket.
  - `agent_signals`: per-agent outputs with eval horizons and snapshots.
  - `metrics_snapshots`: rolling agent performance metrics.
- **Portfolio Snapshot:** Alerts capture contributors, side scores, market evidence, and auditor check summaries (top-three checks) in `alerts.portfolio_snapshot` with digests mirrored in `alerts.auditor_notes`.

## Agents & Orchestration
- **Agents:** Implemented under `server/app/services/agents/` (`technical.py`, `rth_playbook.py`) sharing `base.Agent`.
- **Orchestrator:** `server/app/services/orchestrator.py` coordinates market fetches, agent execution, portfolio weighting, risk, and auditing.
- **Risk/Audit:** `server/app/services/risk_manager.py` enforces temporal/liquidity guards; `app/services/auditor.py` performs overrides and attaches notes.
- **Workers:** Background evaluator entry point lives in `server/app/workers/evaluator.py`.

## Repository Layout
- `server/`: FastAPI backend (Poetry project, tests in `server/tests`).
- `web/`: Next.js frontend (TypeScript, React 18).
- `infra/`: Alembic migrations and infra scaffolding.
- `docker-compose.yml`: Local stack (API, frontend, Postgres, Redis).
