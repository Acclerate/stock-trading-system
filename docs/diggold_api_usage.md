# 掘金量化接口使用文档

## 项目掘金量化接口使用总览

当前项目使用**掘金量化（gm.api）**作为首选数据源，通过多数据源容错机制确保数据获取的稳定性。

---

## 一、核心数据模块

### 1. `data/diggold_data.py` - 掘金SDK封装层

这是项目中最完整的掘金接口封装，使用了以下API：

| 接口 | 用途 |
|------|------|
| `set_token()` | 初始化SDK认证 |
| `history()` | 获取历史K线数据（日/分钟级别） |
| `history_n()` | 获取最近N条数据 |
| `get_instruments()` | 获取股票列表 |
| `get_trading_dates()` | 获取交易日历 |
| `get_symbol_infos()` | 获取标的信息 |

**主要功能方法：**
- `get_stock_history()` - 获取股票历史数据（支持多频率、复权）
- `get_stock_history_n()` - 获取最近N条数据
- `get_stock_list()` - 获取股票列表
- `convert_symbol_to_diggold()` - 代码格式转换（600519 → SHSE.600519）

### 2. `data/data_resilient.py` - 多数据源容错层

作为项目主要数据入口，优先使用掘金SDK：

```python
# 导入的掘金接口
from gm.api import set_token, history, history_n, get_instruments

# 核心方法
_fetch_from_diggold()      # 使用掘金获取股票数据
_fetch_index_from_diggold() # 使用掘金获取指数数据
```

---

## 二、策略模块使用

### Efinance_Strategy 目录下的策略文件

以下策略文件都使用了 `from gm.api import *`：

- `style_ml_enhanced.py`
- `style_rotation_v3.py`
- `ml_strategy_enhanced.py`
- `ml_strategy.py`
- `style_rotation_v2.py`
- `style_rotation_strategy.py`
- `small_cap_strategy.py`
- `multi_factor_strategy.py`
- `intraday_trading_strategy.py`
- `index_enhancement_strategy.py`
- `bollinger_mean_reversion_strategy.py`

### 其他策略文件

| 文件 | 使用的掘金接口 |
|------|---------------|
| `strategies/jinfeng_realtime.py` | `set_token`, `history`, `history_n`, `get_instruments`, `get_trading_dates`, `current`, `last_tick` |
| `strategies/jinfeng_event_driven.py` | `run`, `MODE_LIVE`, `MODE_BACKTEST`, `ADJUST_PREV` |
| `strategies/volume_breakout_strategy.py` | `history_n` |
| `strategies/trend_stocks.py` | `get_instruments` |
| `strategies/analyze_jingao.py` | `set_token`, `current`, `history` |
| `strategies/low_volume_breakout/main.py` | `history_n` |
| `strategies/low_volume_breakout/stock_pool.py` | `get_symbols`, `stk_get_daily_mktvalue_pt` |

---

## 三、测试和工具文件

| 文件 | 用途 |
|------|------|
| `test_diggold_data.py` | 测试掘金数据获取 |
| `check_diggold_token.py` | 检查Token有效性 |
| `tests/test_env_token.py` | 环境变量Token测试 |
| `tests/verify_diggold.py` | 掘金接口验证 |

---

## 四、实际使用的掘金接口汇总

| 接口名称 | 使用场景 | 所在文件 |
|---------|---------|---------|
| `set_token()` | SDK初始化认证 | 多处 |
| `history()` | 获取历史K线数据 | `diggold_data.py`, `data_resilient.py`, `jinfeng_realtime.py` |
| `history_n()` | 获取最近N条数据 | `diggold_data.py`, `jinfeng_realtime.py`, `volume_breakout_strategy.py` |
| `get_instruments()` | 获取股票列表 | `diggold_data.py`, `data_resilient.py`, `trend_stocks.py` |
| `get_trading_dates()` | 获取交易日历 | `diggold_data.py`, `jinfeng_realtime.py` |
| `current()` | 获取当前行情 | `jinfeng_realtime.py`, `analyze_jingao.py` |
| `last_tick()` | 获取最新Tick | `jinfeng_realtime.py` |
| `get_symbol_infos()` | 获取标的信息 | `diggold_data.py` |
| `run()` | 策略运行框架 | `jinfeng_event_driven.py` |
| `MODE_LIVE` / `MODE_BACKTEST` | 运行模式 | `jinfeng_event_driven.py` |
| `ADJUST_PREV` | 前复权常量 | `jinfeng_event_driven.py` |

---

## 五、配置方式

Token配置在 `data/config_data_source.py` 中：

```python
'sources': {
    'diggold': {
        'name': '东财掘金SDK',
        'enabled': True,
        'priority': 1,  # 最高优先级
        'token': os.getenv('DIGGOLD_TOKEN', '')  # 从环境变量读取
    }
}
```

---

## 六、掘金量化历史数据接口参考

### 行情历史数据接口

| 接口名称 | 功能说明 |
|---------|---------|
| `history()` / `history_bars()` | 获取指定股票合约历史K线数据（日/分钟/Tick级别） |
| `get_history_instruments()` | 查询交易标的历史信息数据 |

**`history()` 常用参数：**
```python
from gm.api import *

# 获取历史行情
data = history(
    symbol='SZSE.000001',      # 股票代码
    frequency='1d',            # 周期: 1d(日), 60s(分钟), tick
    start_time='2023-01-01',   # 开始时间
    end_time='2024-01-01',     # 结束时间
    fields='open,high,low,close,volume',  # 返回字段
    adjust=ADJUST_PREV,        # 复权方式: 前复权
    df=True                    # 返回DataFrame格式
)
```

### 基本面数据接口

| 接口名称 | 功能说明 |
|---------|---------|
| `get_fundamentals()` | 查询基本面数据（财务数据） |
| `get_fundamentals_n()` | 查询基本面数据最新n条 |

### 交易标的信息接口

| 接口名称 | 功能说明 |
|---------|---------|
| `get_instruments()` | 查询最新交易标的信息 |
| `get_history_instruments()` | 查询交易标的历史信息 |
| `get_trading_dates()` | 查询交易日列表 |
| `get_previous_trading_date()` | 查询上一个交易日 |

### 板块/行业数据接口

| 接口名称 | 功能说明 |
|---------|---------|
| `get_industry()` | 获取行业分类 |
| `get_concept()` | 获取概念板块 |
| `get_constituents()` | 获取指数成分股 |

### 特色数据

掘金量化提供的数据包括：
- **近10年**日/分钟/Tick级别股票数据
- 财务、分红送配、行业、板块等数据
- 股指期货、商品期货连续数据
- 支持**前复权/后复权**数据获取

### 使用前提

1. 安装 SDK：`pip install gm`
2. 设置 Token：`set_token('your_token_id')`
3. 需要打开掘金终端，接口通过网络请求获取数据

---

## 七、总结

项目将掘金量化作为**首选数据源**，通过 `data_resilient.py` 实现了多数据源容错机制，当掘金接口失败时会自动降级到 Baostock 等备用数据源。

**数据流向：**
```
策略/分析模块 → data_resilient.py → 优先使用掘金SDK → 失败时降级到备用数据源
```
