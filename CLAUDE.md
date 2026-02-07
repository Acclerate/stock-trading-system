# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Stock Science is a quantitative stock analysis system with two main modules:

1. **StockPre** - HS300 stock screening system that scans CSI 300 constituent stocks and filters buy signals based on technical indicators
2. **Stock Grain Ranking** - Multi-dimensional scoring analysis system that provides buy/sell recommendations for specified stocks

Both systems use akshare for data fetching, pandas-ta for technical indicators, and implement a local cache mechanism with automatic retry logic.

## Development Commands

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run StockPre (HS300 Screening)
```bash
python stockPre.py
```

### Run Stock Grain Ranking (Individual Stock Analysis)
```bash
cd stock_grain_ranking
python main.py -s 600489 601088 -b 20250207 -e 20260207
```

Parameters:
- `-s/--symbols`: Stock codes (space-separated, e.g., `600489 601088`)
- `-b/--begin`: Start date (format: YYYYMMDD)
- `-e/--end`: End date (format: YYYYMMDD, defaults to today)

### Cache Management
```python
from cache_manager import CacheManager

# View cache statistics
stats = CacheManager.get_cache_stats()

# Clear expired cache
CacheManager.clear_expired_cache()

# Clear all cache
CacheManager.clear_all_cache()
```

## Architecture

### Data Layer
- **cache_manager.py**: Centralized cache management with 24-hour expiration
- **data_resilient.py**: Wrapper around akshare with automatic retry (3 attempts, 1-3s random delay)
  - `fetch_stock_data()`: Stock OHLCV data with caching
  - `fetch_macro_data()`: Macro economic data (CPI, GDP, PMI, FX)
  - `get_hs300_symbols()`: CSI 300 constituent list
  - `get_stock_info()`: Stock code to name mapping

### StockPre Module (stockPre.py)
Single-file monolithic implementation that:
1. Fetches HS300 symbols via `DataResilient.get_hs300_symbols()`
2. Iterates through each stock sequentially (no parallelization)
3. Calculates indicators using `pandas_ta` (MA5, MA20, MACD, RSI, BOLL, volume)
4. Generates buy signals when >=2 conditions are met
5. Backtests and ranks by cumulative returns

**Buy conditions**: MA golden cross, MACD golden cross, RSI oversold (<30), BOLL lower band touch, volume expansion (>20%)

### Stock Grain Ranking Module (stock_grain_ranking/)
Modular architecture with separate concerns:

- **data.py**: `DataFetcher` class wraps `DataResilient`, `DataCache` manages macro data
- **indicators.py**: `IndicatorsCalculator` - technical indicator calculations
- **signals.py**: `SignalGenerator` - multi-dimensional scoring system
  - Buy score: MACD momentum (30%), BOLL position (20%), RSI divergence (15%), volume-price (20%), macro factors (15%)
  - Sell pressure: trend decay (10%), overbought (10%), capital outflow (10%), drawdown pressure (10%)
  - Dynamic thresholds based on market regime (ADX-based trend/range detection) and volatility
- **backtest.py**: `BacktestStrategy` - returns calculation and performance metrics
- **main.py**: `MainExecutor` with 8-thread concurrent processing using `ThreadPoolExecutor`

### Macro Data Integration
The system integrates macroeconomic indicators from akshare:
- **CPI**: Consumer Price Index
- **GDP**: Gross Domestic Product (quarterly)
- **PMI**: Purchasing Managers Index
- **FX**: USD/CNY exchange rate

Macro data is loaded during `DataCache.initialize()` and used in signal scoring via `SignalGenerator.get_macro_score()`.

## Key Technical Details

### Cache Key Format
Stock data: `{symbol}_{start_date}_{end_date}.pkl` in `cache/stock/`
Macro data: `{data_type}.pkl` in `cache/macro/`

### Date Formats
- akshare uses `YYYYMMDD` string format
- Internal processing uses pandas datetime
- Symbol format: 6-digit code with `.SZ` (Shenzhen) or `.SH` (Shanghai) suffix

### Technical Indicator Parameters
- Moving averages: SMA(5), SMA(20)
- MACD: fast=12, slow=26, signal=9
- RSI: length=14
- BOLL: length=20, std=2.0
- ADX (for market regime): length=14, threshold=25

### Error Handling Pattern
All data fetching functions in `data_resilient.py` implement:
1. Cache lookup (if enabled)
2. Retry loop (max 3 attempts)
3. Random delay between retries (1-3 seconds)
4. Graceful fallback (returns empty DataFrame or raises with context)

## Module Dependencies

```
stockPre.py
  ├── data_resilient.py
  │   └── cache_manager.py
  └── pandas_ta

stock_grain_ranking/main.py
  ├── data.py
  │   ├── data_resilient.py
  │   │   └── cache_manager.py
  │   └── cache_manager.py
  ├── indicators.py (pandas_ta)
  ├── signals.py (uses DataCache.macro_data)
  └── backtest.py
```

## Important Notes

1. **Cache expiration**: All cached data expires after 24 hours by default (`CACHE_EXPIRE_HOURS = 24`)

2. **Symbol handling**: Stock symbols need special handling:
   - Raw symbols from HS300 list include `.SZ`/`.SH` suffixes
   - For akshare API calls, strip the suffix (keep only 6 digits)
   - For name lookup, use the base 6-digit code

3. **Concurrent processing**: Only `stock_grain_ranking/main.py` uses parallel processing (8 workers). `stockPre.py` processes sequentially.

4. **Market regime detection**: Stock Grain Ranking uses ADX > 25 to detect trending markets vs ranging markets, which affects buy/sell thresholds.

5. **Macro data dates**: Different macro indicators have different date formats:
   - CPI: "YYYY年MM月" format
   - GDP: "YYYY年第X季度" format
   - PMI: "YYYY年MM月" format

The `parse_quarter()` function in `main.py` handles various quarter string formats for GDP data parsing.

## MCP Configuration

This project uses **Tavily MCP Server** for web search capabilities, configured in `.claude/config.json`:

```json
{
  "mcpServers": {
    "tavily-search": {
      "command": "npx",
      "args": ["-y", "@tavily/mcp-server"],
      "env": {
        "TAVILY_API_KEY": "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"
      }
    }
  }
}
```

**Purpose**: Provides real-time web search for stock news, market sentiment, and research without using zhipu web search quota.

**Usage**: When you need to search for:
- Real-time stock news and announcements
- Market sentiment analysis
- Company events and developments
- Industry trends and sector news

## Professional Trading Skills System

Located in `skills/` directory, this is a modular trading assistance system that activates only in this project:

### Skills Architecture

```
skills/
├── main.skill              # Main controller - coordinates all subsystems
├── market-monitor.skill    # Market environment monitoring
├── stock-analyzer.skill    # Individual stock analysis
├── trading-advisor.skill   # Trading decision advice
├── risk-manager.skill      # Risk control management
└── daily-review.skill      # Daily/weekly/monthly review
```

### Usage Workflow

**Pre-market (8:30-9:25)**:
```
User: "早上好，帮我分析今天市场"
→ Activates: market-monitor.skill
→ Output: Market environment score, overseas markets, sector analysis
```

**Intraday (9:30-15:00)**:
```
User: "XX股票现在XX元，能买吗？"
→ Activates: stock-analyzer + trading-advisor + risk-manager
→ Output: Technical analysis, trading recommendation, risk control
```

**After-market (15:00-17:00)**:
```
User: "收盘了，帮我总结"
→ Activates: daily-review.skill
→ Output: Daily review, tomorrow's plan, lessons learned
```

### Key Principles

1. **Trading Iron Rules**:
   - No short-term trading (hold ≥1 month)
   - Single stock position ≤20%
   - No chasing highs
   - Mandatory stop-loss at 10%
   - No averaging down on losses

2. **Scoring System**:
   - Technical: 40% (MA, MACD, RSI, KDJ, BOLL, Volume, Patterns)
   - Risk: 30% (stop-loss, risk-reward ratio)
   - Market Environment: 20% (index, sector, sentiment)
   - Fundamental: 10% (business, financials, valuation)

3. **Three-Layer Risk Control**:
   - Pre-trade: Position limits, mandatory stop-loss
   - In-trade: Real-time monitoring, trailing stops
   - Post-trade: Review every trade, optimize rules

### Important Notes

1. **Skills are project-specific**: Only activate in stockScience project sessions
2. **User confirmation required**: All trading decisions need user approval
3. **Risk disclaimer**: Final decision authority and risk responsibility belong to the user
4. **Continuous improvement**: Weekly and monthly system optimization built-in
