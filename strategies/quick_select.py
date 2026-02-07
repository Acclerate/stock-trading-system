#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速选股分析 - 使用缓存数据
"""
import pickle
import pandas as pd
from pathlib import Path
from datetime import datetime

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

    print(f"{'='*70}")
    print(f"{'每日选股分析报告':^50}")
    print(f"{'时间: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^50}")
    print(f"{'='*70}\n")

    results = []

    for cache_file in cache_dir.glob("*.pkl"):
        try:
            # 从文件名提取股票代码
            symbol = cache_file.stem.split('_')[0]

            with open(cache_file, 'rb') as f:
                df = pickle.load(f)

            analysis = analyze_stock(df)

            if analysis and analysis['satisfied_count'] >= 2:
                results.append({
                    'symbol': symbol,
                    **analysis
                })
        except Exception as e:
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
    print(f"{'代码':<10}{'价格':<10}{'RSI':<8}{'满足条件数':<12}{'买入条件'}")
    print("-" * 70)

    for r in results:
        conditions_str = ' + '.join(r['conditions'])
        print(f"{r['symbol']:<10}"
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

if __name__ == "__main__":
    main()
