# QuantDog API Service Interface Documentation

## Overview

QuantDog API is a RESTful API for stock market analysis, providing technical indicators, news sentiment analysis, macro environment insights, and AI-powered research capabilities.

**Base URL**: `http://localhost:8000`

**API Version**: v1

## Table of Contents

1. [General Information](#general-information)
2. [Response Format](#response-format)
3. [Error Handling](#error-handling)
4. [Endpoints](#endpoints)
   - [Health & System](#health--system)
   - [Instruments](#instruments)
   - [Bars](#bars)
   - [Indicators](#indicators)
   - [Analysis](#analysis)
   - [Market Intelligence](#market-intelligence)
   - [Stocks](#stocks)
   - [Ingestion](#ingestion)
   - [Research](#research)
5. [Data Sources](#data-sources)
6. [Rate Limits](#rate-limits)

---

## General Information

### Authentication

Currently, QuantDog API does not require authentication for public endpoints. However, research endpoints require the `RESEARCH_ENABLED=true` configuration flag.

### Supported Markets

- **HK**: Longbridge LV1 Real-time Quotes
- **US**: Nasdaq Basic
- **CN**: LV1 Real-time Quotes

### Request Headers

All endpoints accept standard HTTP headers. For idempotent operations:

```
Idempotency-Key: <unique-request-id>
```

### Symbol Format

- US stocks: `AAPL` or `AAPL.US` (auto-converts to `AAPL.US`)
- HK stocks: `700.HK`
- CN stocks: `000001.SZ`

---

## Response Format

All v1 endpoints use a standardized response envelope.

### Success Response

```json
{
  "code": 1,
  "msg": "success",
  "data": {
    // Response data specific to endpoint
  }
}
```

### Error Response

```json
{
  "code": 0,
  "msg": "Error message",
  "error": {
    "type": "error_type",
    "detail": "Detailed error information"
  }
}
```

### HTTP Status Codes

- `200 OK` - Successful request
- `202 Accepted` - Request accepted, job queued
- `400 Bad Request` - Invalid request parameters
- `404 Not Found` - Resource not found or feature disabled
- `503 Service Unavailable` - Database or service unavailable

---

## Error Handling

### Common Error Types

| Error Type | Description |
|------------|-------------|
| `invalid_request` | malformed request or invalid parameters |
| `missing_field` | required field is missing |
| `invalid_field` | field value is invalid |
| `not_found` | requested resource not found |
| `configuration_error` | system configuration issue (e.g., database) |
| `feature_disabled` | requested feature is disabled |
| `job_enqueue_error` | failed to enqueue background job |

### Error Example

```json
{
  "code": 0,
  "msg": "Symbol is required",
  "error": {
    "type": "missing_field",
    "detail": "symbol field is required"
  }
}
```

---

## Endpoints

### Health & System

#### GET `/health`

Liveness probe endpoint.

**Response**:
```json
{
  "status": "ok"
}
```

#### GET `/api/v1/health`

Health check with v1 envelope format.

**Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "status": "ok"
  }
}
```

#### GET `/api/v1/readyz`

Readiness probe with database connectivity check.

**Response** (200 OK):
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "status": "ok"
  }
}
```

**Response** (503 Service Unavailable):
```json
{
  "code": 0,
  "msg": "not ready",
  "error": {
    "type": "db_unavailable",
    "detail": "DB connectivity check failed"
  }
}
```

#### GET `/api/v1/openapi.json`

OpenAPI 3.x specification document for the API.

---

### Instruments

#### GET `/api/v1/instruments/search`

Search for instruments by symbol query. Creates placeholder instrument if not found.

**Query Parameters**:
- `query` (required): Stock symbol to search

**Example Request**:
```
GET /api/v1/instruments/search?query=AAPL
```

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "instrument": {
      "symbol": "AAPL",
      "name": null,
      "exchange": null,
      "type": null,
      "currency": null,
      "active": true
    }
  }
}
```

#### GET `/api/v1/instruments/<symbol>`

Get instrument details by symbol.

**Path Parameters**:
- `symbol`: Stock symbol

**Example Request**:
```
GET /api/v1/instruments/AAPL
```

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "instrument": {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "exchange": "NASDAQ",
      "type": "EQUITY",
      "currency": "USD",
      "active": true
    }
  }
}
```

---

### Bars

#### GET `/api/v1/instruments/<symbol>/bars`

Get daily OHLCV bars for a symbol.

**Path Parameters**:
- `symbol`: Stock symbol

**Query Parameters**:
- `start` (optional): Start date in YYYY-MM-DD format
- `end` (optional): End date in YYYY-MM-DD format
- `adjusted` (optional): Use adjusted prices (default: `true`)
- `limit` (optional): Maximum rows to return (default: 1000, max: 5000)

**Example Request**:
```
GET /api/v1/instruments/700.HK/bars?start=2024-01-01&end=2024-12-31&adjusted=true&limit=100
```

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "bars": [
      {
        "symbol": "700.HK",
        "bar_date": "2024-01-01",
        "ts_utc": 1704067200,
        "open": 400.0,
        "high": 405.0,
        "low": 398.0,
        "close": 403.0,
        "volume": 10000000,
        "adjusted": true,
        "source": "longbridge"
      }
    ],
    "count": 50
  }
}
```

---

### Indicators

#### GET `/api/v1/instruments/<symbol>/indicators`

Get technical indicators for a symbol.

**Path Parameters**:
- `symbol`: Stock symbol

**Query Parameters**:
- `start` (optional): Start date in YYYY-MM-DD format (defaults to 90 days ago)
- `end` (optional): End date in YYYY-MM-DD format (defaults to today)
- `adjusted` (optional): Use adjusted prices (default: `true`)
- `limit` (optional): Maximum bars to fetch for calculation (default: 100, max: 252)

**Example Request**:
```
GET /api/v1/instruments/700.HK/indicators?start=2024-01-01&end=2024-12-31&adjusted=true&limit=100
```

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "symbol": "700.HK",
    "bars_count": 90,
    "indicators": {
      "sma20": 525.19,
      "sma50": 559.68,
      "rsi14": 50.50,
      "macd": -10.25,
      "macd_signal": -10.25,
      "macd_histogram": 0.0,
      "recent_high": 558.50,
      "recent_low": 498.40,
      "last_close": 507.50
    }
  }
}
```

---

### Analysis

#### POST `/api/v1/analysis/fast`

Perform fast technical analysis on a symbol.

**Request Body**:
```json
{
  "symbol": "700.HK",
  "horizon": "1d"
}
```

**Parameters**:
- `symbol` (required): Stock symbol
- `horizon` (optional): Analysis horizon - one of `1d`, `1w`, `1m` (default: `1d`)

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "symbol": "700.HK",
    "horizon": "1d",
    "analysis": {
      "symbol": "700.HK",
      "decision": "BUY",
      "confidence": 55,
      "score": 0.8,
      "reasons": [
        "Short-term trend is bullish (SMA20 > SMA50)",
        "RSI indicates bullish momentum (50.5)",
        "Price near support level"
      ],
      "indicators_snapshot": {
        "close": 507.5,
        "sma20": 525.27,
        "sma50": 559.68,
        "rsi14": 50.50,
        "macd": -10.25,
        "macd_histogram": 0.0,
        "recent_high": 558.5,
        "recent_low": 498.4
      }
    },
    "ai_enabled": false,
    "ai_error": null,
    "baseline_used": true
  }
}
```

---

### Market Intelligence

#### POST `/api/v1/market/technical`

Perform technical analysis with indicators.

**Request Body**:
```json
{
  "symbol": "700.HK",
  "horizon": "1d"
}
```

**Parameters**:
- `symbol` (required): Stock symbol
- `horizon` (optional): Analysis horizon (default: `1d`)

**Response**: Technical analysis object with indicators and decision

#### POST `/api/v1/market/intel`

Get news and Twitter sentiment analysis.

**Request Body**:
```json
{
  "symbol": "700.HK",
  "limit": 20
}
```

**Parameters**:
- `symbol` (required): Stock symbol
- `limit` (optional): Maximum number of items (default: 20)

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "symbol": "700.HK",
    "news_count": 10,
    "twitter_count": 20,
    "sentiment": "neutral",
    "sentiment_score": 0.067,
    "source_status": {
      "news_cache": "miss",
      "news_provider": "ok",
      "twitter_provider": "ok"
    }
  }
}
```

#### POST `/api/v1/market/macro`

Get macro environment analysis.

**Request Body**:
```json
{
  "symbol": "700.HK",
  "limit": 20
}
```

**Parameters**:
- `symbol` (required): Stock symbol
- `limit` (optional): Limit for data fetching (default: 20)

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "symbol": "700.HK",
    "macro_theme": "inflation",
    "yield_10y": 4.13,
    "fed_rate": 3.64,
    "cpi": 327.46,
    "market_sentiment": "neutral"
  }
}
```

---

### Stocks

#### POST `/api/v1/stocks/<symbol>/strategy`

Get comprehensive strategy analysis for a stock.

**Path Parameters**:
- `symbol`: Stock symbol

**Request Body**:
```json
{
  "horizon": "1d",
  "limit": 20
}
```

**Parameters**:
- `horizon` (optional): Analysis horizon (default: `1d`)
- `limit` (optional): Data limit (default: 20)

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "decision": "HOLD",
    "confidence": 30,
    "combined_score": -0.31,
    "inputs": {
      "technical_score": -0.5,
      "sentiment_score": 0.067,
      "macro_available": false
    },
    "risk_filter": {
      "vix_symbol": null,
      "vix": null,
      "regime": "unknown",
      "cash_target_pct": null,
      "rule": "VIX unavailable; skip regime gating"
    }
  }
}
```

#### GET `/api/v1/stocks/<symbol>/monitor`

Get monitoring snapshot for a single stock.

**Path Parameters**:
- `symbol`: Stock symbol

**Query Parameters**:
- `horizon` (optional): Analysis horizon (default: `1d`)
- `limit` (optional): Data limit (default: 20)

#### POST `/api/v1/stocks/monitor`

Get monitoring snapshot for multiple stocks.

**Request Body**:
```json
{
  "symbols": ["700.HK", "AAPL"],
  "horizon": "1d",
  "limit": 20
}
```

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "results": [
      {
        "symbol": "700.HK",
        "decision": "HOLD",
        "confidence": 30
      },
      {
        "symbol": "AAPL",
        "decision": "BUY",
        "confidence": 55
      }
    ],
    "alerts": []
  }
}
```

---

### Ingestion

#### POST `/api/v1/ingestions`

Enqueue a bar ingestion job to fetch and store market data.

**Request Body**:
```json
{
  "symbol": "700.HK",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "adjusted": true
}
```

**Parameters**:
- `symbol` (required): Stock symbol
- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (required): End date in YYYY-MM-DD format
- `adjusted` (optional): Use adjusted prices (default: `true`)

**Example Response** (201 Created):
```json
{
  "code": 1,
  "msg": "Job enqueued",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "dedupe_key": "ingest:700.HK:1d:2024-01-01:2024-12-31:adjusted=true"
  }
}
```

**Example Response** (Duplicated job):
```json
{
  "code": 1,
  "msg": "Job enqueued (or deduplicated)",
  "data": {
    "message": "Job already exists",
    "dedupe_key": "ingest:700.HK:1d:2024-01-01:2024-12-31:adjusted=true"
  }
}
```

---

### Research

**Note**: Research endpoints require `RESEARCH_ENABLED=true` configuration.

#### POST `/api/v1/research/runs`

Create a new AI-powered research run.

**Request Body**:
```json
{
  "symbol": "700.HK",
  "horizon": "1w"
}
```

**Parameters**:
- `symbol` (required): Stock symbol
- `horizon` (optional): Analysis horizon - one of `1d`, `1w`, `1m`, `3m`, `6m`, `1y` (default: `1w`)

**Headers** (Optional):
- `Idempotency-Key`: Unique identifier for idempotent requests

**Example Response** (202 Accepted):
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "run_id": "550e8400-e29b-41d4-a716-446655440000",
    "symbol": "700.HK",
    "horizon": "1w",
    "status": "pending"
  }
}
```

#### GET `/api/v1/research/runs/<run_id>`

Get research run status and progress.

**Path Parameters**:
- `run_id`: Research run ID

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "run_id": "550e8400-e29b-41d4-a716-446655440000",
    "symbol": "700.HK",
    "status": "completed",
    "requested_at": "2024-03-24T10:00:00Z",
    "started_at": "2024-03-24T10:00:01Z",
    "completed_at": "2024-03-24T10:00:30Z",
    "baseline_used": false,
    "quality_score": 0.85,
    "error_summary": null,
    "progress": {
      "phase1_complete": true,
      "phase2_complete": true,
      "phase3_complete": true,
      "agents_completed": 5
    }
  }
}
```

#### GET `/api/v1/research/runs/<run_id>/result`

Get final research run results including all agent outputs.

**Path Parameters**:
- `run_id`: Research run ID

**Example Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "run_id": "550e8400-e29b-41d4-a716-446655440000",
    "symbol": "700.HK",
    "status": "completed",
    "final_decision": "BUY",
    "final_confidence": 75,
    "baseline_used": false,
    "quality_score": 0.85,
    "requested_at": "2024-03-24T10:00:00Z",
    "started_at": "2024-03-24T10:00:01Z",
    "completed_at": "2024-03-24T10:00:30Z",
    "error_summary": null,
    "agent_outputs": [
      {
        "phase": 1,
        "agent_name": "TechnicalAgent",
        "status": "success",
        "output": "{\"signal\": \"BUY\", \"reason\": \"Strong bullish trend\"}",
        "validation_errors": [],
        "duration_ms": 2500,
        "model_id": "gpt-4"
      }
    ]
  }
}
```

---

## Data Sources

### Market Data
- **Provider**: Longbridge OpenAPI
- **Markets Available**:
  - HK: LV1 Real-time Quotes
  - US: Nasdaq Basic
  - CN: LV1 Real-time Quotes
- **Historical Data**: Up to several years available

### News Data
- **Provider**: 6551.ai OpenNews API
- **Coverage**: Global financial news
- **Latency**: Real-time with cache mechanism

### Twitter Data
- **Provider**: 6551.ai Twitter API
- **Coverage**: Market-related tweets
- **Sentiment Analysis**: Integrated NLP processing

### Macro Data
- **Provider**: St. Louis Fed FRED API
- **Indicators Available**:
  - US Treasury yields (10Y, 2Y)
  - Federal Funds Rate
  - CPI and Core CPI
  - US Dollar Index (DXY)
  - Breakeven inflation rates

---

## Rate Limits

Current implementation does not enforce API rate limits. However, external data providers may have their own limits:

- **Longbridge API**: 60 requests per 30 seconds
- **FRED API**: 120 requests per day
- **6551 APIs**: As configured by API token limits

---

## Usage Examples

### Complete Analysis Workflow

1. **Ingest Data**:
```bash
curl -X POST http://localhost:8000/api/v1/ingestions \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "700.HK",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "adjusted": true
  }'
```

2. **Perform Fast Analysis**:
```bash
curl -X POST http://localhost:8000/api/v1/analysis/fast \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "700.HK",
    "horizon": "1d"
  }'
```

3. **Get Strategy Analysis**:
```bash
curl -X POST http://localhost:8000/api/v1/stocks/700.HK/strategy \
  -H "Content-Type: application/json" \
  -d '{
    "horizon": "1d",
    "limit": 20
  }'
```

### Monitoring Multiple Stocks

```bash
curl -X POST http://localhost:8000/api/v1/stocks/monitor \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["700.HK", "AAPL", "9988.HK"],
    "horizon": "1d"
  }'
```

---

## Support & Resources

- **Documentation**: `backend/FRED_API_CONFIG.md` for FRED API configuration
- **Test Scripts**: `backend/verify.py` for quick verification
- **GitHub**: https://github.com/your-repo/quantdog

---

## Version History

- **v1.0** (2024-03-24): Initial release with Longbridge integration
  - Market data provider migration from YFinance to Longbridge
  - Full technical indicator support
  - News and Twitter sentiment analysis
  - Macro environment analysis via FRED
  - AI-powered research capabilities

---

## License

[Your License Information]
