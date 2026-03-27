# QuantDog 启动流程指南

## 1. 环境配置

创建 `backend/.env` 文件：

```bash
# 必需配置
DATABASE_URL=postgresql://postgres:postgres@db:5432/quantdog

# 可选配置（默认值）
API_HOST=0.0.0.0
API_PORT=8000
WORKER_NAME=quantdog-worker
WORKER_HEARTBEAT_SECONDS=10
LOG_DIR=/app/logs

# 功能开关
ENABLE_AI_ANALYSIS=false
RESEARCH_ENABLED=false
TELEGRAM_ENABLED=false

# Telegram bot 配置（如需启用）
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_API_TOKEN=<shared-service-token>
TELEGRAM_BASE_URL=https://api.telegram.org
TELEGRAM_POLL_TIMEOUT_SECONDS=30
TELEGRAM_POLL_LIMIT=100

# 数据源配置（可选）
FINNHUB_API_KEY=
```

## 2. 启动基础栈

```bash
# 启动所有服务
docker compose up -d --build

# 等待容器就绪后应用数据库迁移
docker compose exec -T api alembic upgrade head

# 验证服务状态
curl -s http://localhost:8000/api/v1/health | jq .
```

## 3. 启动 Telegram Bot（可选）

### 方式一：Docker Compose

```bash
# 启动 Telegram bot
docker compose --profile telegram up -d telegram-bot

# 如果在基础栈运行后启用 Telegram，需要重建 api 和 worker
docker compose up -d --build api worker
docker compose --profile telegram up -d telegram-bot
```

### 方式二：本地 Python 环境

```bash
cd backend

# 单次运行（测试用）
python run_telegram_bot.py --once

# 持续运行
python run_telegram_bot.py
```

## 4. 验证功能

### 基础 API 测试

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 搜索股票
curl "http://localhost:8000/api/v1/instruments/search?query=AAPL"

# 获取技术分析
curl -X POST http://localhost:8000/api/v1/analysis/fast \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "horizon": "1d"}'
```

### Telegram Bot 测试

在 Telegram 中发送命令：

```
/start    - 显示欢迎信息和 Chat ID
/help     - 显示帮助信息
/quote AAPL - 获取技术分析快照
/news AAPL  - 获取最新新闻
/twitter AAPL - 获取 Twitter 情绪
/macro cpi  - 获取宏观经济指标
```

### 出站消息测试

```bash
curl -X POST http://localhost:8000/api/v1/telegram/messages \
  -H "Authorization: Bearer $TELEGRAM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: telegram-demo-1" \
  -d '{
    "chat_id": "123456789",
    "text": "QuantDog alert: AAPL technical snapshot is ready"
  }'
```

## 5. 服务架构

启动后的服务架构：

```
┌─────────────────┐
│  Telegram Bot   │ (可选)
│  (Long Polling) │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   API Server    │
│   (Flask)       │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   PostgreSQL    │
│   (Database)    │
└─────────────────┘

┌─────────────────┐
│   Worker        │
│   (Background)  │
└─────────────────┘
```

## 6. 常用命令

```bash
# 查看日志
docker compose logs -f api
docker compose logs -f telegram-bot

# 停止服务
docker compose down

# 重启服务
docker compose restart api

# 查看容器状态
docker compose ps
```

## 7. 首次启动注意事项

### Telegram Bot 首次启动行为：
- 清除任何现有的 webhook
- 丢弃积压的 Telegram 更新
- 后续重启会保留待处理更新并从最后存储的 `update_id` 恢复

### 数据库迁移：
- 必须在启动后立即执行 `alembic upgrade head`
- 如果遇到迁移问题，可以检查 `backend/alembic/versions/` 目录

## 8. 故障排查

```bash
# 检查容器状态
docker compose ps

# 查看详细日志
docker compose logs api --tail 100

# 进入容器调试
docker compose exec api bash

# 检查数据库连接
docker compose exec api python -c "from infra.sqlalchemy import get_engine; print(get_engine('postgresql://postgres:postgres@db:5432/quantdog'))"
```

## 9. 功能测试验证

### 运行测试套件

```bash
cd backend

# 运行所有测试
pytest -q

# 运行特定测试
pytest -q tests/test_health.py::test_health

# 运行 Telegram 相关测试
pytest -q tests/test_telegram_bot_service.py -k macro
pytest -q tests/test_market_intel.py -k macro
```

### 验证 Telegram 功能

1. **Macro 功能测试**
   - `/macro cpi` - CPI 指标
   - `/macro fed rate` - 联邦基金利率
   - `/macro dxy` - 美元指数

2. **News 功能测试**
   - `/news AAPL` - Apple 新闻
   - `/news TSLA` - Tesla 新闻

3. **Twitter 功能测试**
   - `/twitter AAPL` - Apple Twitter 情绪
   - `/twitter TSLA` - Tesla Twitter 情绪

4. **Quote 功能测试**
   - `/quote AAPL` - Apple 技术分析
   - `/quote TSLA` - Tesla 技术分析

## 10. 环境变量说明

### 必需变量
- `DATABASE_URL` - PostgreSQL 数据库连接字符串

### 可选变量
- `API_HOST` - API 服务器监听地址（默认: 0.0.0.0）
- `API_PORT` - API 服务器端口（默认: 8000）
- `WORKER_NAME` - Worker 进程名称（默认: quantdog-worker）
- `WORKER_HEARTBEAT_SECONDS` - Worker 心跳间隔（默认: 10）
- `LOG_DIR` - 日志目录（默认: /app/logs）

### 功能开关
- `ENABLE_AI_ANALYSIS` - 启用 AI 分析功能（默认: false）
- `RESEARCH_ENABLED` - 启用研究功能（默认: false）
- `TELEGRAM_ENABLED` - 启用 Telegram 功能（默认: false）

### Telegram 配置
- `TELEGRAM_BOT_TOKEN` - Telegram Bot Token
- `TELEGRAM_API_TOKEN` - Telegram API Token（用于出站消息认证）
- `TELEGRAM_BASE_URL` - Telegram API 基础 URL（默认: https://api.telegram.org）
- `TELEGRAM_POLL_TIMEOUT_SECONDS` - 轮询超时时间（默认: 30）
- `TELEGRAM_POLL_LIMIT` - 轮询限制（默认: 100）

### 数据源配置
- `FINNHUB_API_KEY` - Finnhub API 密钥（用于股票数据）

## 11. 端口说明

- `8000` - API 服务器端口
- `5432` - PostgreSQL 数据库端口（内部）
- `5433` - PostgreSQL 数据库端口（外部映射）

## 12. 日志位置

- 容器内: `/app/logs/`
- 主机映射: `./logs/`

日志文件包括：
- `api.log` - API 服务器日志
- `worker.log` - Worker 进程日志
- `telegram-bot.log` - Telegram Bot 日志

## 13. 数据持久化

### PostgreSQL 数据
- 容器内: `/var/lib/postgresql/data`
- 主机映射: `./postgres-data/`

### 数据库迁移
- 迁移脚本: `backend/alembic/versions/`
- 迁移配置: `backend/alembic.ini`

## 14. 性能优化建议

### Worker 扩展
```bash
# 启动多个 Worker 实例
docker compose up -d --scale worker=3
```

### 资源限制
在 `docker-compose.yml` 中配置资源限制：
```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

## 15. 安全注意事项

1. **环境变量安全**
   - 不要将 `.env` 文件提交到版本控制
   - 使用强密码和安全的 API Token
   - 定期轮换密钥

2. **网络安全**
   - 在生产环境中使用 HTTPS
   - 配置防火墙规则
   - 限制数据库访问

3. **Telegram Bot 安全**
   - 保护 `TELEGRAM_API_TOKEN` 不被泄露
   - 验证所有入站消息
   - 限制出站消息的发送频率

## 16. 监控和维护

### 健康检查
```bash
# API 健康检查
curl http://localhost:8000/api/v1/health

# 就绪检查
curl http://localhost:8000/api/v1/readyz
```

### 日志监控
```bash
# 实时查看 API 日志
docker compose logs -f api

# 查看错误日志
docker compose logs api | grep ERROR
```

### 数据库维护
```bash
# 备份数据库
docker compose exec db pg_dump -U postgres quantdog > backup.sql

# 恢复数据库
docker compose exec -T db psql -U postgres quantdog < backup.sql
```

## 17. 更新和升级

### 更新代码
```bash
# 拉取最新代码
git pull

# 重新构建和启动
docker compose up -d --build

# 应用数据库迁移
docker compose exec -T api alembic upgrade head
```

### 回滚版本
```bash
# 回滚到上一个版本
git checkout HEAD~1

# 重新构建和启动
docker compose up -d --build
```

## 18. 常见问题

### Q: 容器启动失败
A: 检查端口占用和 Docker 资源限制

### Q: 数据库连接失败
A: 验证 `DATABASE_URL` 配置和数据库容器状态

### Q: Telegram Bot 无响应
A: 检查 `TELEGRAM_BOT_TOKEN` 配置和网络连接

### Q: API 返回 500 错误
A: 查看 API 日志和数据库迁移状态

### Q: Worker 不处理任务
A: 检查 Worker 日志和数据库连接

## 19. 联系和支持

- 查看项目文档: `README.md`
- 查看代理指南: `AGENTS.md`
- 查看清理报告: `CLEANUP_REPORT.md`

---

**最后更新**: 2026-03-27
**版本**: 1.0.0
