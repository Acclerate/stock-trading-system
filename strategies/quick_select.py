#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速选股分析 - 使用缓存数据
支持统一输出：TXT、CSV、SQLite
"""
import pickle
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_resilient import DataResilient
from utils.strategy_output import StrategyOutputManager, StrategyMetadata, StockData
from strategy_tracker.db.repository import get_repository

def calculate_indicators(df):
    """计算技术指标"""
    # MA
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()

    # MACD
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # BOLL
    df['boll_mid'] = df['close'].rolling(window=20).mean()
    df['boll_std'] = df['close'].rolling(window=20).std()
    df['boll_upper'] = df['boll_mid'] + 2 * df['boll_std']
    df['boll_lower'] = df['boll_mid'] - 2 * df['boll_std']

    # 成交量变化
    df['volume_pct_change'] = df['volume'].pct_change()

    return df

def analyze_stock(df):
    """分析单个股票"""
    if df is None or len(df) < 20:
        return None

    df = calculate_indicators(df)
    latest = df.iloc[-1]

    # 5个买入条件
    conditions = {
        '均线金叉': latest['ma5'] > latest['ma20'],
        'MACD金叉': latest['macd'] > latest['macd_signal'],
        'RSI超卖': latest['rsi'] < 30,
        'BOLL下轨': latest['close'] < latest['boll_lower'],
        '放量20%': latest['volume_pct_change'] > 0.2
    }

    satisfied = [k for k, v in conditions.items() if v]

    return {
        'satisfied_count': len(satisfied),
        'conditions': satisfied,
        'price': latest['close'],
        'rsi': latest['rsi'],
        'ma5': latest['ma5'],
        'ma20': latest['ma20'],
        'macd': latest['macd']
    }

def main():
    cache_dir = Path("cache/stock")

    # 获取股票名称映射
    stock_info = DataResilient.get_stock_info(use_cache=True)
    name_map = dict(zip(stock_info['code'], stock_info['name'])) if not stock_info.empty else {}

    print(f"{'='*70}")
    print(f"{'每日选股分析报告':^50}")
    print(f"{'时间: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^50}")
    print(f"{'='*70}\n")

    # 先收集所有缓存文件，按股票分组
    stock_files = {}  # {symbol: [(file, end_date), ...]}

    for cache_file in cache_dir.glob("*.pkl"):
        try:
            parts = cache_file.stem.split('_')
            if len(parts) >= 3:
                symbol = parts[0]
                start_date = parts[1]
                end_date = parts[2]

                if symbol not in stock_files:
                    stock_files[symbol] = []
                stock_files[symbol].append((cache_file, start_date, end_date))
        except Exception:
            continue

    results = []
    total_analyzed = 0

    for symbol, files in stock_files.items():
        total_analyzed += 1
        # 按结束日期排序，取最新的
        files.sort(key=lambda x: x[2], reverse=True)
        latest_file, start_date, end_date = files[0]

        try:
            with open(latest_file, 'rb') as f:
                df = pickle.load(f)

            analysis = analyze_stock(df)

            if analysis and analysis['satisfied_count'] >= 2:
                results.append({
                    'symbol': symbol,
                    'name': name_map.get(symbol, '未知'),
                    'start_date': start_date,
                    'end_date': end_date,
                    **analysis
                })
        except Exception:
            continue

    # 按满足条件数量排序
    results.sort(key=lambda x: x['satisfied_count'], reverse=True)

    if not results:
        print("【当前没有满足买入条件的股票】")
        print("\n筛选条件：5个条件中至少满足2个")
        print("  1. 均线金叉 (MA5 > MA20)")
        print("  2. MACD金叉 (MACD > Signal)")
        print("  3. RSI超卖 (RSI < 30)")
        print("  4. BOLL下轨 (收盘价 < 下轨)")
        print("  5. 放量20% (成交量增长 > 20%)")
        return

    print(f"【找到 {len(results)} 只满足条件的股票】\n")
    print(f"{'代码':<8}{'名称':<10}{'日期范围':<18}{'价格':<10}{'RSI':<8}{'满足条件数':<12}{'买入条件'}")
    print("-" * 100)

    for r in results:
        conditions_str = ' + '.join(r['conditions'])
        date_range = f"{r['start_date'][:4]}-{r['start_date'][4:6]}-{r['start_date'][6:]} ~ {r['end_date'][:4]}-{r['end_date'][4:6]}-{r['end_date'][6:]}"
        print(f"{r['symbol']:<8}"
              f"{r['name']:<10}"
              f"{date_range:<18}"
              f"{r['price']:>8.2f}  "
              f"{r['rsi']:>6.1f}  "
              f"{r['satisfied_count']}/5      "
              f"{conditions_str}")

    print("\n" + "=" * 70)
    print("【风险提示】")
    print("  1. 本分析基于技术指标，不构成投资建议")
    print("  2. 技术分析存在滞后性，请结合基本面分析")
    print("  3. 投资有风险，入市需谨慎")
    print("  4. 建议设置止损位（单笔亏损不超过10%）")
    print("=" * 70)

    # ========== 使用统一输出工具保存结果 ==========
    print("\n正在保存结果...")

    # 创建策略元数据
    metadata = StrategyMetadata(
        strategy_name="快速选股分析（基于缓存）",
        strategy_type="quick_select",
        screen_date=datetime.now(),
        generated_at=datetime.now(),
        scan_count=total_analyzed,
        match_count=len(results),
        strategy_params={
            'data_source': 'cache',
            'min_conditions': 2
        },
        filter_conditions="5个条件中至少满足2个",
        scan_scope="缓存中的所有股票"
    )

    # 创建输出管理器
    output_mgr = StrategyOutputManager(metadata)

    # 添加股票数据
    for r in results:
        conditions_str = ' + '.join(r['conditions'])

        stock = StockData(
            stock_code=r['symbol'],
            stock_name=r['name'],
            screen_price=r['price'],
            score=r['satisfied_count'],
            reason=conditions_str,
            extra_fields={
                'rsi': r['rsi'],
                'ma5': r['ma5'],
                'ma20': r['ma20'],
                'macd': r['macd'],
                'satisfied_count': r['satisfied_count'],
                'conditions': conditions_str
            }
        )
        output_mgr.add_stock(stock)

    # 自定义表格格式化函数
    def format_quick_select_table(stocks):
        rows = []
        if stocks:
            rows.append("=== 快速选股结果（按满足条件数量降序）===")
            rows.append(f"{'代码':<8}{'名称':<10}{'价格':<10}{'RSI':<8}{'MA5':<10}{'MA20':<10}{'满足条件数':<12}{'买入条件'}")
            rows.append("-" * 100)

            for s in stocks:
                extra = s.extra_fields
                rows.append(
                    f"{s.stock_code:<8}"
                    f"{s.stock_name:<10}"
                    f"{s.screen_price:>8.2f}  "
                    f"{extra.get('rsi', 0):>6.1f}  "
                    f"{extra.get('ma5', 0):>8.2f}  "
                    f"{extra.get('ma20', 0):>8.2f}  "
                    f"{extra.get('satisfied_count', 0)}/5      "
                    f"{s.reason}"
                )
        else:
            rows.append("=== 当前无符合条件的股票 ===")
        return rows

    # 同时输出所有格式
    try:
        repo = get_repository()
        results = output_mgr.output_all(repo=repo, table_formatter=format_quick_select_table)
        print(f"✓ TXT: {results['txt']}")
        print(f"✓ CSV: {results['csv']}")
        print(f"✓ 数据库记录ID: {results['screening_id']}")
    except Exception as e:
        # 如果数据库操作失败，至少输出文件
        print(f"注意: 数据库写入失败 ({e})，仅输出文件")
        results = output_mgr.output_all(table_formatter=format_quick_select_table)
        print(f"✓ TXT: {results['txt']}")
        print(f"✓ CSV: {results['csv']}")

if __name__ == "__main__":
    main()
