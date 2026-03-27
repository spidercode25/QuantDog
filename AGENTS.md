# QuantDog Agent Guidelines

Agentic coding agents working in this repository should follow these conventions.

---

## Build and Test Commands

**Test suite:**
```bash
cd backend && pytest -q                    # Run all tests
cd backend && pytest -q tests/test_health.py::test_health  # Run single test
```

**Lint and formatting:**
```bash
cd backend && ruff check .                 # Lint code
```

**Type checking:**
```bash
# Pyright runs with basic type checking (see pyrightconfig.json)
# No explicit command needed - IDEs or CI handle it
```

**Database migrations:**
```bash
# Inside Docker compose
docker compose exec -T api alembic upgrade head

# From host (cd to backend first)
cd backend && alembic upgrade head
```

**Dev stack:**
```bash
docker compose up -d --build               # Start full stack
```

---

## Code Style Guidelines

### Imports and File Headers

**File structure order:**
1. Pyright directives (optional, suppress warnings as needed)
2. `from __future__ import annotations`
3. Standard library imports
4. Third-party imports
5. Local imports from `quantdog` module (absolute paths)

**Examples:**
```python
# pyright: reportMissingImports=false, reportUnknownVariableType=false

from __future__ import annotations

import logging
from dataclasses import dataclass

from flask import Blueprint, request

from quantdog.api.envelope import error, success  # pyright: ignore[reportImplicitRelativeImport]
from quantdog.infra.sqlalchemy import get_engine
from quantdog.config import get_settings
```

### Naming Conventions

- **Functions and variables:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE` (for module-level constants)
- **Private members:** `_prefix` (single underscore)

```python
@dataclass(frozen=True, slots=True)
class DbCheckResult:
    ok: bool

def get_engine(database_url: str) -> Engine:
    pass

_MAX_RETRIES = 3
_status = "pending"
```

### Type Hints

- Use type hints on all function signatures
- Optional types: `str | None` (Python 3.10+ syntax)
- Keyword-only args: `*, timeout_seconds: float = 1.0`

```python
def check_db_connectivity(
    database_url: str | None,
    *,
    timeout_seconds: float = 1.0,
) -> DbCheckResult:
    pass
```

### Error Handling

**Return error state, don't raise from API handlers:**
```python
@instruments_bp.get("/instruments/<symbol>")
def get_instrument(symbol: str):
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error", detail="DATABASE_URL not set")
    return success({"instrument": instrument})
```

**Use dataclasses for error results:**
```python
@dataclass(frozen=True, slots=True)
class DbCheckResult:
    ok: bool
    error_type: str | None = None
    detail: str | None = None
```

### API Response Envelope

**v1 endpoints must use the envelope contract:**
```python
# Success
return success({"status": "ok"}, msg="success", status_code=200)
# Returns: {"code": 1, "msg": "success", "data": {"status": "ok"}}

# Error
return error("Not found", error_type="not_found", detail="Symbol not found", status_code=404)
# Returns: {"code": 0, "msg": "Not found", "error": {"type": "not_found", "detail": "Symbol not found"}}
```

**Never return raw Flask responses for v1 endpoints.**

### Logging

```python
import logging

logger = logging.getLogger("quantdog.module.name")

logger.info("Processing %s", symbol)
logger.warning("Retry %s/%s", attempt, max_attempts)
logger.error("Failed to fetch: %s", e)
```

### Dataclasses

Use frozen dataclasses with slots for value objects:
```python
@dataclass(frozen=True, slots=True)
class Settings:
    api_host: str
    api_port: int
    database_url: str | None
```

### Pydantic Models

For complex schemas, use Pydantic with extra forbid:
```python
from pydantic import BaseModel, Field

class ResearchRun(BaseModel):
    model_config = {"extra": "forbid"}
    run_id: str = Field(description="Unique run identifier")
    symbol: str = Field(description="Stock symbol")
```

### Database Patterns

**SQLAlchemy engines:**
```python
from quantdog.infra.sqlalchemy import get_engine

engine = get_engine(settings.database_url)
with engine.connect() as conn:
    result = conn.execute(text("SELECT ..."))
    conn.commit()
```

**Text queries with parameters:**
```python
from sqlalchemy import text

conn.execute(
    text("SELECT * FROM instruments WHERE symbol = :symbol"),
    {"symbol": query}
)
```

### Test Structure

```python
import pytest

def test_endpoint_name():
    # Set up env before import
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data["code"] == 1

    # Cleanup
    os.environ.pop("DATABASE_URL", None)
```

---

## Architecture

**Module layout:**
- `backend/quantdog/api/` - Flask API surface (blueprints, routes)
- `backend/quantdog/domain/` - Domain objects/invariants (reserved)
- `backend/quantdog/services/` - Use-cases/orchestration (reserved)
- `backend/quantdog/infra/` - DB/providers/clients
- `backend/quantdog/jobs/` - Worker runtime and job queue
- `backend/quantdog/analysis/` - Technical indicators and analysis
- `backend/quantdog/research/` - Research agents and LLM orchestration
- `backend/quantdog/memory/` - Memory retrieval and embedding
- `backend/quantdog/screening/` - Screening and watchlists
- `backend/quantdog/config/` - Configuration and settings
- `backend/quantdog/utils/` - Utility functions
- `backend/tests/` - Test files

**Feature flags:**
- `RESEARCH_ENABLED` - Enable research agents (default: false)
- `ENABLE_AI_ANALYSIS` - Enable AI analysis (default: false)

---

## Type Checking Configuration

Pyright runs in `basic` mode with most warnings suppressed for expedited development. Type hints are encouraged but not enforced via CI.

---

## Testing Notes

Tests use SQLite `:memory:` for fast test execution. Set `DATABASE_URL` before importing the app to connect to in-memory DB.
