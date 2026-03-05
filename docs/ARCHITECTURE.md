# QuantDog Architecture

## Overview

QuantDog is an API-first stock analysis backend designed for local-first deployment using Docker Compose. It provides REST APIs for market data ingestion, technical analysis, and optional AI-powered research.

## System Components

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                          │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐               │
│  │   db    │   │   api   │   │ worker  │               │
│  │ (Postgres)│ │ (Flask) │   │(Python) │               │
│  └─────────┘   └─────────┘   └─────────┘               │
│       │              │              │                   │
│       └──────────────┴──────────────┘                   │
│                      │                                   │
│              PostgreSQL Network                          │
└─────────────────────────────────────────────────────────┘
```

## Database Schema

### Core Tables

- **instruments**: Stock symbols and metadata
- **bars_1d**: Daily OHLCV data (adjusted and unadjusted)
- **jobs**: Background job queue with state management

### Key Design Decisions

1. **Job Deduplication**: Uses `dedupe_key` with partial unique index to prevent duplicate jobs
2. **Concurrency**: Uses `SELECT ... FOR UPDATE SKIP LOCKED` for safe multi-worker processing
3. **Crash Recovery**: Stale jobs (heartbeat > 5 min) are requeued

## Job Queue Architecture

### Job States

```
queued → running → succeeded / failed / requeued
```

### Claim Algorithm

```sql
BEGIN;
SELECT * FROM jobs
WHERE state = 'queued'
  AND dedupe_key = :key
  AND (locked_by IS NULL OR locked_by = :worker)
FOR UPDATE SKIP LOCKED
LIMIT 1;
-- Update state to 'running', set locked_by, locked_at, heartbeat_at
COMMIT;
```

### Crash Recovery

Jobs with stale heartbeat (> 5 minutes) are transitioned back to `queued` by any worker on startup.

### Scheduler Guard

Uses PostgreSQL advisory locks to ensure only one worker enqueues periodic refresh jobs:

```sql
SELECT pg_try_advisory_lock(1234567890);
```

## API Design

### Response Envelope

All v1 endpoints use a consistent response format:

**Success:**
```json
{
  "code": 1,
  "msg": "success",
  "data": { ... }
}
```

**Error:**
```json
{
  "code": 0,
  "msg": "human readable message",
  "error": {
    "type": "error_type",
    "detail": "detailed explanation"
  }
}
```

### Feature Flags

- `ENABLE_AI_ANALYSIS`: Controls AI-enhanced fast analysis
- `RESEARCH_ENABLED`: Controls multi-agent deep research features

Both default to `false` for safe-by-default operation.

## Technical Indicators

The analysis module provides:

- **SMA20/SMA50**: Simple Moving Averages
- **RSI14**: Relative Strength Index (14-period)
- **MACD**: Moving Average Convergence Divergence
- **Support/Resistance**: Recent high/low levels

### Baseline Analysis Rules

The rule-based analysis generates BUY/SELL/HOLD signals based on:

1. **Trend** (SMA crossover): +0.5 for bullish, -0.5 for bearish
2. **Momentum** (price vs SMA): +/- 0.3 based on distance
3. **RSI**: +0.4 oversold, -0.4 overbought
4. **MACD**: +0.3 bullish, -0.3 bearish
5. **Support/Resistance**: +/- 0.2 based on price position

Decision threshold: score >= 0.5 = BUY, score <= -0.5 = SELL, else HOLD

## Worker Design

### Startup Sequence

1. Load configuration from environment
2. Connect to database
3. Recover stale jobs (heartbeat timeout)
4. Enter poll loop

### Poll Loop

```
while running:
    1. Claim next available job (SKIP LOCKED)
    2. Execute job handler
    3. Update job state (succeeded/failed)
    4. Sleep for poll_interval seconds
```

### Job Types

- **ingestion**: Fetch and store bars from data providers
- **research_run**: Execute multi-agent analysis (when RESEARCH_ENABLED=true)

## Extension Points

### Adding New Indicators

1. Add calculation function in `backend/quantdog/analysis/indicators.py`
2. Update `calculate_indicators()` to include new indicator
3. Add endpoint in `backend/quantdog/api/indicators.py` if needed

### Adding New Data Providers

1. Create provider class implementing `MarketDataProvider` interface
2. Implement `fetch_bars_1d(symbol, start_date, end_date, adjusted)`
3. Register in provider factory

### Adding New Job Types

1. Add job kind to job handler registry
2. Implement handler function in appropriate module
3. Handler receives job payload and updates job state

## Testing Strategy

- **Unit Tests**: Pure functions (indicators, analysis rules)
- **Integration**: Docker Compose boot, health endpoints
- **CI**: No external API calls; use stub providers

## Security Considerations

- No authentication in MVP (API-only, local-first)
- Feature flags prevent accidental exposure of AI features
- Database credentials via environment variables only
- No storage of API keys in database

## Performance Notes

- Bars endpoint: max 5000 rows per request
- Indicators endpoint: max 252 bars (~1 year)
- Job dedupe prevents duplicate ingestion
- SKIP LOCKED enables safe horizontal worker scaling
