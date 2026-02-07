# Stock Science - 个人量化交易分析系统

## 项目简介

**Stock Science** 是一个基于技术分析和东财掘金SDK的个人量化交易分析系统。系统通过掘金量化终端的专用数据接口获取稳定的股票交易数据，提供精准的选股信号和交易建议。

### 核心功能

- **StockPre**: 沪深300成分股筛选系统 - 自动扫描成分股，基于技术指标筛选买入信号
- **Stock Grain Ranking**: 多维评分股票分析系统 - 对指定股票进行多维度评分，提供买卖建议

### 适用场景

- 📊 **个人选股**: 从沪深300成分股中筛选符合技术指标的股票
- 📈 **个股分析**: 对指定股票进行深度技术分析，获取买卖建议
- 💰 **策略验证**: 回测交易策略的历史表现
- 📚 **量化学习**: 了解技术分析指标在量化交易中的应用

### 核心特性

- 🚀 **稳定数据源**: 使用东财掘金SDK，专用协议获取数据，稳定可靠
- 💾 **本地缓存**: 数据缓存24小时，大幅提升运行速度（90%+）
- 🔄 **智能容错**: 主数据源失败时自动切换到备用数据源
- ⚡ **高效处理**: 多线程并发处理，保持快速响应
- 📊 **多维分析**: 结合均线、MACD、RSI、BOLL、成交量等多个技术指标

---

## 📚 项目文档

详细文档请查看 `docs/` 文件夹：

- **[docs/README.md](docs/README.md)** - 文档索引
- **[Python环境配置](docs/PYTHON_ENVIRONMENT.md)** - Anaconda Python环境设置
- **[项目配置指南](docs/PROJECT_SETUP.md)** - 环境配置详解
- **[数据源文档](docs/akshare_data_sources.md)** - 数据源使用说明
- **[评估报告](docs/FINAL_EVALUATION_REPORT.md)** - 系统评估报告

---

## 数据源说明

### 主要数据源：东财掘金SDK

本项目使用**东财掘金量化终端SDK**作为主要数据源：

- **数据质量**: 高质量、实时更新的交易数据
- **连接方式**: 专用协议，不受HTTP网络环境影响
- **数据范围**: 支持A股全市场股票、指数、期货等
- **更新频率**: 实时数据，盘中可获取最新行情

### 获取掘金SDK Token

1. 访问 [掘金量化官网](https://www.myquant.cn/)
2. 注册账号并登录
3. 在个人中心获取 Token
4. 配置到 `config_data_source.py` 文件中

```python
# config_data_source.py 示例
'token': 'your_token_here'  # 替换为您的Token
```

### 备用数据源

系统配置了 Baostock 作为备用数据源，当主数据源不可用时自动切换。

---

## 快速开始

### 环境要求

- **Python**: 3.9+ (推荐使用Anaconda)
- **Python路径**: `D:\ProgramData\anaconda3\python.exe` (Anaconda base环境)
- 掘金SDK (gm 3.0+)
- 东财掘金账号和 Token

### 安装依赖

使用Anaconda Python安装依赖：

```cmd
D:\ProgramData\anaconda3\python.exe -m pip install -r requirements.txt
D:\ProgramData\anaconda3\python.exe -m pip install gm  # 掘金SDK
```

或使用便捷脚本：

```cmd
run_python.bat -m pip install -r requirements.txt
```

### 配置数据源

1. 配置环境变量（推荐）：
   编辑 `.env` 文件，填入您的掘金Token：
   ```bash
   DIGGOLD_TOKEN=your_token_here
   ```

2. 或配置文件：
   编辑 `data/config_data_source.py`，填入您的掘金Token：
   ```python
   'token': 'xxxxxxxxxxxxxxxx'  # 替换为您的Token
   ```

### 运行示例

#### StockPre - 沪深300成分股筛选

使用Anaconda Python：
```cmd
D:\ProgramData\anaconda3\python.exe strategies\stockPre.py
```

或使用便捷脚本：
```cmd
run_python.bat strategies\stockPre.py
```

**输出示例**:
```
=== 买入信号股票推荐 (按累计收益率降序) ===
名称                  代码             最新日期        股价      收益率       判定依据
晶澳科技                002459.SZ      2026-02-06   12.27 178.32%  均线金叉 + MACD金叉
海康威视                002415.SZ      2026-02-06   32.64 148.75%  均线金叉 + MACD金叉
```

#### Stock Grain Ranking - 个股多维评分分析

使用Anaconda Python：
```cmd
cd stock_grain_ranking
D:\ProgramData\anaconda3\python.exe main.py -s 600489 601088 -b 20250207 -e 20260207
```

或使用便捷脚本：
```cmd
cd stock_grain_ranking
..\run_python.bat main.py -s 600489 601088 -b 20250207 -e 20260207
```

**参数说明**:
- `-s`: 股票代码（多个代码用空格分隔）
- `-b`: 开始日期（格式：YYYYMMDD）
- `-e`: 结束日期（格式：YYYYMMDD，默认当天）

---

## 功能特性详解

### StockPre 系统

**功能描述**:
- 自动获取沪深300成分股列表
- 使用掘金SDK获取高质量股票数据
- 计算技术指标（均线、MACD、RSI、BOLL、成交量）
- 基于多条件筛选买入信号（至少满足2个条件）
- 进行策略回测验证
- 按累计收益率排序输出推荐股票

**技术指标**:
- **均线**: 5日均线、20日均线
- **MACD**: 快线(12)、慢线(26)、信号线(9)
- **RSI**: 14日相对强弱指标
- **BOLL**: 20日布林带
- **成交量**: 3日平均成交量及变化率

**筛选条件**:
- 均线金叉（5日均线 > 20日均线）
- MACD金叉（MACD > MACD信号线）
- RSI超卖（RSI < 30）
- 股价触及BOLL下轨
- 成交量放大20%以上

### Stock Grain Ranking 系统

**功能描述**:
- 对指定股票进行技术指标计算
- 生成多维评分（买入评分 + 卖出压力）
- 动态调整买入/卖出阈值
- 集成宏观经济数据（CPI、GDP、PMI、汇率）
- 提供详细的买卖建议和评分构成

---

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.9+ | 主要编程语言 |
| pandas | 2.2.3 | 数据处理 |
| numpy | 1.23.5 | 数值计算 |
| gm (掘金SDK) | 3.0.180 | **主要数据源** |
| TA-Lib | - | 技术指标计算 |

---

## 项目结构

```
stockScience/
├── docs/                           # 项目文档
│   ├── README.md                   # 文档索引
│   ├── PROJECT_SETUP.md            # 配置指南
│   ├── akshare_data_sources.md     # 数据源文档
│   ├── FINAL_EVALUATION_REPORT.md  # 评估报告
│   └── 专业交易监控系统.md          # 交易系统文档
├── strategies/                      # 策略模块
│   ├── stockPre.py                 # 沪深300筛选系统
│   └── stockRanking.py             # 多维评分系统
├── data/                           # 数据模块
│   ├── data_resilient.py           # 数据获取（掘金SDK优先）
│   ├── diggold_data.py             # 掘金SDK封装
│   └── cache_manager.py            # 缓存管理
├── stock_grain_ranking/            # 个股分析模块
│   ├── main.py                     # 主程序
│   ├── indicators.py               # 技术指标
│   ├── signals.py                  # 信号生成
│   └── backtest.py                 # 回测模块
├── analysis/                       # 分析脚本
├── utils/                          # 工具模块
├── tests/                          # 测试脚本
├── cache/                          # 缓存目录
├── .env                            # 环境变量（Token等）
├── .env.example                    # 环境变量模板
├── config_data_source.py           # 数据源配置
├── requirements.txt                # Python依赖
├── CLAUDE.md                       # Claude AI配置
└── README.md                       # 本文件
```

---

## 安全说明

⚠️ **重要提示**:

- `config_data_source.py` 包含您的私人Token，已在 `.gitignore` 中忽略
- 请勿将 `config_data_source.py` 提交到公开仓库
- 请勿将您的Token分享给他人
- 建议定期更换Token以保证安全

---

## 版本历史

### v2.0 (2026-02-08) - 掘金SDK集成

**重大更新**:
- 集成东财掘金SDK作为主要数据源
- 新增 `diggold_data.py` 掘金SDK封装模块
- 新增 `config_data_source.py` 数据源配置文件
- 更新 `data_resilient.py` 支持多数据源配置
- 创建配置文件模板 `config_data_source.py.example`
- 更新 `.gitignore` 保护敏感配置

**数据源优先级**:
1. 东财掘金SDK（主要，稳定）
2. Baostock（备用）
3. AkShare（可选，已禁用）

### v1.2 (2026-02-07) - 本地缓存机制

**新增功能**:
- 本地缓存机制，速度提升90%+
- API失败自动重试3次

---

## 常见问题

### Q: 为什么使用掘金SDK而不是免费的AkShare？

A: 掘金SDK有以下优势：
- 数据质量更高，更新更及时
- 使用专用协议，不受HTTP网络环境影响
- 提供更多数据维度和功能
- 更稳定可靠，适合个人量化交易

### Q: Token安全吗？

A: Token存储在 `config_data_source.py` 中，该文件已在 `.gitignore` 中忽略，不会被提交到公开仓库。

### Q: 如何获取掘金SDK Token？

A: 访问 https://www.myquant.cn/ 注册账号，在个人中心即可获取Token。

---

## 许可证

本项目仅供个人学习和研究使用，不构成投资建议。投资有风险，入市需谨慎。

---

**最后更新**: 2026-02-08
**数据源**: 东财掘金量化终端SDK
