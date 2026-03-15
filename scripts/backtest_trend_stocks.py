#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
趋势股策略回测 - 计算收益率
回测逻辑：
1. 对每只股票，在历史数据中每天判断是否满足趋势条件
2. 满足条件时买入，持有一段时间后卖出
3. 计算所有交易的收益率统计
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Windows encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from data.data_resilient import DataResilient
from data.cache_manager import CacheManager


def normalize_symbol(symbol):
    """标准化股票代码"""
    if '.' in str(symbol):
        return symbol.split('.')[-1]
    return symbol


def get_all_a_stocks():
    """获取全A股列表（剔除创业板、科创板、ST股）"""
    cache_key = 'all_a_stocks_filtered'
    cached = CacheManager.load_macro_cache(cache_key)
    if cached is not None:
        return [normalize_symbol(s) for s in cached]

    from gm.api import get_instruments

    df = get_instruments(sec_types=1, df=True)
    if df is None or df.empty:
        return []

    df['code'] = df['symbol'].apply(lambda x: x.split('.')[-1] if '.' in str(x) else str(x))

    if 'sec_name' in df.columns:
        df['name'] = df['sec_name']
    else:
        df['name'] = ''

    # 过滤
    df = df[~df['code'].str.startswith('300')]
    df = df[~df['code'].str.startswith('688')]
    df = df[~df['code'].str.startswith('301')]
    df = df[~df['name'].str.contains('ST|退|暂停', na=False)]
    valid_prefixes = ['600', '601', '603', '605', '000', '001', '002']
    df = df[df['code'].str[:3].isin(valid_prefixes)]

    codes = df['code'].tolist()
    code_name_dict = dict(zip(df['code'], df['name']))
    CacheManager.save_macro_cache('stock_name_dict', code_name_dict)
    CacheManager.save_macro_cache(cache_key, codes)

    print(f"✅ 获取到 {len(codes)} 只股票")
    return codes


def calculate_indicators(df):
    """计算趋势指标"""
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    df['ma30'] = df['close'].rolling(window=30).mean()
    df['vol_ma5'] = df['volume'].rolling(window=5).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma5']
    return df


def calculate_trend_score(row, prev_row):
    """
    计算趋势强度评分 (0-100)
    评分越高，趋势越强
    """
    ma5, ma10, ma30 = row['ma5'], row['ma10'], row['ma30']
    price = row['close']

    if pd.isna(ma5) or pd.isna(ma10) or pd.isna(ma30):
        return 0

    score = 0

    # 1. 多头排列强度 (30分)
    ma_spread = (ma5 - ma30) / ma30 * 100  # MA5与MA30的距离百分比
    score += min(max(ma_spread * 5, 0), 30)

    # 2. 股价位置 (25分)
    ma5_gap = (price - ma5) / ma5 * 100  # 股价在MA5上方的距离
    if ma5_gap > 0:
        score += min(max(ma5_gap * 3, 0), 25)

    # 3. 均线向上 (20分)
    if pd.notna(prev_row['ma5']) and pd.notna(prev_row['ma10']) and pd.notna(prev_row['ma30']):
        ma5_rising = row['ma5'] > prev_row['ma5']
        ma10_rising = row['ma10'] > prev_row['ma10']
        ma30_rising = row['ma30'] > prev_row['ma30']
        rising_count = sum([ma5_rising, ma10_rising, ma30_rising])
        score += rising_count * 6.67

    # 4. 成交量确认 (25分)
    vol_ratio = row.get('vol_ratio', 1)
    if vol_ratio >= 1.5:
        score += 25  # 明显放量
    elif vol_ratio >= 1.2:
        score += 18  # 轻度放量
    elif vol_ratio >= 1.0:
        score += 10  # 正常
    else:
        score += 5   # 缩量

    return score


def is_trend_signal(row, prev_row, min_score=50):
    """
    判断是否为趋势信号（优化版）

    条件：
    1. MA5 > MA10 > MA30（多头排列）
    2. 趋势强度评分 >= min_score（默认50分）
    3. 股价在MA5上方或非常接近
    """
    ma5, ma10, ma30 = row['ma5'], row['ma10'], row['ma30']

    if pd.isna(ma5) or pd.isna(ma10) or pd.isna(ma30):
        return False

    # 多头排列
    if not (ma5 > ma10 > ma30):
        return False

    # 股价在MA5附近（上方或下方1%以内）
    price = row['close']
    ma5_gap = (price - ma5) / ma5
    if ma5_gap < -0.01:  # 股价低于MA5超过1%，不买入
        return False

    # 计算趋势评分
    score = calculate_trend_score(row, prev_row)

    return score >= min_score


def backtest_single_stock(symbol, name_map, start_date, end_date, hold_days=10,
                          min_score=50, cooldown_days=5):
    """
    对单只股票进行回测（优化版）

    参数：
    - min_score: 最低趋势评分要求（默认50分）
    - cooldown_days: 卖出后冷却期（默认5天）
    """
    stock_name = name_map.get(symbol, "")

    try:
        df = DataResilient.fetch_stock_data(symbol, start_date, end_date, use_cache=True)
        if df is None or df.empty or len(df) < 35:
            return []

        df = calculate_indicators(df)

        trades = []
        position = None  # (entry_date, entry_price)
        last_exit_date = None  # 最后一次卖出日期

        for i in range(31, len(df)):  # 从第31天开始，确保指标有效
            current = df.iloc[i]
            prev = df.iloc[i - 1]
            current_date = df.index[i]

            # 如果没有持仓，检查是否买入
            if position is None:
                # 检查冷却期
                if last_exit_date is not None:
                    days_since_exit = (current_date - last_exit_date).days
                    if days_since_exit < cooldown_days:
                        continue  # 冷却期内，不买入

                # 检查趋势信号
                if is_trend_signal(current, prev, min_score):
                    entry_date = current_date
                    entry_price = current['close']
                    position = (entry_date, entry_price)
            else:
                # 已有持仓，检查是否卖出
                days_held = (current_date - position[0]).days

                # 卖出条件：
                # 1. 持有达到目标天数
                # 2. 止损：跌幅超过5%
                # 3. 止盈：涨幅超过15%
                # 4. 趋势破坏：MA5 <= MA10
                entry_price = position[1]
                current_price = current['close']
                return_pct = (current_price - entry_price) / entry_price * 100

                should_sell = False
                sell_reason = ""

                if days_held >= hold_days:
                    should_sell = True
                    sell_reason = f"持有{hold_days}天"
                elif return_pct <= -5:
                    should_sell = True
                    sell_reason = f"止损({return_pct:.1f}%)"
                elif return_pct >= 15:
                    should_sell = True
                    sell_reason = f"止盈({return_pct:.1f}%)"
                elif current['ma5'] <= current['ma10']:
                    should_sell = True
                    sell_reason = "趋势破坏"

                if should_sell:
                    exit_date = current_date
                    exit_price = current['close']
                    trades.append({
                        'symbol': symbol,
                        'name': stock_name,
                        'entry_date': position[0],
                        'entry_price': position[1],
                        'exit_date': exit_date,
                        'exit_price': exit_price,
                        'hold_days': days_held,
                        'return_pct': return_pct,
                        'sell_reason': sell_reason
                    })
                    position = None
                    last_exit_date = exit_date

        return trades

    except Exception as e:
        return []


def analyze_results(trades):
    """分析回测结果"""
    if not trades:
        return None

    df = pd.DataFrame(trades)

    # 基本统计
    total_trades = len(df)
    winning_trades = len(df[df['return_pct'] > 0])
    losing_trades = len(df[df['return_pct'] < 0])

    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

    # 收益统计
    avg_return = df['return_pct'].mean()
    median_return = df['return_pct'].median()
    max_return = df['return_pct'].max()
    min_return = df['return_pct'].min()

    # 盈亏统计
    avg_win = df[df['return_pct'] > 0]['return_pct'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['return_pct'] < 0]['return_pct'].mean() if losing_trades > 0 else 0

    # 持有天数统计
    avg_hold_days = df['hold_days'].mean()

    # 卖出原因统计
    sell_reasons = df['sell_reason'].value_counts()

    # 累计收益（假设每次投入相同资金）
    cumulative_return = (1 + df['return_pct'] / 100).prod() - 1

    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'avg_return': avg_return,
        'median_return': median_return,
        'max_return': max_return,
        'min_return': min_return,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'avg_hold_days': avg_hold_days,
        'cumulative_return': cumulative_return,
        'sell_reasons': sell_reasons,
        'trades_df': df
    }


def main():
    """主程序"""
    import argparse

    parser = argparse.ArgumentParser(description='趋势股策略回测（优化版）')
    parser.add_argument('-d', '--days', type=int, default=180,
                        help='回测数据天数 (默认: 180)')
    parser.add_argument('-H', '--hold-days', type=int, default=10,
                        help='目标持有天数 (默认: 10)')
    parser.add_argument('--top-n', type=int, default=None,
                        help='只回测前N只股票 (用于快速测试)')
    parser.add_argument('--min-score', type=int, default=50,
                        help='最低趋势评分要求 (默认: 50分)')
    parser.add_argument('--cooldown', type=int, default=5,
                        help='卖出后冷却期天数 (默认: 5天)')

    args = parser.parse_args()

    CacheManager.initialize()

    print("=" * 70)
    print("趋势股策略回测系统（优化版）")
    print("=" * 70)
    print(f"回测周期: {args.days}天")
    print(f"目标持有: {args.hold_days}天")
    print(f"止损: -5% | 止盈: +15%")
    print(f"最低趋势评分: {args.min_score}分")
    print(f"卖出后冷却期: {args.cooldown}天")
    print("=" * 70)
    print()

    # 获取股票列表
    symbols = get_all_a_stocks()
    if not symbols:
        print("无法获取股票列表")
        return

    name_map = CacheManager.load_macro_cache('stock_name_dict') or {}

    # 日期设置
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")

    print(f"\n开始回测，数据范围: {start_date} ~ {end_date}")
    print()

    # 限制股票数量（用于快速测试）
    if args.top_n:
        symbols = symbols[:args.top_n]
        print(f"⚠️ 测试模式：仅回测前 {args.top_n} 只股票\n")

    # 回测
    all_trades = []
    total = len(symbols)

    for idx, symbol in enumerate(symbols, 1):
        if idx % 10 == 0 or idx == total:
            print(f"进度: {idx}/{total} ({idx/total*100:.1f}%) - 交易数: {len(all_trades)}")

        trades = backtest_single_stock(
            symbol, name_map, start_date, end_date,
            args.hold_days, args.min_score, args.cooldown
        )
        all_trades.extend(trades)

    print()
    print("=" * 70)
    print("回测完成！")
    print("=" * 70)

    # 分析结果
    result = analyze_results(all_trades)

    if result is None:
        print("\n⚠️ 未产生任何交易信号")
        return

    print(f"\n📊 回测统计:")
    print(f"  总交易次数: {result['total_trades']}")
    print(f"  盈利次数:   {result['winning_trades']}")
    print(f"  亏损次数:   {result['losing_trades']}")
    print(f"  胜率:       {result['win_rate']:.2f}%")
    print()
    print(f"💰 收益统计:")
    print(f"  平均收益:   {result['avg_return']:.2f}%")
    print(f"  中位数收益: {result['median_return']:.2f}%")
    print(f"  最大收益:   {result['max_return']:.2f}%")
    print(f"  最大亏损:   {result['min_return']:.2f}%")
    print(f"  平均盈利:   {result['avg_win']:.2f}%")
    print(f"  平均亏损:   {result['avg_loss']:.2f}%")
    print(f"  盈亏比:     {abs(result['avg_win'] / result['avg_loss']) if result['avg_loss'] != 0 else 0:.2f}")
    print()
    print(f"⏱️ 持有统计:")
    print(f"  平均持有天数: {result['avg_hold_days']:.1f}天")
    print()
    print(f"📈 累计收益: {result['cumulative_return']*100:.2f}% (假设等额投资每笔交易)")
    print()
    print(f"🔍 卖出原因分布:")
    for reason, count in result['sell_reasons'].items():
        print(f"  {reason}: {count}次 ({count/result['total_trades']*100:.1f}%)")

    print("\n" + "=" * 70)
    print("🏆 最佳交易 Top 10")
    print("=" * 70)

    top_trades = result['trades_df'].nlargest(10, 'return_pct')
    for idx, (_, row) in enumerate(top_trades.iterrows(), 1):
        print(f"{idx:2d}. {row['name']:8s} {row['symbol']:6s} | "
              f"{row['entry_date'].strftime('%Y-%m-%d')} -> {row['exit_date'].strftime('%Y-%m-%d')} | "
              f"持有{row['hold_days']:2d}天 | 收益: {row['return_pct']:6.2f}% ({row['sell_reason']})")

    print("\n" + "=" * 70)
    print("💔 最差交易 Top 10")
    print("=" * 70)

    worst_trades = result['trades_df'].nsmallest(10, 'return_pct')
    for idx, (_, row) in enumerate(worst_trades.iterrows(), 1):
        print(f"{idx:2d}. {row['name']:8s} {row['symbol']:6s} | "
              f"{row['entry_date'].strftime('%Y-%m-%d')} -> {row['exit_date'].strftime('%Y-%m-%d')} | "
              f"持有{row['hold_days']:2d}天 | 收益: {row['return_pct']:6.2f}% ({row['sell_reason']})")

    # 保存详细交易记录
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = output_dir / f"trend_backtest_{timestamp}.csv"
    result['trades_df'].to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 详细交易记录已保存: {csv_file}")


if __name__ == "__main__":
    main()
