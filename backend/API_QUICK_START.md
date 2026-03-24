# QuantDog API Quick Start Guide

## 📚 API Documentation

This API provides comprehensive stock market analysis capabilities including technical indicators, sentiment analysis, macro environment insights, and AI-powered research.

### Documentation Files

- **Complete API Guide**: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - Detailed documentation with examples
- **OpenAPI Specification**: [openapi.yaml](./openapi.yaml) - OpenAPI 3.0 spec for API tools
- **Summary**: This quick start guide

---

## 🚀 Quick Start

### 1. Start the API Server

```bash
cd backend
python -m quantdog.api
```

The API will start at `http://localhost:8000`

### 2. Health Check

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "ok"
}
```

### 3. Run Complete Analysis

#### Step 3a: Ingest Market Data

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

#### Step 3b: Perform Fast Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analysis/fast \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "700.HK",
    "horizon": "1d"
  }'
```

**Response**:
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "symbol": "700.HK",
    "horizon": "1d",
    "analysis": {
      "decision": "BUY",
      "confidence": 55,
      "score": 0.8,
      "reasons": [
        "Short-term trend is bullish (SMA20 > SMA50)",
        "RSI indicates bullish momentum (50.5)"
      ],
      "indicators_snapshot": {
        "close": 507.5,
        "sma20": 525.27,
        "rsi14": 50.50
      }
    }
  }
}
```

---

## 📊 Core Endpoints

### Instruments

**Search Instrument**
```
GET /api/v1/instruments/search?query=AAPL
```

**Get Instrument Details**
```
GET /api/v1/instruments/AAPL
```

### Market Data

**Get OHLCV Bars**
```
GET /api/v1/instruments/700.HK/bars?start=2024-01-01&end=2024-12-31
```

**Get Technical Indicators**
```
GET /api/v1/instruments/700.HK/indicators
```

### Analysis

**Fast Analysis**
```
POST /api/v1/analysis/fast
{
  "symbol": "700.HK",
  "horizon": "1d"
}
```

### Market Intelligence

**Technical Analysis**
```
POST /api/v1/market/technical
{
  "symbol": "700.HK"
}
```

**News & Twitter Sentiment**
```
POST /api/v1/market/intel
{
  "symbol": "700.HK",
  "limit": 20
}
```

**Macro Environment Analysis**
```
POST /api/v1/market/macro
{
  "symbol": "700.HK"
}
```

### Strategy & Monitoring

**Get Stock Strategy**
```
POST /api/v1/stocks/700.HK/strategy
{
  "horizon": "1d"
}
```

**Monitor Multiple Stocks**
```
POST /api/v1/stocks/monitor
{
  "symbols": ["700.HK", "AAPL"],
  "horizon": "1d"
}
```

---

## 🔧 Configuration

### Required Configuration

Create `.env` file in `/backend` directory:

```bash
# Database
DATABASE_URL=sqlite:///quantdog.db

# Longbridge (Market Data)
LONGBRIDGE_APP_KEY=your_app_key
LONGBRIDGE_APP_SECRET=your_app_secret
LONGBRIDGE_ACCESS_TOKEN=your_access_token

# OpenNews (News Data)
OPENNEWS_BASE_URL=https://ai.6551.io
OPENNEWS_TOKEN=your_token

# Twitter (Sentiment Data)
TWITTER_BASE_URL=https://ai.6551.io
TWITTER_TOKEN=your_token

# FRED (Macro Data)
FRED_BASE_URL=https://api.stlouisfed.org/fred
FRED_API_KEY=your_fred_api_key

# Feature Flags
ENABLE_AI_ANALYSIS=true
RESEARCH_ENABLED=true
```

### API Configuration

```python
API_HOST=0.0.0.0
API_PORT=8000
LOG_DIR=./logs
```

---

## 📝 Response Format

### Success Response

```json
{
  "code": 1,
  "msg": "success",
  "data": {
    // Response data
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

---

## 🎯 Common Use Cases

### 1. Technical Analysis

Get technical indicators and buy/sell signal:

```bash
curl -X POST http://localhost:8000/api/v1/analysis/fast \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "horizon": "1d"}'
```

### 2. Multi-Stock Monitoring

Monitor a portfolio of stocks:

```bash
curl -X POST http://localhost:8000/api/v1/stocks/monitor \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "MSFT", "GOOGL"], "horizon": "1d"}'
```

### 3. Market Intelligence

Get news sentiment analysis:

```bash
curl -X POST http://localhost:8000/api/v1/market/intel \
  -H "Content-Type: application/json" \
  -d '{"symbol": "700.HK", "limit": 20}'
```

### 4. Macro Analysis

Understand macro environment:

```bash
curl -X POST http://localhost:8000/api/v1/market/macro \
  -H "Content-Type: application/json" \
  -d '{"symbol": "700.HK"}'
```

### 5. Data Ingestion

Ingest historical market data:

```bash
curl -X POST http://localhost:8000/api/v1/ingestions \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "adjusted": true
  }'
```

---

## 🧪 Testing

Run API tests:

```bash
cd backend
python -m pytest tests/test_analysis_api.py -v
```

Quick verification:

```bash
cd backend
python verify.py
```

---

## 🛠️ Error Handling

### Common Errors

**Database not configured**:
```json
{
  "code": 0,
  "msg": "Database not configured",
  "error": {
    "type": "configuration_error",
    "detail": "DATABASE_URL not set"
  }
}
```

**Symbol not found**:
```json
{
  "code": 0,
  "msg": "No bars found",
  "error": {
    "type": "not_found",
    "detail": "No bars found for AAPL. Ingest data first."
  }
}
```

**Invalid request**:
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

## 📖 Additional Resources

### Data Sources

- **Market Data**: [Longbridge OpenAPI](https://open.longbridge.com/docs)
- **News Data**: 6551.ai OpenNews API
- **Twitter Data**: 6551.ai Twitter API  
- **Macro Data**: St. Louis Fed [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html)

### Supported Features

✅ Technical Analysis (SMA, RSI, MACD, Support/Resistance)
✅ News Sentiment Analysis
✅ Twitter Sentiment Analysis
✅ Macro Environment Analysis
✅ Strategy Synthesis
✅ Batch Monitoring
✅ AI-Powered Research (requires RESEARCH_ENABLED=true)

### Known Limitations

⚠️ VIX volatility data not available via Longbridge
⚠️ Research feature requires LLM configuration
⚠️ Rate limits apply to external APIs (Longbridge, FRED)

---

## 📞 Support

For detailed information, see:
- Complete API Documentation: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
- FRED API Configuration: [FRED_API_CONFIG.md](./FRED_API_CONFIG.md)
- Testing Report: [COMPLETE_TEST_REPORT.txt](./COMPLETE_TEST_REPORT.txt)

---

## 🔄 Version History

- **v1.0** (2024-03-24): Initial release
  - Longbridge market data integration
  - Full technical analysis capabilities
  - News and Twitter sentiment analysis
  - Macro environment analysis
  - AI-powered research

---

**API Version**: v1  
**Base URL**: `http://localhost:8000`  
**Documentation Last Updated**: 2024-03-24
