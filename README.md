# Field Worker Tracker (FWT)

Backend (FastAPI + PostgreSQL/PostGIS) and web dashboard (React) for planning field work, collecting location events from workers' mobile devices, calculating attendance and payroll, and generating reports.

---

## Architecture & Layout

```
backend/   FastAPI app (src/fw/...), Alembic migrations, Procrastinate worker
web/       React dashboard (Vite, TypeScript, Tailwind, TanStack Router)
infra/     Docker Compose, Postgres + PostGIS init scripts
docs/      Architectural documentation, decision records, specifications
.agents/   Agent rules and skills
```

---

## Prerequisites

- [Docker](https://www.docker.com/) & Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python package manager, manages Python 3.12)
- [Node.js](https://nodejs.org/) v22+ and [pnpm](https://pnpm.io/) v12+

---

## Quick Start

### 1. Environment Configuration

```bash
cp .env.example .env
```

### 2. Start Services via Docker Compose

To start the full environment (PostGIS, API, Worker, Web, Mailpit):

```bash
docker compose up -d
```

- **API Liveness**: [http://localhost:8000/health](http://localhost:8000/health)
- **API Readiness**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)
- **Web Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Mailpit Web UI**: [http://localhost:8025](http://localhost:8025)

---

## Local Development (Without Full Docker)

### 1. Start Database & Mail Catcher Only

```bash
docker compose up -d db mail
```

### 2. Backend Setup & Migrations

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn fw.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd ../web
pnpm install
pnpm dev
```

### 4. Generate TypeScript Types from OpenAPI

```bash
cd web
pnpm run codegen:api
```

---

## Running Quality Checks

### Backend Checks

```bash
cd backend
uv run ruff check
uv run ruff format --check
uv run pyright
uv run lint-imports
uv run pytest
```

### Frontend Checks

```bash
cd web
pnpm run lint
pnpm run build
```

