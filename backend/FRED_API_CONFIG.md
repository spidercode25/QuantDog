# FRED API 配置指南

## 如何配置 FRED API Key

QuantDog 系统支持通过 FRED (Federal Reserve Economic Data) API 获取美国宏观经济数据，用于分析市场环境并确定宏观主题。

### 获取 FRED API Key

1. 访问 St. Louis Fed FRED API 网站: https://fred.stlouisfed.org/docs/api/api_key.html
2. 点击 "Request API Key" 按钮
3. 注册或登录账号
4. 获取您的 API Key (格式类似: `abc123xyz456`)

### 配置方法

#### 方法 1: 使用 .env 文件 (推荐)

在 `backend/.env` 文件中添加以下行:

```bash
# FRED API 配置
FRED_BASE_URL=https://api.stlouisfed.org/fred
FRED_API_KEY=your_actual_api_key_here
```

#### 方法 2: 使用环境变量

在运行应用前设置环境变量:

```bash
# Linux/Mac
export FRED_API_KEY="your_actual_api_key_here"

# Windows PowerShell
$env:FRED_API_KEY="your_actual_api_key_here"

# Windows CMD
set FRED_API_KEY=your_actual_api_key_here
```

#### 方法 3: 在 Docker Compose 中配置

编辑 `docker-compose.yml` 文件，在 api 和 worker 服务中添加环境变量:

```yaml
services:
  api:
    environment:
      - FRED_BASE_URL=https://api.stlouisfed.org/fred
      - FRED_API_KEY=your_actual_api_key_here
    # ... 其他配置

  worker:
    environment:
      - FRED_BASE_URL=https://api.stlouisfed.org/fred
      - FRED_API_KEY=your_actual_api_key_here
    # ... 其他配置
```

### 验证配置

运行 FRED API 连接测试:

```bash
cd backend
python test_fred_api.py
```

预期输出:
```
[OK] yield_10y (GS10): 4.25 (2024-03-24)
[OK] fed_rate (FEDFUNDS): 5.25 (2024-03-24)
[OK] cpi (CPIAUCSL): 310.2 (2024-02-01)
[OK] dxy (DTWEXBGS): 104.5 (2024-03-22)
```

### FRED API 功能

配置 FRED API 后，系统将能够:

1. **获取宏观数据指标**
   - 美国国债收益率 (10年、2年期)
   - 联邦基金利率
   - CPI 和核心 CPI
   - 美元指数 (DXY)
   - 收益率曲线斜率

2. **确定宏观主题**
   - Growth (成长) - 收益率曲线倒置
   - Rates (利率) - 美联储利率高于 CPI
   - Inflation (通胀) - 高 CPI 或 breakeven
   - Liquidity (流动性) - 强势美元
   - None (无明确主题)

3. **增强策略分析**
   - 结合技术分析、情绪分析和宏观环境
   - 提供更全面的市场视角
   - 改进交易决策的准确性

### 使用的 FRED 数据系列

| 数据名称 | FRED Series ID | 描述 |
|----------|----------------|------|
| yield_10y | GS10 | 10年期国债收益率 |
| yield_2y | DGS2 | 2年期国债收益率 |
| fed_rate | FEDFUNDS | 联邦基金利率 |
| cpi | CPIAUCSL | 消费物价指数 |
| core_cpi | CPILFESL | 核心消费物价指数 |
| dxy | DTWEXBGS | 贸易加权美元指数 |
| breakeven | T10YIE | 10年期盈亏平衡通胀率 |

### 注意事项

1. **API 限制**: FRED API 有请求频率限制（默认每天 120 次请求）
2. **数据延迟**: FRED 数据通常有 1-2 天的延迟
3. **缓存机制**: 系统会缓存宏观数据以减少 API 调用
4. **错误处理**: 如果 API 调用失败，系统会优雅降级，不影响其他功能

### 故障排除

#### 问题: "FRED API Key not set"
**解决方案**: 按照上述配置方法设置 FRED_API_KEY

#### 问题: "Macro data retrieval failed"
**解决方案**:
1. 检查 API Key 是否正确
2. 运行 `python test_fred_api.py` 验证 API 连接
3. 检查网络连接是否正常

#### 问题: "Rate limit exceeded"
**解决方案**: 等待一段时间后重试，系统会使用缓存的宏观数据

### 获取帮助

如需更多帮助，请参考:
- FRED API 文档: https://fred.stlouisfed.org/docs/api/api_key.html
- FRED 数据系列搜索: https://fred.stlouisfed.org/
- QuantDog 文档: https://github.com/your-repo/quantdog
