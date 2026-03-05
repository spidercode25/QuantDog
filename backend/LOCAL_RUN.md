# QuantDog 本地运行指南

无需 Docker，直接在命令行运行 QuantDog。

## 前置要求

- Python 3.12+
- pip

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
cd backend
python init_db.py
```

这会创建一个 SQLite 数据库 `quantdog.db`。

### 3. 启动 API 服务器

```bash
cd backend
python run_api.py
```

API 将在 http://127.0.0.1:8000 运行。

### 4. 测试 API

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 搜索股票
curl "http://127.0.0.1:8000/api/v1/instruments/search?query=AAPL"

# 创建 ingestion 任务
curl -X POST http://127.0.0.1:8000/api/v1/ingestions \
  -H "Content-Type: application/json" \
  -d '{"symbol": "MSFT", "start_date": "2024-01-01", "end_date": "2024-12-31", "adjusted": true}'

# 运行 worker 处理任务
cd backend
python run_worker.py --once
```

## 可用 API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/` | GET | 服务信息 |
| `/api/v1/health` | GET | API v1 健康检查 |
| `/api/v1/readyz` | GET | 就绪检查 (需要 DB) |
| `/api/v1/instruments/search` | GET | 搜索股票 |
| `/api/v1/instruments/{symbol}/bars` | GET | 获取 K 线api/v1/in数据 |
| `/struments/{symbol}/indicators` | GET | 获取技术指标 |
| `/api/v1/ingestions` | POST | 创建数据摄取任务 |
| `/api/v1/analysis/fast` | POST | 快速分析 |

## 配置

编辑 `backend/.env` 文件:

```bash
DATABASE_URL=sqlite:///./quantdog.db
API_HOST=127.0.0.1
API_PORT=8000
ENABLE_AI_ANALYSIS=false
RESEARCH_ENABLED=false
```

## 启用研究功能

如需启用 AI 多智能体研究功能:

```bash
# 编辑 .env
RESEARCH_ENABLED=true
ENABLE_AI_ANALYSIS=true
```

然后重新启动 API。

## 注意事项

- SQLite 仅支持单 worker 运行（不支持 `FOR UPDATE SKIP LOCKED`）
- 如需 PostgreSQL 支持，使用 Docker Compose
- yfinance 可能因网络问题无法获取数据
