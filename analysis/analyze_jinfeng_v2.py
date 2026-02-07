# -*- coding: utf-8 -*-
"""
分析金风科技 (002202.SZ) - 手动计算技术指标（不依赖pandas_ta）
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_sources import MultiSourceDataFetcher

def calculate_ma(series, period):
    """计算均线"""
    return series.rolling(window=period).mean()

def calculate_ema(series, period):
    """计算指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(close, fast=12, slow=26, signal=9):
    """计算MACD"""
    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)
    macd = ema_fast - ema_slow
    macd_signal = calculate_ema(macd, signal)
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist

def calculate_rsi(close, period=14):
    """计算RSI"""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger(close, period=20, std_dev=2):
    """计算布林带"""
    sma = calculate_ma(close, period)
    std = close.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def analyze_stock(symbol):
    """分析单只股票"""
    print(f"\n{'='*60}")
    print(f"分析股票: 金风科技 ({symbol})")
    print(f"{'='*60}\n")

    # 获取数据
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    try:
        fetcher = MultiSourceDataFetcher()
        df = fetcher.fetch_stock_data(symbol, start_date, end_date, verbose=True)

        if df is None or df.empty:
            print(f"无法获取 {symbol} 的数据")
            return

        print(f"\n数据范围: {df.index.min().strftime('%Y-%m-%d')} 至 {df.index.max().strftime('%Y-%m-%d')}")
        print(f"数据量: {len(df)} 条\n")

        # 确保有足够的数据
        if len(df) < 60:
            print("数据不足，无法进行技术分析")
            return

        # ========== 计算技术指标 ==========

        # 1. MA均线
        df['ma5'] = calculate_ma(df['close'], 5)
        df['ma10'] = calculate_ma(df['close'], 10)
        df['ma20'] = calculate_ma(df['close'], 20)
        df['ma60'] = calculate_ma(df['close'], 60)

        # 2. MACD
        df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(df['close'])

        # 3. RSI
        df['rsi'] = calculate_rsi(df['close'])

        # 4. BOLL布林带
        df['boll_upper'], df['boll_middle'], df['boll_lower'] = calculate_bollinger(df['close'])

        # 5. 成交量均线
        df['volume_ma5'] = df['volume'].rolling(window=5).mean()
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()

        # 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        print(f"最新交易日: {latest.name.strftime('%Y-%m-%d')}")
        print(f"收盘价: {latest['close']:.2f} 元")
        print(f"涨跌幅: {((latest['close'] / prev['close'] - 1) * 100):+.2f}%")
        print(f"成交量: {latest['volume']:,.0f} 手\n")

        # ========== MA分析 ==========
        print("【MA均线分析】")
        print(f"  MA5:  {latest['ma5']:.2f}")
        print(f"  MA10: {latest['ma10']:.2f}")
        print(f"  MA20: {latest['ma20']:.2f}")
        print(f"  MA60: {latest['ma60']:.2f}")

        ma_signal = []
        if pd.notna(latest['ma5']) and pd.notna(latest['ma10']) and pd.notna(latest['ma20']):
            if latest['ma5'] > latest['ma10'] > latest['ma20']:
                ma_signal.append("多头排列")
            elif latest['ma5'] < latest['ma10'] < latest['ma20']:
                ma_signal.append("空头排列")

            # 金叉检测
            if pd.notna(prev['ma5']) and pd.notna(prev['ma10']):
                if prev['ma5'] <= prev['ma10'] and latest['ma5'] > latest['ma10']:
                    ma_signal.append("MA5/MA10金叉 ⭐")

            if pd.notna(prev['ma5']) and pd.notna(prev['ma20']):
                if prev['ma5'] <= prev['ma20'] and latest['ma5'] > latest['ma20']:
                    ma_signal.append("MA5/MA20金叉 ⭐")

            if pd.notna(prev['ma10']) and pd.notna(prev['ma20']):
                if prev['ma10'] <= prev['ma20'] and latest['ma10'] > latest['ma20']:
                    ma_signal.append("MA10/MA20金叉 ⭐")

        if pd.notna(latest['ma5']):
            if latest['close'] > latest['ma5']:
                ma_signal.append("股价站上MA5")
            elif latest['close'] < latest['ma5']:
                ma_signal.append("股价跌破MA5")

        if ma_signal:
            print(f"  信号: {', '.join(ma_signal)}")
        else:
            print(f"  信号: 无明显信号")
        print()

        # ========== MACD分析 ==========
        print("【MACD分析】")
        if pd.notna(latest['macd']):
            print(f"  DIF:  {latest['macd']:.4f}")
            print(f"  DEA:  {latest['macd_signal']:.4f}")
            print(f"  MACD: {latest['macd_hist']:.4f}")

            macd_signal = []
            if latest['macd_hist'] > 0:
                macd_signal.append("MACD柱为正")
            else:
                macd_signal.append("MACD柱为负")

            if pd.notna(prev['macd_hist']):
                if prev['macd_hist'] <= 0 and latest['macd_hist'] > 0:
                    macd_signal.append("MACD金叉 ⭐")
                elif prev['macd_hist'] >= 0 and latest['macd_hist'] < 0:
                    macd_signal.append("MACD死叉")

            if pd.notna(prev['macd']) and pd.notna(prev['macd_signal']):
                if prev['macd'] <= prev['macd_signal'] and latest['macd'] > latest['macd_signal']:
                    macd_signal.append("DIF上穿DEA")

            if macd_signal:
                print(f"  信号: {', '.join(macd_signal)}")
            else:
                print(f"  信号: 无明显信号")
        else:
            print("  数据不足")
        print()

        # ========== RSI分析 ==========
        print("【RSI分析】")
        if pd.notna(latest['rsi']):
            print(f"  RSI(14): {latest['rsi']:.2f}")

            rsi_signal = []
            if latest['rsi'] < 30:
                rsi_signal.append("超卖区域（<30）⭐ 可能反弹")
            elif latest['rsi'] > 70:
                rsi_signal.append("超买区域（>70）注意回调")
            elif 30 <= latest['rsi'] <= 50:
                rsi_signal.append("偏弱区域（30-50）")
            elif 50 < latest['rsi'] <= 70:
                rsi_signal.append("偏强区域（50-70）")

            if rsi_signal:
                print(f"  信号: {', '.join(rsi_signal)}")
        else:
            print("  数据不足")
        print()

        # ========== BOLL分析 ==========
        print("【布林带分析】")
        if pd.notna(latest['boll_upper']):
            print(f"  上轨: {latest['boll_upper']:.2f}")
            print(f"  中轨: {latest['boll_middle']:.2f}")
            print(f"  下轨: {latest['boll_lower']:.2f}")
            print(f"  当前价: {latest['close']:.2f}")

            boll_width = ((latest['boll_upper'] - latest['boll_lower']) / latest['boll_middle'] * 100)
            print(f"  通道宽度: {boll_width:.2f}%")

            boll_signal = []
            if latest['close'] > latest['boll_upper']:
                boll_signal.append("突破上轨（强势）")
            elif latest['close'] < latest['boll_lower']:
                boll_signal.append("跌破下轨（弱势）⭐ 超卖")
            elif latest['boll_lower'] <= latest['close'] <= latest['boll_upper']:
                boll_signal.append("在通道内运行")

            if boll_width < 5:
                boll_signal.append("通道收窄，可能变盘")

            if boll_signal:
                print(f"  信号: {', '.join(boll_signal)}")
        else:
            print("  数据不足")
        print()

        # ========== 成交量分析 ==========
        print("【成交量分析】")
        if pd.notna(latest['volume_ma5']):
            print(f"  成交量: {latest['volume']:,.0f}")
            print(f"  5日均量: {latest['volume_ma5']:,.0f}")
            print(f"  20日均量: {latest['volume_ma20']:,.0f}")

            volume_signal = []
            volume_ratio = latest['volume'] / latest['volume_ma5'] if latest['volume_ma5'] > 0 else 0
            print(f"  量比: {volume_ratio:.2f}")

            if latest['volume'] > latest['volume_ma5'] * 1.5:
                volume_signal.append("放量（>5日均量1.5倍）⭐")
            elif latest['volume'] < latest['volume_ma5'] * 0.7:
                volume_signal.append("缩量（<5日均量0.7倍）")
            else:
                volume_signal.append("量能正常")

            if pd.notna(latest['volume_ma20']) and latest['volume'] > latest['volume_ma20']:
                volume_signal.append("量能高于20日均量")

            if volume_signal:
                print(f"  信号: {', '.join(volume_signal)}")
        else:
            print("  数据不足")
        print()

        # ========== 综合研判 ==========
        print("="*60)
        print("【综合研判】")

        buy_signals = []
        sell_signals = []

        # 收集所有信号
        if "MA5/MA10金叉" in str(ma_signal) or "MA10/MA20金叉" in str(ma_signal):
            buy_signals.append("均线金叉")
        if "多头排列" in str(ma_signal):
            buy_signals.append("均线多头排列")
        if "空头排列" in str(ma_signal):
            sell_signals.append("均线空头排列")

        if "MACD金叉" in str(macd_signal):
            buy_signals.append("MACD金叉")
        if "MACD死叉" in str(macd_signal):
            sell_signals.append("MACD死叉")

        if "超卖区域" in str(rsi_signal):
            buy_signals.append("RSI超卖")
        if "超买区域" in str(rsi_signal):
            sell_signals.append("RSI超买")

        if "跌破下轨" in str(boll_signal):
            buy_signals.append("布林带超卖")
        if "突破上轨" in str(boll_signal):
            sell_signals.append("布林带超买")

        if "放量" in str(volume_signal) and ("金叉" in str(ma_signal) or "MACD金叉" in str(macd_signal)):
            buy_signals.append("放量配合金叉")

        # 输出结论
        if buy_signals:
            print(f"\n  [OK] 买入信号: {', '.join(set(buy_signals))}")
        if sell_signals:
            print(f"  [!] 卖出/观望信号: {', '.join(set(sell_signals))}")

        # 综合评级
        buy_score = len(set(buy_signals))
        sell_score = len(set(sell_signals))

        print(f"\n{'='*60}")
        print(f"【综合评级】")
        if buy_score >= 3 and buy_score > sell_score:
            print(f"  评级: ★★★★☆ 强势买入")
            print(f"  建议: 多个买入信号共振，建议关注")
        elif buy_score >= 2 and buy_score > sell_score:
            print(f"  评级: ★★★☆☆ 谨慎买入")
            print(f"  建议: 有买入信号，可考虑分批建仓")
        elif sell_score >= 3 and sell_score > buy_score:
            print(f"  评级: ★☆☆☆☆ 建议回避")
            print(f"  建议: 多个卖出信号，建议观望或减仓")
        elif sell_score >= 2 and sell_score > buy_score:
            print(f"  评级: ★★☆☆☆ 观望")
            print(f"  建议: 有卖出信号，建议谨慎")
        else:
            print(f"  评级: ★★☆☆☆ 震荡整理")
            print(f"  建议: 信号不明确，建议继续观察")

        # 显示最近5天数据
        print(f"\n{'='*60}")
        print(f"【最近5日数据】")
        display_cols = ['open', 'close', 'high', 'low', 'volume', 'ma5', 'ma10', 'ma20', 'macd_hist', 'rsi']
        recent = df[display_cols].tail(5)
        for idx, row in recent.iterrows():
            print(f"\n{idx.strftime('%Y-%m-%d')}:")
            print(f"  开:{row['open']:.2f} 高:{row['high']:.2f} 低:{row['low']:.2f} 收:{row['close']:.2f}")
            print(f"  MA5:{row['ma5']:.2f} MA10:{row['ma10']:.2f} MA20:{row['ma20']:.2f}")
            print(f"  MACD:{row['macd_hist']:.4f} RSI:{row['rsi']:.2f}")

        print(f"\n{'='*60}\n")

        # 打印数据源状态
        print("\n数据源状态统计:")
        fetcher.print_status()

    except Exception as e:
        print(f"分析失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 金风科技
    analyze_stock("002202.SZ")
