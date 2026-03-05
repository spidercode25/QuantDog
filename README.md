# QuantDog

QuantDog is an API-first stock analysis MVP scaffold, inspired by QuantDinger.
**QuantDog is not affiliated with or endorsed by QuantDinger.**

## Quickstart

```bash
# Clone and start the stack
docker compose up -d --build

# Wait for containers to be ready, then apply migrations
docker compose exec -T api alembic upgrade head

# Verify the stack is running
curl -s http://localhost:8000/api/v1/health | jq .
```

## Architecture Overview

- **db**: PostgreSQL database for persistent storage
- **api**: Flask REST API server
- **worker**: Background job processor for data ingestion and analysis

## API Examples

### Health & Status

```bash
# Basic health check
curl http://localhost:8000/health

# API v1 health (no DB required)
curl http://localhost:8000/api/v1/health

# Readiness probe (requires DB)
curl http://localhost:8000/api/v1/readyz

# OpenAPI spec
curl http://localhost:8000/api/v1/openapi.json
```

### Instruments

```bash
# Search for a symbol (creates if not exists)
curl "http://localhost:8000/api/v1/instruments/search?query=AAPL"
```

### Bars (OHLCV Data)

```bash
# Get daily bars for a symbol
curl "http://localhost:8000/api/v1/instruments/AAPL/bars?start=2024-01-01&end=2024-12-31&limit=100"

# Get adjusted bars (default)
curl "http://localhost:8000/api/v1/instruments/AAPL/bars?adjusted=true&limit=50"
```

### Ingestion (Background Jobs)

```bash
# Enqueue an ingestion job
curl -X POST http://localhost:8000/api/v1/ingestions \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "tf": "1d",
    "start": "2024-01-01",
    "end": "2024-12-31",
    "adjusted": true
  }'

# Check job status
curl http://localhost:8000/api/v1/jobs/{job_id}
```

### Technical Indicators

```bash
# Get indicators for a symbol (requires bars to be ingested first)
curl "http://localhost:8000/api/v1/instruments/AAPL/indicators?start=2024-01-01"
```

### Fast Analysis

```bash
# Run rule-based analysis (no AI required)
curl -X POST http://localhost:8000/api/v1/analysis/fast \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "horizon": "1d"
  }'
```

## Configuration

The API/worker entrypoints load a local `.env` file (if present) using
`python-dotenv`.

Create a `.env` file:

```bash
# Required
DATABASE_URL=postgresql://postgres:postgres@db:5432/quantdog

# Optional - defaults shown
API_HOST=0.0.0.0
API_PORT=8000
WORKER_NAME=quantdog-worker
WORKER_HEARTBEAT_SECONDS=10
LOG_DIR=/app/logs

# Feature flags
ENABLE_AI_ANALYSIS=false
RESEARCH_ENABLED=false

# Provider keys (optional)
FINNHUB_API_KEY=
```

## Migrations (Alembic)

Alembic configuration lives under `backend/alembic/` and the revision scripts
live under `backend/alembic/versions/`.

To apply migrations inside the running Docker compose environment:

```bash
docker compose exec -T api alembic upgrade head
```

If you're running from the host Python environment (not Docker), run from the
`backend/` directory so `alembic.ini` is found:

```bash
cd backend
alembic upgrade head
```

Response envelope contract (v1 endpoints only):

- success: `{ "code": 1, "msg": "success", "data": <payload> }`
- error: `{ "code": 0, "msg": "<human message>", "error": {"type": "...", "detail": "..."} }`

Logs are written to stdout and to rotating files under `/app/logs` in the
container. `docker-compose.yml` mounts this to `./logs` on the host.

## Layout

- `backend/quantdog/api/` - Flask API surface
- `backend/quantdog/domain/` - domain objects/invariants (reserved)
- `backend/quantdog/services/` - use-cases/orchestration (reserved)
- `backend/quantdog/infra/` - DB/providers/clients
- `backend/quantdog/jobs/` - worker runtime and job queue
- `backend/quantdog/analysis/` - technical indicators and analysis

## Development

### Run tests

```bash
cd backend
pytest -q
```

### Run linter

```bash
cd backend
ruff check .
```

### Run a single test

```bash
cd backend
pytest -q tests/test_health.py::test_health
```

## Notes

- Research features are gated by `RESEARCH_ENABLED=false` by default.
- AI analysis features are gated by `ENABLE_AI_ANALYSIS=false` by default.
- The worker uses Postgres SKIP LOCKED for concurrent job processing - safe to scale to multiple replicas.
