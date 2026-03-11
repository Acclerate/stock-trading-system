#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时股票强弱监控系统 - 掘金SDK事件驱动模式
真正的实时订阅，通过on_bar回调接收实时K线推送
"""

import sys
import os
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入掘金SDK
from gm.api import subscribe, run, set_token

# 导入配置
from data.config_data_source import DATA_SOURCE_CONFIG
import config.realtime_strength_config as cfg

# 测试股票列表
TEST_STOCKS = {
    'SHSE.600644': '乐山电力',
    'SZSE.000818': '航锦科技',
    'SZSE.002202': '金风科技',
    'SZSE.000988': '华工科技',
}
SYMBOLS = list(TEST_STOCKS.keys())

# 技术指标参数
MA_SHORT = cfg.MA_SHORT
MA_LONG = cfg.MA_LONG
MACD_FAST = cfg.MACD_FAST
MACD_SLOW = cfg.MACD_SLOW
MACD_SIGNAL = cfg.MACD_SIGNAL
RSI_PERIOD = cfg.RSI_PERIOD
BOLL_PERIOD = cfg.BOLL_PERIOD
BOLL_STD = cfg.BOLL_STD
ADX_PERIOD = cfg.ADX_PERIOD
ATR_PERIOD = cfg.ATR_PERIOD

# 全局状态
price_data = {}
last_analysis = {}


def print_header():
    """打印表头"""
    print("\n" + "="*100)
    print(f"{'股票':<12} {'价格':<10} {'涨跌':<10} {'综合评分':<12} {'趋势':<10} {'动量':<10} {'成交量':<10} {'RSI':<8} {'ADX':<8} {'评级':<10}")
    print("="*100)


def print_analysis_line(symbol, name, analysis):
    """打印分析结果一行"""
    strength = analysis['overall_strength']
    price = analysis['price']
    change_pct = analysis.get('change_pct', 0)

    # 涨跌幅显示
    if change_pct >= 0:
        change_str = f"+{change_pct:.2f}%"
    else:
        change_str = f"{change_pct:.2f}%"

    # 强弱评级
    if strength >= 75:
        rating = "[超强]"
    elif strength >= 60:
        rating = "[强势]"
    elif strength >= 45:
        rating = "[中性]"
    elif strength >= 30:
        rating = "[弱势]"
    else:
        rating = "[超弱]"

    # 趋势状态
    trend_str = "[多头]" if analysis['trend_score'] > 55 else "[空头]" if analysis['trend_score'] < 45 else "[震荡]"

    # 动量状态
    mom_str = "[强]" if analysis['momentum_score'] > 55 else "[弱]" if analysis['momentum_score'] < 45 else "[中]"

    # 成交量状态
    vol_str = "[放量]" if analysis['volume_score'] > 55 else "[缩量]" if analysis['volume_score'] < 45 else "[平稳]"

    print(f"{name:<12} {price:<10.2f} {change_str:<10} {strength:<12.1f} {trend_str:<10} {mom_str:<10} {vol_str:<10} {analysis['rsi']:<8.1f} {analysis['adx']:<8.1f} {rating:<10}")


def analyze_strength(df):
    """分析股票强弱"""
    if df is None or len(df) < 30:
        return None

    try:
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        volume = df['volume'].values.astype(float)

        # 计算技术指标
        ma_short = ta.sma(pd.Series(close), length=MA_SHORT).values
        ma_long = ta.sma(pd.Series(close), length=MA_LONG).values

        # MACD
        macd_result = ta.macd(pd.Series(close), fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        macd = macd_result.iloc[:, 0].values if not macd_result.empty else np.zeros(len(close))
        macd_signal = macd_result.iloc[:, 1].values if len(macd_result.columns) > 1 else np.zeros(len(close))
        macd_hist = macd_result.iloc[:, 2].values if len(macd_result.columns) > 2 else np.zeros(len(close))

        # RSI
        rsi = ta.rsi(pd.Series(close), length=RSI_PERIOD).values

        # 布林带
        boll = ta.bbands(pd.Series(close), length=BOLL_PERIOD, std=BOLL_STD)
        if boll is not None and not boll.empty:
            upper = boll.iloc[:, 0].values
            lower = boll.iloc[:, 2].values if len(boll.columns) > 2 else boll.iloc[:, 0].values
        else:
            upper = np.full(len(close), np.nan)
            lower = np.full(len(close), np.nan)

        # ADX
        adx_result = ta.adx(pd.Series(high), pd.Series(low), pd.Series(close), length=ADX_PERIOD)
        adx = adx_result.iloc[:, 0].values if not adx_result.empty else np.full(len(close), 20)

        # ATR
        atr_result = ta.atr(pd.Series(high), pd.Series(low), pd.Series(close), length=ATR_PERIOD)
        atr = atr_result.values if not atr_result.empty else np.zeros(len(close))

        # 获取最新值
        current_price = close[-1]
        current_ma_short = ma_short[-1] if not pd.isna(ma_short[-1]) else close[-1]
        current_ma_long = ma_long[-1] if not pd.isna(ma_long[-1]) else close[-1]
        current_macd = macd[-1] if not pd.isna(macd[-1]) else 0
        current_macd_signal = macd_signal[-1] if not pd.isna(macd_signal[-1]) else 0
        current_macd_hist = macd_hist[-1] if not pd.isna(macd_hist[-1]) else 0
        current_rsi = rsi[-1] if not pd.isna(rsi[-1]) else 50
        current_upper = upper[-1]
        current_lower = lower[-1]
        current_adx = adx[-1] if not pd.isna(adx[-1]) else 20
        current_atr = atr[-1] if not pd.isna(atr[-1]) else 0

        # 计算涨跌幅
        if len(close) >= 2:
            change_pct = ((close[-1] - close[-2]) / close[-2]) * 100
        else:
            change_pct = 0

        # 计算强弱评分
        trend_score = calculate_trend_score(current_ma_short, current_ma_long,
                                           current_macd, current_macd_signal,
                                           current_macd_hist, current_adx)

        momentum_score = calculate_momentum_score(current_rsi, current_price,
                                                  current_upper, current_lower)

        volume_score = calculate_volume_score(volume)

        volatility_score = calculate_volatility_score(current_atr, current_price)

        # 综合强弱评分
        overall_strength = (
            trend_score * 0.35 +
            momentum_score * 0.30 +
            volume_score * 0.20 +
            volatility_score * 0.15
        )

        return {
            'price': current_price,
            'change_pct': change_pct,
            'trend_score': trend_score,
            'momentum_score': momentum_score,
            'volume_score': volume_score,
            'volatility_score': volatility_score,
            'overall_strength': overall_strength,
            'rsi': current_rsi,
            'adx': current_adx,
            'macd_hist': current_macd_hist,
            'ma_diff_pct': ((current_ma_short / current_ma_long) - 1) * 100 if current_ma_long > 0 else 0
        }

    except Exception as e:
        print(f"    分析出错: {e}")
        return None


def calculate_trend_score(ma_short, ma_long, macd, macd_signal, macd_hist, adx):
    """计算趋势强度评分"""
    score = 50
    if ma_short > ma_long:
        score += 15
    else:
        score -= 15
    if macd > macd_signal:
        score += 15
        if macd_hist > 0:
            score += 5
    else:
        score -= 15
    if adx > 25:
        score += min(15, (adx - 25) / 2)
    return max(0, min(100, score))


def calculate_momentum_score(rsi, price, upper, lower):
    """计算动量强度评分"""
    score = 50
    if rsi > 50:
        score += (rsi - 50) * 0.5
    else:
        score -= (50 - rsi) * 0.5
    if pd.notna(upper) and pd.notna(lower):
        boll_width = upper - lower
        if boll_width > 0:
            if price > upper:
                score += 10
            elif price < lower:
                score -= 10
            else:
                position = (price - lower) / boll_width
                score += (position - 0.5) * 20
    return max(0, min(100, score))


def calculate_volume_score(volume):
    """计算成交量强度评分"""
    if len(volume) < 5:
        return 50
    recent_vol = volume[-1]
    avg_vol = np.mean(volume[-5:])
    if avg_vol > 0:
        if recent_vol > avg_vol * 1.2:
            return 75 + min(25, (recent_vol / avg_vol - 1.2) * 50)
        elif recent_vol < avg_vol * 0.8:
            return 25 - min(25, (1 - recent_vol / avg_vol) * 50)
        else:
            return 50
    return 50


def calculate_volatility_score(atr, price):
    """计算波动率强度评分"""
    if pd.isna(atr) or price == 0:
        return 50
    atr_pct = (atr / price) * 100
    if 1 < atr_pct < 3:
        return 60 + min(40, (atr_pct - 1) * 20)
    elif atr_pct >= 3:
        return 50
    else:
        return max(0, atr_pct * 30)


# ========== 掘金SDK回调函数 ==========

def init(context):
    """策略初始化"""
    print("\n" + "="*100)
    print("  实时股票强弱监控系统 - 掘金SDK事件驱动模式")
    print("  监控股票: 乐山电力、航锦科技、金风科技、华工科技")
    print("  启动时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("="*100)
    print(f"\n已订阅 {len(SYMBOLS)} 只股票的 1 分钟实时行情")
    print(f"等待实时数据推送... (仅在交易时间内会有数据)")
    print(f"按 Ctrl+C 停止监控\n")

    # 订阅股票行情
    subscribe(SYMBOLS, frequency='60s')

    print_header()


def on_bar(bar):
    """K线数据推送回调 - 这里的数据是实时的！"""
    symbol = bar.symbol
    name = TEST_STOCKS.get(symbol, symbol)

    # 初始化该股票的数据
    if symbol not in price_data:
        price_data[symbol] = pd.DataFrame()

    # 添加新的K线数据
    new_row = {
        'datetime': pd.to_datetime(bar.eob),
        'open': float(bar.open),
        'high': float(bar.high),
        'low': float(bar.low),
        'close': float(bar.close),
        'volume': float(bar.volume)
    }

    price_data[symbol] = pd.concat([
        price_data[symbol],
        pd.DataFrame([new_row])
    ], ignore_index=True)

    # 限制数据窗口
    if len(price_data[symbol]) > 200:
        price_data[symbol] = price_data[symbol].tail(200).reset_index(drop=True)

    # 确保有足够的数据进行分析
    if len(price_data[symbol]) >= 30:
        # 执行强弱分析
        analysis = analyze_strength(price_data[symbol])

        if analysis:
            # 打印时间戳
            now_str = datetime.now().strftime('%H:%M:%S')
            print(f"\n[{now_str}] 收到 {name} 实时数据:")
            print_analysis_line(symbol, name, analysis)

            # 检查告警
            check_alert(symbol, name, analysis)


def on_tick(tick):
    """分笔数据推送回调"""
    pass


def check_alert(symbol, name, analysis):
    """检查告警"""
    alerts = []

    # 强势告警
    if analysis['overall_strength'] >= 75:
        alerts.append(f"[强势告警] 综合评分 {analysis['overall_strength']:.1f}")

    # 弱势告警
    elif analysis['overall_strength'] <= 30:
        alerts.append(f"[弱势告警] 综合评分 {analysis['overall_strength']:.1f}")

    # RSI超买告警
    if analysis['rsi'] >= 75:
        alerts.append(f"[RSI超买] {analysis['rsi']:.1f}")

    # RSI超卖告警
    elif analysis['rsi'] <= 25:
        alerts.append(f"[RSI超卖] {analysis['rsi']:.1f}")

    # 打印告警
    if alerts:
        for alert in alerts:
            print(f"    >>> {name} {alert}")


def on_order(order):
    """委托回调"""
    pass


def on_trade(trade):
    """成交回调"""
    pass


def on_stop(context):
    """策略停止回调"""
    print("\n监控已停止")


# ========== 主程序 ==========

def main():
    """主函数"""
    # 设置Token
    token = DATA_SOURCE_CONFIG['sources']['diggold']['token']
    if not token:
        print("错误: DIGGOLD_TOKEN 未配置")
        return

    from gm.api import set_token
    set_token(token)

    print("\n正在启动实时监控...")
    print("注意: 只有在交易时间内才会收到实时K线推送")
    print("      非交易时间会等待直到交易时间开始")
    print("\n如果长时间没有数据，请确认:")
    print("  1. 掘金量化终端已启动")
    print("  2. 当前是交易时间（周一至周五 9:30-15:00）")
    print("  3. DIGGOLD_TOKEN 配置正确")

    # 运行策略 - 这里会阻塞，等待回调
    run(
        init=init,
        on_bar=on_bar,
        on_tick=on_tick,
        on_order=on_order,
        on_trade=on_trade,
        on_stop=on_stop
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户停止监控")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
