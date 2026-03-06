# 项目技术指标类接口使用文档

## 概述

本项目使用 **TA-Lib** 库计算技术指标，而非掘金量化接口自带的技术指标功能。

**数据流向：**
```
掘金接口(history/history_n) → 获取原始OHLCV数据 → TA-Lib计算指标 → 策略使用
```

---

## 一、使用的技术指标库

| 库名称 | 版本要求 | 用途 |
|--------|---------|------|
| **TA-Lib** | >=0.4.0 | 计算技术指标（MACD、KDJ、RSI等） |
| **Pandas** | - | 简单均线计算（备用） |

---

## 二、TA-Lib指标使用情况汇总

### 2.1 指标使用统计

| 指标名称 | TA-Lib函数 | 使用次数 | 参数设置 |
|---------|-----------|---------|---------|
| **SMA（简单移动平均线）** | `talib.SMA()` | 30+次 | timeperiod=5, 10, 20, 60, 120 |
| **MACD** | `talib.MACD()` | 12次 | fast=12, slow=26, signal=9 |
| **RSI（相对强弱指标）** | `talib.RSI()` | 14次 | timeperiod=6, 14 |
| **布林带 (BOLL)** | `talib.BBANDS()` | 12次 | timeperiod=20, nbdevup=2, nbdevdn=2 |
| **KDJ（随机指标）** | `talib.STOCH()` | 2次 | fastk=9, slowk=3, slowd=3 |
| **ADX（趋势强度）** | `talib.ADX()` | 4次 | timeperiod=14 |
| **ATR（真实波幅）** | `talib.ATR()` | 2次 | timeperiod=14 |

### 2.2 指标详细说明

#### 1. 均线系统 (SMA)
```python
# 使用示例
df['ma5'] = talib.SMA(close, timeperiod=5)
df['ma10'] = talib.SMA(close, timeperiod=10)
df['ma20'] = talib.SMA(close, timeperiod=20)
df['ma60'] = talib.SMA(close, timeperiod=60)
df['ma120'] = talib.SMA(close, timeperiod=120)
```

#### 2. MACD（指数平滑异同平均线）
```python
# 使用示例
macd, macd_signal, macd_hist = talib.MACD(
    close, 
    fastperiod=12,    # 快线周期
    slowperiod=26,    # 慢线周期
    signalperiod=9    # 信号线周期
)
df['macd'] = macd
df['macd_signal'] = macd_signal
df['macd_hist'] = macd_hist
```

#### 3. RSI（相对强弱指标）
```python
# 使用示例
df['rsi'] = talib.RSI(close, timeperiod=14)    # 标准14日RSI
df['rsi_6'] = talib.RSI(close, timeperiod=6)   # 6日RSI（短期）
```

#### 4. 布林带 (BOLL)
```python
# 使用示例
boll_upper, boll_mid, boll_lower = talib.BBANDS(
    close, 
    timeperiod=20,    # 20日均线
    nbdevup=2,        # 上轨标准差倍数
    nbdevdn=2         # 下轨标准差倍数
)
df['boll_upper'] = boll_upper
df['boll_mid'] = boll_mid
df['boll_lower'] = boll_lower
```

#### 5. KDJ（随机指标）
```python
# 使用示例
slowk, slowd = talib.STOCH(
    high, low, close,
    fastk_period=9,   # K线周期
    slowk_period=3,   # K线平滑
    slowd_period=3    # D线平滑
)
df['kdj_k'] = slowk
df['kdj_d'] = slowd
df['kdj_j'] = 3 * slowk - 2 * slowd  # J值计算
```

#### 6. ADX（平均趋向指数）
```python
# 使用示例
df['adx'] = talib.ADX(high, low, close, timeperiod=14)
```

#### 7. ATR（真实波幅）
```python
# 使用示例
df['atr'] = talib.ATR(high, low, close, timeperiod=14)
```

---

## 三、使用TA-Lib的文件清单

### 3.1 核心指标计算模块

| 文件路径 | 说明 | 包含指标 |
|---------|------|---------|
| `realtime_monitor/indicator_engine.py` | 指标计算引擎（最完整） | MA, MACD, RSI, KDJ, BOLL, ATR, ADX |
| `stock_grain_ranking/indicators.py` | 谷粒排名指标模块 | MA, MACD, RSI, BOLL |
| `stock_pre_ranking/indicators.py` | 盘前排名指标模块 | MA, MACD, RSI, BOLL |

### 3.2 策略文件

| 文件路径 | 说明 | 包含指标 |
|---------|------|---------|
| `strategies/stockRanking.py` | 股票评分策略 | MA, MACD, RSI, BOLL, ADX |
| `strategies/stockPre.py` | HS300筛选策略 | MA, MACD, RSI, BOLL |
| `strategies/stockPre_lite.py` | 轻量版筛选 | MA, MACD, RSI, BOLL |
| `strategies/volume_breakout_strategy.py` | 成交量突破策略 | MA |
| `strategies/jinfeng_realtime.py` | 实时分析策略 | MA, MACD, RSI, KDJ, BOLL, ATR, ADX |
| `strategies/analyze_jingao.py` | 个股分析工具 | MA, MACD, RSI, BOLL |
| `strategies/analyze_single.py` | 单股分析工具 | MA, MACD, RSI, BOLL |

### 3.3 工具文件

| 文件路径 | 说明 |
|---------|------|
| `utils/check_talib.py` | TA-Lib安装检查工具 |

---

## 四、核心代码示例

### 4.1 完整指标计算（来自 `realtime_monitor/indicator_engine.py`）

```python
import pandas as pd
import numpy as np
import talib

class IndicatorEngine:
    """技术指标计算引擎"""

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        volume = df['volume'].values.astype(float)

        # ========== 均线系统 ==========
        df['ma5'] = talib.SMA(close, timeperiod=5)
        df['ma10'] = talib.SMA(close, timeperiod=10)
        df['ma20'] = talib.SMA(close, timeperiod=20)
        df['ma60'] = talib.SMA(close, timeperiod=60)

        # ========== MACD ==========
        macd, macd_signal, macd_hist = talib.MACD(
            close, fastperiod=12, slowperiod=26, signalperiod=9
        )
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist

        # ========== RSI ==========
        df['rsi'] = talib.RSI(close, timeperiod=14)
        df['rsi_6'] = talib.RSI(close, timeperiod=6)

        # ========== KDJ ==========
        slowk, slowd = talib.STOCH(
            high, low, close,
            fastk_period=9, slowk_period=3, slowd_period=3
        )
        df['kdj_k'] = slowk
        df['kdj_d'] = slowd
        df['kdj_j'] = 3 * slowk - 2 * slowd

        # ========== 布林带 ==========
        boll_upper, boll_mid, boll_lower = talib.BBANDS(
            close, timeperiod=20, nbdevup=2, nbdevdn=2
        )
        df['boll_upper'] = boll_upper
        df['boll_mid'] = boll_mid
        df['boll_lower'] = boll_lower

        # ========== ATR ==========
        df['atr'] = talib.ATR(high, low, close, timeperiod=14)

        # ========== 成交量指标 ==========
        df['volume_ma5'] = talib.SMA(volume, timeperiod=5)

        # ========== ADX ==========
        df['adx'] = talib.ADX(high, low, close, timeperiod=14)

        return df
```

### 4.2 简化版指标计算（来自 `stock_grain_ranking/indicators.py`）

```python
import pandas as pd
import talib

class IndicatorsCalculator:
    @staticmethod
    def calculate_indicators(df):
        """计算技术指标"""
        close = df['close'].values

        # 均线
        df['ma5'] = talib.SMA(close, timeperiod=5)
        df['ma20'] = talib.SMA(close, timeperiod=20)

        # MACD
        macd, macd_signal, macd_hist = talib.MACD(
            close, fastperiod=12, slowperiod=26, signalperiod=9
        )
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist

        # RSI
        df['rsi'] = talib.RSI(close, timeperiod=14)

        # BOLL
        boll_upper, boll_mid, boll_lower = talib.BBANDS(
            close, timeperiod=20, nbdevup=2, nbdevdn=2
        )
        df['boll_upper'] = boll_upper
        df['boll_mid'] = boll_mid
        df['boll_lower'] = boll_lower

        return df.dropna()
```

---

## 五、指标参数标准化

项目中使用的指标参数已标准化：

| 指标 | 参数 | 说明 |
|------|------|------|
| MA5 | timeperiod=5 | 5日均线 |
| MA10 | timeperiod=10 | 10日均线 |
| MA20 | timeperiod=20 | 20日均线 |
| MA60 | timeperiod=60 | 60日均线 |
| MACD | fast=12, slow=26, signal=9 | 标准MACD参数 |
| RSI | timeperiod=14 | 标准14日RSI |
| RSI短周期 | timeperiod=6 | 6日RSI |
| BOLL | period=20, std=2 | 20日布林带 |
| KDJ | K=9, D=3, J=3 | 标准KDJ参数 |
| ADX | timeperiod=14 | 14日ADX |
| ATR | timeperiod=14 | 14日ATR |

---

## 六、信号生成示例

项目中基于这些指标生成的交易信号：

### 买入信号条件
- **MACD金叉**: MACD > Signal
- **RSI超卖**: RSI < 30
- **BOLL下轨**: 收盘价 < BOLL下轨
- **MA金叉**: MA5 > MA20

### 卖出信号条件
- **MACD死叉**: MACD < Signal
- **RSI超买**: RSI > 70
- **BOLL上轨**: 收盘价 > BOLL上轨

---

## 七、未使用的TA-Lib指标

以下TA-Lib指标在项目中**未被使用**：
- `talib.EMA()` - 指数移动平均线（使用SMA替代）
- `talib.WMA()` - 加权移动平均线
- `talib.CCI()` - 商品通道指数
- `talib.MOM()` - 动量指标
- `talib.ROC()` - 变动率指标
- `talib.WILLR()` - 威廉指标
- `talib.OBV()` - 能量潮指标
- `talib.SAR()` - 抛物线转向指标

---

## 八、总结

1. **项目中所有技术指标均通过TA-Lib计算**，掘金量化接口仅用于获取原始OHLCV数据
2. **最常用的指标**：SMA（30+次）、RSI（14次）、MACD（12次）、BOLL（12次）
3. **最完整的指标实现**：`realtime_monitor/indicator_engine.py` 包含8种指标
4. **指标参数已标准化**，符合行业通用标准
