# 低位放量突破策略 (Low Volume Breakout Strategy)

## 策略概述

本策略用于寻找长期低位震荡的中小盘股票，捕捉近期逐步放量的潜在机会。

### 策略逻辑

1. **中小市值**：20亿-200亿元
2. **长期低位震荡**：当前价格 < 250日最高价的60%
3. **近期逐步放量**：5日均量 > 20日均量 × 1.5，且20日均量 > 60日均量
4. **趋势转强**：收盘价 > MA60

## 目录结构

```
low_volume_breakout/
├── __init__.py       # 模块初始化
├── config.py         # 策略参数配置
├── stock_pool.py     # 股票池获取与筛选
├── indicators.py     # 技术指标计算
├── signals.py        # 信号生成逻辑
├── main.py           # 主入口程序
└── README.md         # 本文档
```

## 使用方法

### 基本使用

```bash
# 进入项目目录
cd D:/privategit/github/stockScience

# 运行策略（使用默认参数）
python strategies/low_volume_breakout/main.py
```

### 自定义参数

```bash
# 自定义市值范围
python strategies/low_volume_breakout/main.py --min-cap 30 --max-cap 150

# 自定义低位阈值和放量倍数
python strategies/low_volume_breakout/main.py --low-threshold 0.55 --volume-ratio 2.0

# 自定义输出Top N股票
python strategies/low_volume_breakout/main.py --top-n 30

# 完整参数示例
python strategies/low_volume_breakout/main.py \
    --min-cap 30 \
    --max-cap 150 \
    --low-threshold 0.55 \
    --volume-ratio 2.0 \
    --data-period 300 \
    --max-workers 8 \
    --top-n 50 \
    --end-date 2026-02-24
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--min-cap` | 20.0 | 最小市值（亿元） |
| `--max-cap` | 200.0 | 最大市值（亿元） |
| `--low-threshold` | 0.6 | 低位阈值（当前价格/250日最高价） |
| `--volume-ratio` | 1.5 | 放量倍数（5日均量/20日均量） |
| `--data-period` | 300 | 获取历史数据天数 |
| `--max-workers` | 8 | 并发处理线程数 |
| `--top-n` | 50 | 输出Top N股票 |
| `--end-date` | 今天 | 结束日期（YYYY-MM-DD） |

## 输出结果

### 控制台输出

```
====================================================================================================
低位放量突破策略 - 筛选结果
生成时间: 2026-02-24 17:45:30
====================================================================================================

【策略参数】
  市值范围: 20亿 - 200亿
  低位阈值: 60%
  放量倍数: 1.5x
  数据周期: 300天
  均线周期: MA5/MA20/MA60
  均量周期: VOL5/VOL20/VOL60

【筛选统计】
  分析总数: 1234
  买入信号: 45
  观望: 1189

【Top 50 结果】

排名  代码             名称        市值      价格      价位%    放量    趋势    得分    判定依据
--------------------------------------------------------------------------------------------------------
1     SHSE.600XXX                  45.2     12.35    55.2%   1.8x    1.05   85.3   低位(55.2%) + 放量(1.8x) + 趋势启动(105.0%)
...
```

### 文件输出

结果保存在 `outputs/low_volume_breakout/` 目录下，文件名格式：
```
stock_pool_YYYYMMDD_HHMMSS.txt
```

## 模块化使用

```python
from strategies.low_volume_breakout import (
    StrategyConfig,
    StockPoolManager,
    IndicatorCalculator,
    SignalGenerator,
    LowVolumeBreakoutStrategy
)

# 创建自定义配置
config = StrategyConfig(
    min_market_cap=30,
    max_market_cap=150,
    low_threshold=0.55,
    volume_ratio=2.0
)

# 运行策略
strategy = LowVolumeBreakoutStrategy(config)
results = strategy.run()

# 或者分步执行
pool_manager = StockPoolManager(config)
stock_pool = pool_manager.get_stock_pool()

signal_gen = SignalGenerator(config)
# ... 对每只股票进行分析
```

## 技术指标说明

| 指标 | 说明 |
|------|------|
| price_position | 价格位置 = 当前收盘价 / 250日最高价 |
| volume_expansion | 放量倍数 = 5日均量 / 20日均量 |
| volume_trend | 均量趋势 = 20日均量 / 60日均量 |
| trend_strength | 趋势强度 = 收盘价 / MA60 |
| amplitude_120 | 120日振幅 = (120日最高 - 120日最低) / 120日最低 |
| RSI | 相对强弱指标（14日） |
| BOLL | 布林带（20日，2倍标准差） |

## 依赖项

- pandas: 数据处理
- numpy: 数值计算
- 掘金SDK (gm.api): 数据获取
- data_resilient: 数据缓存和容错
- cache_manager: 缓存管理

## 注意事项

1. **数据源依赖**：本策略依赖掘金SDK获取数据，请确保已正确配置Token
2. **缓存机制**：策略使用24小时缓存，首次运行较慢，后续会快很多
3. **并发处理**：默认使用8个线程并发处理，可根据机器配置调整
4. **风险提示**：本策略仅供学习参考，不构成投资建议

## 更新日志

### v1.0.0 (2026-02-24)
- 初始版本发布
- 实现核心筛选逻辑
- 支持并发处理
- 支持命令行参数配置
