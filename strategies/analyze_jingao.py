"""
分析金风科技实时数据
"""
import sys
import os
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.diggold_data import DiggoldDataSource
from gm.api import set_token, current, history
from datetime import datetime
import pandas as pd
import numpy as np
import talib

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 初始化
set_token(DiggoldDataSource.TOKEN)
print("="*80)
print("金风科技 (002202) 实时分析")
print("="*80)
print(f"⏰ 分析时间: 2026-02-09 {datetime.now().strftime('%H:%M:%S')}\n")

# 金风科技代码: 002202，转换为掘金格式
symbol = "SZSE.002202"

print(f"📡 获取金风科技实时价格: {symbol}")
try:
    tick_data = current(symbols=[symbol])
    if tick_data and len(tick_data) > 0:
        latest = tick_data[0]
        if isinstance(latest, dict):
            price = latest.get('price', latest.get('last_price', 0))
            print(f"\n{'='*60}")
            print(f"📊 金风科技实时行情")
            print(f"{'='*60}")
            print(f"股票代码: {symbol}")
            print(f"最新价格: {price:.2f} 元")
            print(f"更新时间: {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'='*60}\n")
except Exception as e:
    print(f"获取实时价格失败: {e}")

# 获取历史数据
print(f"📡 获取历史数据...")
# 使用当前日期2026年2月9日
end_date = '2026-02-09'
start_date = '2025-12-11'  # 近60天数据

try:
    df = history(
        symbol=symbol,
        frequency='1d',
        start_time=start_date,
        end_time=end_date,
        adjust=1,
        df=True
    )

    if df is not None and not df.empty:
        # 处理日期
        if 'eob' in df.columns:
            df['date'] = pd.to_datetime(df['eob'])
            df = df.drop(columns=['eob'])
        if 'date' in df.columns:
            df.set_index('date', inplace=True)

        print(f"📊 获取到 {len(df)} 条数据\n")

        # 计算指标
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)

        df['ma5'] = talib.SMA(close, timeperiod=5)
        df['ma10'] = talib.SMA(close, timeperiod=10)
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

        # 最新数据
        latest = df.iloc[-1]

        print(f"{'='*80}")
        print(f"📊 金风科技技术分析")
        print(f"{'='*80}")
        print(f"📅 数据日期: {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"📈 收盘价: {latest['close']:.2f} 元\n")

        print(f"{'='*80}")
        print(f"📈 均线系统")
        print(f"{'='*80}")
        print(f"MA5  : {latest['ma5']:>8.2f} 元  {'↑' if latest['close'] > latest['ma5'] else '↓'}")
        print(f"MA10 : {latest['ma10']:>8.2f} 元  {'↑' if latest['close'] > latest['ma10'] else '↓'}")
        print(f"MA20 : {latest['ma20']:>8.2f} 元  {'↑' if latest['close'] > latest['ma20'] else '↓'}")

        if latest['ma5'] > latest['ma10'] > latest['ma20']:
            print(f"\n均线趋势: 🟢 多头排列")
        elif latest['ma5'] < latest['ma10'] < latest['ma20']:
            print(f"\n均线趋势: 🔴 空头排列")
        else:
            print(f"\n均线趋势: 🟡 均线纠缠")

        print(f"\n{'='*80}")
        print(f"📊 MACD")
        print(f"{'='*80}")
        print(f"MACD: {latest['macd_hist']:.4f}  {'🟢金叉' if latest['macd'] > latest['macd_signal'] else '🔴死叉'}")

        print(f"\n{'='*80}")
        print(f"📉 RSI")
        print(f"{'='*80}")
        print(f"RSI(14): {latest['rsi']:.2f}")
        if latest['rsi'] > 70:
            print(f"状态: 🔴 超买")
        elif latest['rsi'] < 30:
            print(f"状态: 🟢 超卖")
        else:
            print(f"状态: 🟡 中性")

        print(f"\n{'='*80}")
        print(f"📊 布林带")
        print(f"{'='*80}")
        print(f"上轨: {latest['boll_upper']:.2f} 元")
        print(f"中轨: {latest['boll_mid']:.2f} 元")
        print(f"下轨: {latest['boll_lower']:.2f} 元")
        print(f"当前: {latest['close']:.2f} 元")

        print(f"\n{'='*80}")
        print(f"📊 近期表现")
        print(f"{'='*80}")
        for days in [3, 5, 10, 20]:
            if len(df) > days:
                change = (df['close'].iloc[-1] / df['close'].iloc[-days-1] - 1) * 100
                bar = "📈" + "█" * int(abs(change)/2) if change > 0 else "📉" + "▓" * int(abs(change)/2)
                print(f"近{days:2d}日: {change:>+6.2f}% {bar}")

except Exception as e:
    print(f"分析失败: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*80}")
print("✅ 分析完成")
print(f"{'='*80}\n")
