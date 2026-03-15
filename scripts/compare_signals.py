#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信号对比分析工具
对比 stockPre 和 main 两种策略的买卖点差异
"""
import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Windows encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.data_resilient import DataResilient
from data.cache_manager import CacheManager

try:
    import talib
except ImportError:
    talib = None


# ==================== stockPre 策略逻辑 ====================
def stockPre_calculate_indicators(df):
    """stockPy: 使用 TA-Lib 计算指标"""
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values

    df['ma5'] = talib.SMA(close, timeperiod=5)
    df['ma20'] = talib.SMA(close, timeperiod=20)
    macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = macd_hist
    df['rsi'] = talib.RSI(close, timeperiod=14)
    boll_upper, boll_mid, boll_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    df['boll_upper'] = boll_upper
    df['boll_mid'] = boll_mid
    df['boll_lower'] = boll_lower
    df['volume_ma3'] = df['volume'].rolling(window=3).mean()
    df['volume_pct_change'] = (df['volume'] / df['volume_ma3'].shift(1)) - 1

    return df


def stockPre_generate_signals(df):
    """stockPre: 5个条件，满足2个即可买入"""
    buy_conditions = [
        (df['ma5'] > df['ma20']),           # 均线金叉
        (df['macd'] > df['macd_signal']),    # MACD金叉
        (df['rsi'] < 30),                    # RSI超卖
        (df['close'] < df['boll_lower']),    # BOLL下轨
        (df['volume_pct_change'] > 0.2)     # 放量20%
    ]
    satisfied_counts = sum(cond.astype(int) for cond in buy_conditions)
    buy_signal = satisfied_counts >= 2

    # 卖出：任一条件触发
    sell_signal = (
        (df['macd'] < df['macd_signal']) |  # MACD死叉
        (df['rsi'] > 70) |                  # RSI超买
        (df['close'] > df['boll_upper'])     # BOLL上轨
    )

    signals = pd.DataFrame(index=df.index)
    signals['buy'] = buy_signal
    signals['sell'] = sell_signal
    signals['buy_score'] = satisfied_counts
    return signals


# ==================== main 策略逻辑 ====================
def crossed_above(left, right):
    """金叉事件检测"""
    return (left > right) & (left.shift(1) <= right.shift(1))


def crossed_below(left, right):
    """死叉事件检测"""
    return (left < right) & (left.shift(1) >= right.shift(1))


def main_calculate_indicators(df):
    """main: 计算指标（与stockPre相同）"""
    close = df['close'].astype(float)
    volume = df['volume'].astype(float)

    df['ma5'] = close.rolling(window=5).mean()
    df['ma20'] = close.rolling(window=20).mean()

    # MACD
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = macd_hist

    df['volume_ma3'] = volume.rolling(window=3).mean()
    df['volume_pct_change'] = (volume / df['volume_ma3'].shift(1)) - 1

    return df


def main_generate_signals(df, buy_lookback_days=3, sell_confirm_days=2):
    """main: 严格买入条件，确认卖出条件"""
    ma_up = df['ma5'] > df['ma20']
    macd_up = df['macd'] > df['macd_signal']
    volume_up = df['volume_pct_change'] > 0.2
    price_above_ma20 = df['close'] > df['ma20']
    macd_hist_up = df['macd_hist'] > 0

    # 金叉事件
    ma_cross_up = crossed_above(df['ma5'], df['ma20'])
    macd_cross_up = crossed_above(df['macd'], df['macd_signal'])
    ma_cross_down = crossed_below(df['ma5'], df['ma20'])
    macd_cross_down = crossed_below(df['macd'], df['macd_signal'])

    # 近期有金叉（事件）
    recent_ma_cross = ma_cross_up.rolling(window=buy_lookback_days, min_periods=1).max().astype(bool)
    recent_macd_cross = macd_cross_up.rolling(window=buy_lookback_days, min_periods=1).max().astype(bool)

    # 买入：全部条件同时满足
    buy_signal = (
        ma_up &                    # 均线多头排列
        macd_up &                  # MACD多头
        volume_up &                # 放量
        price_above_ma20 &         # 股价在MA20上方
        macd_hist_up &             # MACD柱为正
        recent_ma_cross &          # 近期有均线金叉
        recent_macd_cross          # 近期有MACD金叉
    )

    # 卖出：多级确认
    weak_bearish = (~ma_up) | (~macd_up)
    bearish_confirm = weak_bearish.rolling(window=sell_confirm_days, min_periods=sell_confirm_days).sum() >= sell_confirm_days
    strong_bearish = (~ma_up) & (~macd_up)
    hard_exit = ma_cross_down & macd_cross_down

    sell_signal = strong_bearish | bearish_confirm | hard_exit

    signals = pd.DataFrame(index=df.index)
    signals['buy'] = buy_signal
    signals['sell'] = sell_signal
    signals['ma_cross_up'] = ma_cross_up
    signals['macd_cross_up'] = macd_cross_up
    signals['recent_ma_cross'] = recent_ma_cross
    signals['recent_macd_cross'] = recent_macd_cross
    signals['strong_bearish'] = strong_bearish
    signals['bearish_confirm'] = bearish_confirm
    signals['hard_exit'] = hard_exit

    # 买入条件满足数（用于分析）
    buy_condition_count = (
        ma_up.astype(int) +
        macd_up.astype(int) +
        volume_up.astype(int) +
        price_above_ma20.astype(int) +
        macd_hist_up.astype(int) +
        recent_ma_cross.astype(int) +
        recent_macd_cross.astype(int)
    )
    signals['buy_score'] = buy_condition_count

    return signals


# ==================== 对比分析 ====================
def compare_signals(symbol, start_date, end_date):
    """对比两个策略的信号差异"""
    # 获取数据
    df = DataResilient.fetch_stock_data(symbol, start_date, end_date, use_cache=True)
    if df is None or len(df) < 35:
        return None

    # 计算两套指标
    df1 = stockPre_calculate_indicators(df.copy())
    df2 = main_calculate_indicators(df.copy())

    # 生成两套信号
    signals1 = stockPre_generate_signals(df1)
    signals2 = main_generate_signals(df2)

    # 合并对比
    comparison = pd.DataFrame(index=df.index)
    comparison['close'] = df['close']
    comparison['ma5'] = df1['ma5']
    comparison['ma20'] = df1['ma20']

    # stockPre 信号
    comparison['stockPre_buy'] = signals1['buy']
    comparison['stockPre_sell'] = signals1['sell']
    comparison['stockPre_score'] = signals1['buy_score']

    # main 信号
    comparison['main_buy'] = signals2['buy']
    comparison['main_sell'] = signals2['sell']
    comparison['main_score'] = signals2['buy_score']
    comparison['ma_cross_up'] = signals2['ma_cross_up']
    comparison['macd_cross_up'] = signals2['macd_cross_up']

    # 信号差异
    comparison['only_stockPre_buy'] = comparison['stockPre_buy'] & ~comparison['main_buy']
    comparison['only_main_buy'] = comparison['main_buy'] & ~comparison['stockPre_buy']
    comparison['both_buy'] = comparison['stockPre_buy'] & comparison['main_buy']

    return comparison


def analyze_symbol(symbol, name_map, start_date, end_date):
    """分析单只股票的信号差异"""
    stock_name = name_map.get(symbol, symbol)

    try:
        comp = compare_signals(symbol, start_date, end_date)
        if comp is None:
            return None

        # 只看最近30天
        recent = comp.iloc[-30:]

        stats = {
            'symbol': symbol,
            'name': stock_name,
            'latest_price': float(recent['close'].iloc[-1]),
            'latest_date': recent.index[-1].strftime('%Y-%m-%d'),
            'stockPre_buy_days': int(recent['stockPre_buy'].sum()),
            'main_buy_days': int(recent['main_buy'].sum()),
            'both_buy_days': int(recent['both_buy'].sum()),
            'only_stockPre_days': int(recent['only_stockPre_buy'].sum()),
            'only_main_days': int(recent['only_main_buy'].sum()),
            'latest_stockPre_signal': bool(recent['stockPre_buy'].iloc[-1]),
            'latest_main_signal': bool(recent['main_buy'].iloc[-1]),
        }

        # 记录差异日期
        diff_dates = recent[recent['only_stockPre_buy'] | recent['only_main_buy']].index
        stats['signal_diff_dates'] = [d.strftime('%Y-%m-%d') for d in diff_dates]

        return stats

    except Exception as e:
        return None


def main():
    """主程序"""
    import argparse

    parser = argparse.ArgumentParser(description='策略信号对比分析')
    parser.add_argument('-s', '--symbol', type=str, help='指定股票代码 (如: 600519)')
    parser.add_argument('-p', '--pool', type=str, default='zz500',
                        choices=['hs300', 'zz500', 'zz1000', 'zx50'],
                        help='股票池 (默认: zz500)')
    parser.add_argument('-d', '--days', type=int, default=90,
                        help='分析天数 (默认: 90)')
    parser.add_argument('--top-n', type=int, default=20,
                        help='显示前N只差异最大的股票 (默认: 20)')

    args = parser.parse_args()

    CacheManager.initialize()

    print("=" * 80)
    print("策略信号对比分析: stockPre vs main")
    print("=" * 80)
    print(f"分析周期: 最近{args.days}天")
    print("=" * 80)
    print()

    # 日期设置
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=args.days + 50)).strftime("%Y%m%d")

    # 获取股票列表
    from strategies.stockPre import STOCK_POOLS, get_stock_pool_symbols
    symbols = get_stock_pool_symbols(args.pool)
    if not symbols:
        print(f"无法获取股票池")
        return

    # 获取名称映射
    stock_code_name_df = DataResilient.get_stock_info(use_cache=True)
    code_name_dict = dict(zip(stock_code_name_df['code'], stock_code_name_df['name'])) if not stock_code_name_df.empty else {}

    # 如果指定了单只股票
    if args.symbol:
        stats = analyze_symbol(args.symbol, code_name_dict, start_date, end_date)
        if stats:
            print_single_analysis(stats)
            print_detailed_signals(args.symbol, start_date, end_date)
        return

    # 批量分析
    print(f"正在分析 {len(symbols)} 只股票...\n")

    all_stats = []
    for idx, symbol in enumerate(symbols, 1):
        base_symbol = symbol.split('.')[0]

        if idx % 50 == 0:
            print(f"进度: {idx}/{len(symbols)}")

        stats = analyze_symbol(base_symbol, code_name_dict, start_date, end_date)
        if stats and (stats['stockPre_buy_days'] > 0 or stats['main_buy_days'] > 0):
            all_stats.append(stats)

    print(f"\n✅ 分析完成，有效股票: {len(all_stats)} 只\n")

    # 显示汇总
    print_summary(all_stats)

    # 显示差异最大的股票
    print("\n" + "=" * 80)
    print(f"信号差异最大的 {args.top_n} 只股票")
    print("=" * 80)
    print_top_diff(all_stats, args.top_n)


def print_single_analysis(stats):
    """打印单只股票分析"""
    print(f"\n股票: {stats['name']} ({stats['symbol']})")
    print(f"最新价: {stats['latest_price']:.2f} | 日期: {stats['latest_date']}")
    print("-" * 60)
    print(f"{'指标':<25}{'stockPre策略':>15}{'main策略':>15}")
    print("-" * 60)
    print(f"{'买入信号天数':<25}{stats['stockPre_buy_days']:>15}{stats['main_buy_days']:>15}")
    print(f"{'两者都买入':<25}{stats['both_buy_days']:>15}{'-':>14}")
    print(f"{'仅stockPre买入':<25}{stats['only_stockPre_days']:>15}{'-':>14}")
    print(f"{'仅main买入':<25}{'-':>14}{stats['only_main_days']:>15}")
    print(f"{'最新买入信号'::<25}{'✓' if stats['latest_stockPre_signal'] else '✗':>15}{'✓' if stats['latest_main_signal'] else '✗':>15}")


def print_detailed_signals(symbol, start_date, end_date):
    """打印详细信号对比"""
    comp = compare_signals(symbol, start_date, end_date)
    if comp is None:
        return

    print("\n" + "=" * 80)
    print("最近信号对比详情")
    print("=" * 80)

    # 最近有差异的日期
    recent = comp.iloc[-15:]
    diff_days = recent[recent['only_stockPre_buy'] | recent['only_main_buy'] | recent['both_buy']]

    if diff_days.empty:
        print("最近15天无买入信号差异")
        return

    print(f"{'日期':<12}{'收盘':>8}{'stockPre':>10}{'main':>10}{'stockPre分':>12}{'main分':>10}{'差异'}")
    print("-" * 80)

    for date, row in diff_days.iterrows():
        date_str = date.strftime('%Y-%m-%d')
        stockPre = '✓买入' if row['stockPre_buy'] else ('✓卖出' if row['stockPre_sell'] else '')
        main_sig = '✓买入' if row['main_buy'] else ('✓卖出' if row['main_sell'] else '')
        diff = ''
        if row['only_stockPre_buy']:
            diff = '仅stockPre'
        elif row['only_main_buy']:
            diff = '仅main'
        elif row['both_buy']:
            diff = '一致买入'

        print(f"{date_str:<12}{row['close']:>8.2f}{stockPre:>10}{main_sig:>10}{row['stockPre_score']:>12}{row['main_score']:>10}{diff}")


def print_summary(all_stats):
    """打印汇总统计"""
    if not all_stats:
        return

    df = pd.DataFrame(all_stats)

    print("\n" + "=" * 80)
    print("汇总统计")
    print("=" * 80)

    total = len(all_stats)
    stockPre_latest = df['latest_stockPre_signal'].sum()
    main_latest = df['latest_main_signal'].sum()

    print(f"分析股票数: {total}")
    print(f"最新有stockPre买入信号: {stockPre_latest} 只 ({stockPre_latest/total*100:.1f}%)")
    print(f"最新有main买入信号: {main_latest} 只 ({main_latest/total*100:.1f}%)")
    print(f"两者都有: {df[df['latest_stockPre_signal'] & df['latest_main_signal']].shape[0]} 只")
    print()

    # stockPre 特点
    print("stockPre策略特点:")
    print(f"  - 平均买入天数/股: {df['stockPre_buy_days'].mean():.1f} 天")
    print(f"  - 买入最频繁股票: {df.loc[df['stockPre_buy_days'].idxmax(), 'name']} ({df['stockPre_buy_days'].max()} 天)")
    print()

    # main 特点
    print("main策略特点:")
    print(f"  - 平均买入天数/股: {df['main_buy_days'].mean():.1f} 天")
    print(f"  - 买入更严格，信号更少")
    print(f"  - 要求近期金叉事件 + 所有条件满足")


def print_top_diff(all_stats, top_n):
    """打印差异最大的股票"""
    if not all_stats:
        return

    df = pd.DataFrame(all_stats)

    # 计算差异分数：stockPre买入多但main买入少的
    df['diff_score'] = df['only_stockPre_days'] - df['only_main_days']

    print(f"\n{'序号':<6}{'名称':<16}{'代码':<10}{'stockPre':>10}{'main':>8}{'仅stockPre':>12}{'仅main':>10}{'差异分':>10}")
    print("-" * 90)

    # 按差异排序
    top_diff = df.nlargest(top_n, 'diff_score')

    for idx, (_, row) in enumerate(top_diff.iterrows(), 1):
        print(f"{idx:<6}{row['name'][:14]:<16}{row['symbol']:<10}"
              f"{row['stockPre_buy_days']:>10}{row['main_buy_days']:>8}"
              f"{row['only_stockPre_days']:>12}{row['only_main_days']:>10}{row['diff_score']:>10}")

    print("\n说明:")
    print("  - stockPre: 宽松策略 (满足2/5条件即可)")
    print("  - main: 严格策略 (需同时满足7个条件 + 金叉事件)")
    print("  - 差异分大 = stockPre买入多但main不买，可能存在假突破")


if __name__ == "__main__":
    main()
