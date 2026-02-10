"""单只股票技术分析工具"""
import pandas as pd
import talib
import akshare as ak
from datetime import datetime, timedelta


def analyze_stock(symbol, name=""):
    """分析单只股票的技术指标"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    print(f"\n{'='*60}")
    print(f"股票分析: {name} ({symbol})")
    print(f"{'='*60}\n")

    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                               start_date=start_date.strftime("%Y%m%d"),
                               end_date=end_date.strftime("%Y%m%d"))
        df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume'
        }, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
    except Exception as e:
        print(f"❌ 获取数据失败: {e}")
        return

    # 计算指标
    close = df['close'].values
    df['ma5'] = talib.SMA(close, timeperiod=5)
    df['ma10'] = talib.SMA(close, timeperiod=10)
    df['ma20'] = talib.SMA(close, timeperiod=20)
    df['ma60'] = talib.SMA(close, timeperiod=60)

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
    latest_date = df.index[-1].strftime('%Y-%m-%d')

    print(f"📅 数据日期: {latest_date}")
    print(f"\n{'='*60}")
    print(f"📊 股价与均线")
    print(f"{'='*60}")
    print(f"最新收盘价: {latest['close']:.2f} 元")
    print(f"MA5  : {latest['ma5']:.2f} 元 {'↑' if latest['close'] > latest['ma5'] else '↓'}")
    print(f"MA10 : {latest['ma10']:.2f} 元 {'↑' if latest['close'] > latest['ma10'] else '↓'}")
    print(f"MA20 : {latest['ma20']:.2f} 元 {'↑' if latest['close'] > latest['ma20'] else '↓'}")
    print(f"MA60 : {latest['ma60']:.2f} 元 {'↑' if latest['close'] > latest['ma60'] else '↓'}")

    ma_signal = "中性"
    if latest['ma5'] < latest['ma10'] < latest['ma20'] < latest['ma60']:
        ma_signal = "🔴 空头排列（强烈看空）"
    elif latest['ma5'] > latest['ma10'] > latest['ma20']:
        ma_signal = "🟢 多头排列（看多）"
    print(f"\n均线信号: {ma_signal}")

    print(f"\n{'='*60}")
    print(f"📈 MACD指标")
    print(f"{'='*60}")
    print(f"MACD      : {latest['macd']:.4f}")
    print(f"Signal    : {latest['macd_signal']:.4f}")
    print(f"Histogram : {latest['macd_hist']:.4f}")
    macd_signal_text = "🟢 金叉（买入信号）" if latest['macd'] > latest['macd_signal'] else "🔴 死叉（卖出信号）"
    print(f"\nMACD信号: {macd_signal_text}")

    print(f"\n{'='*60}")
    print(f"📉 RSI指标 (14日)")
    print(f"{'='*60}")
    print(f"RSI值: {latest['rsi']:.2f}")
    if latest['rsi'] > 70:
        rsi_status = "🔴 超买（风险区域）"
    elif latest['rsi'] < 30:
        rsi_status = "🟢 超卖（机会区域）"
    else:
        rsi_status = "🟡 中性区域"
    print(f"RSI状态: {rsi_status}")

    print(f"\n{'='*60}")
    print(f"📊 布林带 (20日, 2倍标准差)")
    print(f"{'='*60}")
    print(f"上轨: {latest['boll_upper']:.2f} 元")
    print(f"中轨: {latest['boll_mid']:.2f} 元")
    print(f"下轨: {latest['boll_lower']:.2f} 元")
    print(f"当前: {latest['close']:.2f} 元")

    boll_pct = (latest['close'] - latest['boll_lower']) / (latest['boll_upper'] - latest['boll_lower']) * 100
    if boll_pct < 10:
        boll_status = "🟢 接近下轨（超卖）"
    elif boll_pct > 90:
        boll_status = "🔴 接近上轨（超买）"
    else:
        boll_status = f"🟡 中间区域 ({boll_pct:.0f}%位置)"
    print(f"布林带位置: {boll_status}")

    print(f"\n{'='*60}")
    print(f"🎯 综合评分")
    print(f"{'='*60}")

    score = 0
    max_score = 5

    # 均线评分
    if latest['close'] > latest['ma5']:
        score += 1
        print(f"✓ 股价在MA5之上 (+1分)")
    else:
        print(f"✗ 股价在MA5之下 (0分)")

    # MACD评分
    if latest['macd'] > latest['macd_signal']:
        score += 1
        print(f"✓ MACD金叉 (+1分)")
    else:
        print(f"✗ MACD死叉 (0分)")

    # RSI评分
    if latest['rsi'] < 30:
        score += 1
        print(f"✓ RSI超卖 (+1分)")
    elif latest['rsi'] < 50:
        print(f"○ RSI中性 (0分)")
    else:
        print(f"✗ RSI超买/偏高 (0分)")

    # 布林带评分
    if latest['close'] < latest['boll_lower']:
        score += 1
        print(f"✓ 价格触及下轨 (+1分)")
    elif latest['close'] < latest['boll_mid']:
        print(f"○ 价格在中轨之下 (0分)")
    else:
        print(f"✗ 价格在中轨之上 (0分)")

    # 趋势评分
    if latest['ma5'] > latest['ma20']:
        score += 1
        print(f"✓ 短期趋势向上 (+1分)")
    else:
        print(f"✗ 短期趋势向下 (0分)")

    print(f"\n技术面得分: {score}/{max_score}")

    # 操作建议
    print(f"\n{'='*60}")
    print(f"💡 操作建议")
    print(f"{'='*60}")

    if score >= 4:
        print(f"🟢 强烈买入信号")
        print(f"   建议: 可考虑分批买入")
    elif score >= 3:
        print(f"🟡 观望/谨慎买入")
        print(f"   建议: 等待更好入场点")
    elif score >= 2:
        print(f"🟠 持有/减仓")
        print(f"   建议: 已持有可考虑减仓")
    else:
        print(f"🔴 卖出信号")
        print(f"   建议: 建议止损离场")

    # 近期涨跌
    print(f"\n{'='*60}")
    print(f"📊 近期表现")
    print(f"{'='*60}")
    for i in [3, 5, 10, 20]:
        if len(df) > i:
            change = (df['close'].iloc[-1] / df['close'].iloc[-i-1] - 1) * 100
            print(f"近{i}日涨跌: {change:+.2f}%")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    # 分析金风科技
    analyze_stock("002202", "金风科技")