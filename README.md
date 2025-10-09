# Trading Dashboard

A full-stack trading analytics platform featuring a FastAPI backend and a Next.js frontend, packaged for fast onboarding with devcontainers, Docker Compose, and pre-commit automation.

## Getting Started

1. **Clone & configure**
   ```bash
   cp .env.example .env
   ```
2. **Launch services**
   ```bash
   docker compose up -d
   ```
   This boots Postgres (port 5432) and Redis (port 6379) with health checks enabled.
3. **(Optional) Use the Dev Container**
   - Open the repository in VS Code
   - Run the `Dev Containers: Reopen in Container` command for a fully provisioned Python 3.11 / Node 20 environment

## Backend (FastAPI)

```bash
cd server
poetry install
poetry run alembic upgrade head
make run  # starts uvicorn on http://localhost:8000
```

- Health check lives at `GET /health` and returns `{"status": "ok"}`.
- Re-run database migrations with `poetry run alembic upgrade head`.
- Execute tests and tooling:
  ```bash
  make test
  make typecheck
  make lint
  ```

## Frontend (Next.js)

```bash
cd web
pnpm install
pnpm dev  # runs on http://localhost:3000
```

The frontend consumes the backend via `NEXT_PUBLIC_API_BASE_URL` set in `.env`.

## Tooling & Quality Gates

- Pre-commit hooks format and lint Python + TypeScript; install them with:
  ```bash
  pre-commit install
  ```
- Docker Compose keeps Postgres and Redis data in named volumes (`db-data`, `redis-data`).
- The repository ships with `.editorconfig` and shared configs for consistent formatting.

## Troubleshooting

- To verify containers: `docker compose ps` and check for `healthy` status.
- If ports are already in use, stop existing local Postgres/Redis instances or adjust `docker-compose.yml`.
