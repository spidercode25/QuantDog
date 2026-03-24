# QuantDog API Documentation

欢迎访问 QuantDog API 服务接口文档！

## 📚 文档列表

### 🚀 快速开始
- **[API_QUICK_START.md](./API_QUICK_START.md)** - 快速入门指南，包含常用示例
  - 5分钟快速上手
  - 核心端点列表
  - 常用使用场景
  - 错误处理指南

### 📖 完整文档
- **[API_DOCUMENTATION.md](./API_DOCUMENTATION.md)** - 完整 API 参考文档
  - 所有端点详细说明
  - 请求/响应示例
  - 数据源介绍
  - 限流说明
  - 版本历史

### 🔧 规范文件
- **[openapi.yaml](./openapi.yaml)** - OpenAPI 3.0 规范文件
  - 可用于 API 工具（如 Swagger UI、Postman）
  - 标准化 API 定义
  - Schema 定义

### ⚙️ 配置指南
- **[FRED_API_CONFIG.md](./FRED_API_CONFIG.md)** - FRED API 配置说明
  - 如何获取 API Key
  - 配置方法
  - 故障排除

---

## 🌐 API 基本信息

**Base URL**: `http://localhost:8000`

**API Version**: v1

**Documentation Version**: 1.0.0

**Last Updated**: 2024-03-24

---

## 🎯 核心功能

### 1. 市场数据获取
- ✅ 实时和历史 K 线数据
- ✅ 支持多市场（HK、US、CN）
- ✅ 数据提供商：Longbridge OpenAPI

### 2. 技术分析
- ✅ 移动平均线 (SMA20, SMA50)
- ✅ 相对强弱指标 (RSI14)
- ✅ 指数平滑异同移动平均线 (MACD)
- ✅ 支撑/阻力位识别

### 3. 情绪分析
- ✅ 新闻情绪分析 (6551 AI)
- ✅ Twitter 情绪分析
- ✅ 综合情绪评分

### 4. 宏观环境分析
- ✅ 美国国债收益率
- ✅ 利率环境
- ✅ 消费者物价指数 (CPI)
- ✅ 宏观主题确定

### 5. 策略综合
- ✅ 多源数据融合
- ✅ 技术评分
- ✅ 情绪评分
- ✅ 宏观评分
- ✅ 风险过滤

### 6. AI 驱动研究
- ✅ 多阶段代理分析
- ✅ 质量评分
- ✅ 最终决策生成

---

## 📊 端点分类

### 健康检查
```
GET /health
GET /api/v1/health
GET /api/v1/readyz
```

### 证券信息
```
GET /api/v1/instruments/search
GET /api/v1/instruments/{symbol}
```

### 市场数据
```
GET /api/v1/instruments/{symbol}/bars
GET /api/v1/instruments/{symbol}/indicators
```

### 分析
```
POST /api/v1/analysis/fast
```

### 市场智能
```
POST /api/v1/market/technical
POST /api/v1/market/intel
POST /api/v1/market/macro
```

### 策略与监控
```
POST /api/v1/stocks/{symbol}/strategy
GET /api/v1/stocks/{symbol}/monitor
POST /api/v1/stocks/monitor
```

### 数据摄取
```
POST /api/v1/ingestions
```

### 研究
```
POST /api/v1/research/runs
GET /api/v1/research/runs/{run_id}
GET /api/v1/research/runs/{run_id}/result
```

---

## 🚀 立即开始

### 1. 快速测试

```bash
curl http://localhost:8000/health
```

### 2. 获取技术分析

```bash
curl -X POST http://localhost:8000/api/v1/analysis/fast \
  -H "Content-Type: application/json" \
  -d '{"symbol": "700.HK", "horizon": "1d"}'
```

### 3. 查看完整文档

- **快速入门**: [API_QUICK_START.md](./API_QUICK_START.md)
- **完整文档**: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
- **OpenAPI 规范**: [openapi.yaml](./openapi.yaml)

---

## 💡 使用建议

### 开发环境
1. 参考 [API_QUICK_START.md](./API_QUICK_START.md) 快速上手
2. 运行测试脚本验证集成
3. 查看 [COMPLETE_TEST_REPORT.txt](./COMPLETE_TEST_REPORT.txt) 了解测试结果

### 生产部署
1. 配置所有必需的环境变量
2. 参考 [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) 的限流说明
3. 使用 [openapi.yaml](./openapi.yaml) 生成客户端 SDK

### API 集成
1. 导入 [openapi.yaml](./openapi.yaml) 到 Swagger UI / Postman
2. 根据 [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) 调用端点
3. 实现错误处理逻辑

---

## 🛠️ 故障排除

### 常见问题

**问：API 返回 400 错误**
- 答：检查请求参数格式和必填字段

**问：无数据返回**
- 答：确认已摄取数据，使用 `/api/v1/ingestions` 端点

**问：研究功能 404**
- 答：设置 `RESEARCH_ENABLED=true` 环境变量

**问：宏观数据不可用**
- 答：配置 `FRED_API_KEY` 环境变量

详细故障排除请参考：
- [FRED_API_CONFIG.md](./FRED_API_CONFIG.md) - FRED 配置问题
- [COMPLETE_TEST_REPORT.txt](./COMPLETE_TEST_REPORT.txt) - 系统状态

---

## 📞 获取帮助

### 文档
- [API_QUICK_START.md](./API_QUICK_START.md) - 快速入门
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - 完整文档
- [openapi.yaml](./openapi.yaml) - OpenAPI 规范

### 测试与验证
- [verify.py](./verify.py) - 快速验证脚本
- [test_*.py](./tests/) - 完整测试套件

### 配置文件
- [.env](./.env) - 环境变量配置
- [FRED_API_CONFIG.md](./FRED_API_CONFIG.md) - FRED 配置指南

---

## 📝 更新日志

### v1.0.0 (2024-03-24)
- ✅ Longbridge 市场数据集成
- ✅ 完整技术分析功能
- ✅ 新闻和推特情绪分析
- ✅ 宏观环境分析（FRED）
- ✅ AI 驱动研究能力
- ✅ 策略综合与监控
- ✅ 完整 API 文档

---

**API Base URL**: `http://localhost:8000`

**支持市场**: HK, US, CN

**数据源**: Longbridge, 6551 AI, FRED

**技术栈**: Flask, SQLAlchemy, Longbridge SDK

---

## 🔗 相关链接

- Longbridge OpenAPI: https://open.longbridge.com/docs
- FRED API: https://fred.stlouisfed.org/docs/api/api_key.html
- OpenAPI Specification: https://swagger.io/specification/

---

**祝您使用愉快！** 🚀
