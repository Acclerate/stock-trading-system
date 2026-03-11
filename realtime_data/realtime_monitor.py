#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时股票强弱监控系统 - 掘金SDK
使用 current() 函数获取实时行情快照
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置环境变量避免编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

print("\n" + "="*130)
print("  实时股票强弱监控系统 - 掘金SDK (使用 current 函数)")
print("="*130)

# 导入掘金SDK
try:
    from gm.api import set_token, current, history_n
    from data.config_data_source import DATA_SOURCE_CONFIG
except ImportError as e:
    print(f"错误: 无法导入掘金SDK - {e}")
    print("请确保已安装 gm 包: pip install gm")
    sys.exit(1)

# 设置Token
token = DATA_SOURCE_CONFIG['sources']['diggold']['token']
if not token:
    print("错误: DIGGOLD_TOKEN 未配置")
    print("请在 .env 文件中配置 DIGGOLD_TOKEN")
    sys.exit(1)

set_token(token)
print(f"掘金SDK已初始化 (Token: {token[:16]}...)")

# 导入其他依赖
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
import time

# 测试股票列表
STOCK_NAMES = {
    'SHSE.600644': '乐山电力',
    'SZSE.000818': '航锦科技',
    'SZSE.002202': '金风科技',
    'SZSE.000988': '华工科技',
}
SYMBOLS = list(STOCK_NAMES.keys())

# 技术指标参数
MA_SHORT = 5
MA_LONG = 20
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# 全局状态 - 存储历史数据用于计算技术指标
price_history = {}  # {symbol: DataFrame with OHLCV data}
prev_close_price = {}  # 存储昨收价用于计算当天涨跌
last_alert_time = {}
last_close_price = {}  # 记录上次收盘价用于计算涨跌


def init_price_history():
    """初始化价格历史数据"""
    print("\n正在初始化历史数据...")
    end_date = datetime.now().strftime('%Y-%m-%d')

    for symbol in SYMBOLS:
        try:
            # 获取最近200条历史数据用于计算技术指标
            data = history_n(
                symbol=symbol,
                frequency='60s',
                count=200,
                end_time=end_date,
                df=True
            )

            if data is not None and not data.empty:
                # 处理数据格式
                if 'eob' in data.columns:
                    data['datetime'] = pd.to_datetime(data['eob'])
                elif 'bob' in data.columns:
                    data['datetime'] = pd.to_datetime(data['bob'])

                # 确保所有列都存在
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                for col in required_cols:
                    if col not in data.columns:
                        data[col] = 0

                # 只保留需要的列
                data = data[['datetime', 'open', 'high', 'low', 'close', 'volume']].copy()

                price_history[symbol] = data
                last_close_price[symbol] = data['close'].iloc[-1]

                # 获取昨收价（使用日线数据）
                try:
                    daily_data = history_n(
                        symbol=symbol,
                        frequency='1d',
                        count=10,
                        end_time=end_date,
                        df=True
                    )
                    if daily_data is not None and not daily_data.empty and len(daily_data) >= 2:
                        # 倒数第二条是昨天，倒数第一条是今天
                        if len(daily_data) >= 2:
                            # 检查今天是否有数据
                            today_data = daily_data.iloc[-1]
                            # 如果今天的开盘价和历史数据最后一条接近，说明今天数据已更新
                            if abs(today_data['open'] - data['close'].iloc[-1]) < 0.01 or today_data['datetime'].date() == datetime.now().date():
                                # 使用昨天的收盘价作为昨收价
                                prev_close_price[symbol] = daily_data.iloc[-2]['close']
                            else:
                                # 今天还没有新数据，用最后一条的收盘价
                                prev_close_price[symbol] = daily_data.iloc[-1]['close']
                        else:
                            prev_close_price[symbol] = daily_data.iloc[-1]['close']
                    else:
                        prev_close_price[symbol] = 0
                except:
                    prev_close_price[symbol] = 0

                print(f"  {STOCK_NAMES[symbol]}: 已加载 {len(data)} 条历史数据, 昨收: {prev_close_price[symbol]:.2f}")
            else:
                print(f"  {STOCK_NAMES[symbol]}: 获取历史数据失败")
                # 创建空的DataFrame
                price_history[symbol] = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
                last_close_price[symbol] = 0
                prev_close_price[symbol] = 0
        except Exception as e:
            print(f"  {STOCK_NAMES[symbol]}: 初始化失败 - {e}")
            price_history[symbol] = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
            last_close_price[symbol] = 0
            prev_close_price[symbol] = 0


def update_with_current_tick(symbol, tick_data):
    """用实时tick数据更新历史数据"""
    if symbol not in price_history:
        price_history[symbol] = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

    current_df = price_history[symbol]

    # 获取tick数据中的价格信息
    price = tick_data.get('price', 0)
    if price == 0:
        price = tick_data.get('close', 0)

    volume = tick_data.get('volume', 0)
    amount = tick_data.get('amount', 0)

    current_time = datetime.now()

    # 获取当前分钟的开盘价（如果是新的一分钟）
    if len(current_df) > 0:
        last_time = current_df['datetime'].iloc[-1]
        # 如果是同一分钟，更新该分钟的数据
        if current_time.strftime('%Y-%m-%d %H:%M') == last_time.strftime('%Y-%m-%d %H:%M'):
            # 更新当前K线
            current_df.loc[current_df.index[-1], 'high'] = max(current_df['high'].iloc[-1], price)
            current_df.loc[current_df.index[-1], 'low'] = min(current_df['low'].iloc[-1], price)
            current_df.loc[current_df.index[-1], 'close'] = price
            current_df.loc[current_df.index[-1], 'volume'] = volume
        else:
            # 新的一分钟，创建新的K线
            new_row = {
                'datetime': current_time,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
            current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        # 第一条数据
        new_row = {
            'datetime': current_time,
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': volume
        }
        current_df = pd.DataFrame([new_row])

    # 限制数据窗口
    if len(current_df) > 200:
        current_df = current_df.tail(200).reset_index(drop=True)

    price_history[symbol] = current_df

    return price


def calculate_strength(df):
    """计算强弱指标"""
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

        macd_result = ta.macd(pd.Series(close), fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        if macd_result is not None and not macd_result.empty:
            macd = macd_result.iloc[:, 0].values
            macd_signal = macd_result.iloc[:, 1].values if len(macd_result.columns) > 1 else np.zeros(len(close))
            macd_hist = macd_result.iloc[:, 2].values if len(macd_result.columns) > 2 else np.zeros(len(close))
        else:
            macd = np.zeros(len(close))
            macd_signal = np.zeros(len(close))
            macd_hist = np.zeros(len(close))

        rsi = ta.rsi(pd.Series(close), length=RSI_PERIOD).values

        # 布林带
        boll = ta.bbands(pd.Series(close), length=20, std=2)
        if boll is not None and not boll.empty:
            upper = boll.iloc[:, 0].values
            lower = boll.iloc[:, 2].values if len(boll.columns) > 2 else boll.iloc[:, 0].values
        else:
            upper = np.full(len(close), np.nan)
            lower = np.full(len(close), np.nan)

        # ADX
        adx_result = ta.adx(pd.Series(high), pd.Series(low), pd.Series(close), length=14)
        if adx_result is not None and not adx_result.empty:
            adx = adx_result.iloc[:, 0].values
        else:
            adx = np.full(len(close), 20)

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

        # 计算涨跌幅
        if len(close) >= 2:
            change_pct = ((close[-1] - close[-2]) / close[-2]) * 100
        else:
            change_pct = 0

        # 计算强弱评分
        trend_score = 50
        if current_ma_short > current_ma_long:
            trend_score += 15
        else:
            trend_score -= 15
        if current_macd > current_macd_signal:
            trend_score += 15
            if current_macd_hist > 0:
                trend_score += 5
        else:
            trend_score -= 15
        if current_adx > 25:
            trend_score += min(15, (current_adx - 25) / 2)

        trend_score = max(0, min(100, trend_score))

        # 动量评分
        momentum_score = 50
        if current_rsi > 50:
            momentum_score += (current_rsi - 50) * 0.5
        else:
            momentum_score -= (50 - current_rsi) * 0.5

        if pd.notna(current_upper) and pd.notna(current_lower):
            boll_width = current_upper - current_lower
            if boll_width > 0:
                if current_price > current_upper:
                    momentum_score += 10
                elif current_price < current_lower:
                    momentum_score -= 10
                else:
                    position = (current_price - current_lower) / boll_width
                    momentum_score += (position - 0.5) * 20

        momentum_score = max(0, min(100, momentum_score))

        # 成交量评分
        if len(volume) >= 5:
            recent_vol = volume[-1]
            avg_vol = np.mean(volume[-5:])
            if avg_vol > 0:
                if recent_vol > avg_vol * 1.2:
                    volume_score = 75 + min(25, (recent_vol / avg_vol - 1.2) * 50)
                elif recent_vol < avg_vol * 0.8:
                    volume_score = 25 - min(25, (1 - recent_vol / avg_vol) * 50)
                else:
                    volume_score = 50
            else:
                volume_score = 50
        else:
            volume_score = 50

        # 综合评分
        overall_strength = (
            trend_score * 0.35 +
            momentum_score * 0.30 +
            volume_score * 0.20 +
            50 * 0.15  # 波动率暂时用50代替
        )

        return {
            'price': current_price,
            'change_pct': change_pct,
            'trend_score': trend_score,
            'momentum_score': momentum_score,
            'volume_score': volume_score,
            'overall_strength': overall_strength,
            'rsi': current_rsi,
            'adx': current_adx,
            'macd_hist': current_macd_hist,
            'ma_diff_pct': ((current_ma_short / current_ma_long) - 1) * 100 if current_ma_long > 0 else 0
        }

    except Exception as e:
        return None


def print_header():
    """打印表头"""
    print("\n" + "="*150)
    print(f"{'股票':<12} {'价格':<10} {'涨跌':<10} {'当天涨跌':<10} {'综合评分':<12} {'趋势':<10} {'动量':<10} {'成交量':<10} {'评级':<10}")
    print("="*150)


def get_rating(strength):
    """获取评级"""
    if strength >= 75:
        return "[超强]"
    elif strength >= 60:
        return "[强势]"
    elif strength >= 45:
        return "[中性]"
    elif strength >= 30:
        return "[弱势]"
    else:
        return "[超弱]"


def get_trend_status(trend_score):
    """获取趋势状态"""
    if trend_score > 55:
        return "[多头]"
    elif trend_score < 45:
        return "[空头]"
    else:
        return "[震荡]"


def get_momentum_status(momentum_score):
    """获取动量状态"""
    if momentum_score > 55:
        return "[强]"
    elif momentum_score < 45:
        return "[弱]"
    else:
        return "[中]"


def get_volume_status(volume_score):
    """获取成交量状态"""
    if volume_score > 55:
        return "[放量]"
    elif volume_score < 45:
        return "[缩量]"
    else:
        return "[平稳]"


def print_result(symbol, name, analysis, tick_data=None):
    """打印分析结果"""
    strength = analysis['overall_strength']
    price = analysis['price']
    change_pct = analysis.get('change_pct', 0)

    # 计算当天涨跌幅（基于昨收价）
    day_change_pct = 0
    if symbol in prev_close_price and prev_close_price[symbol] > 0:
        day_change_pct = ((price - prev_close_price[symbol]) / prev_close_price[symbol]) * 100
    elif tick_data:
        # 如果没有昨收价，尝试使用tick中的open作为参考
        open_price = tick_data.get('open', 0)
        if open_price > 0:
            day_change_pct = ((price - open_price) / open_price) * 100

    change_str = f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%"
    day_change_str = f"+{day_change_pct:.2f}%" if day_change_pct >= 0 else f"{day_change_pct:.2f}%"

    rating = get_rating(strength)
    trend_str = get_trend_status(analysis['trend_score'])
    mom_str = get_momentum_status(analysis['momentum_score'])
    vol_str = get_volume_status(analysis['volume_score'])

    # 如果有tick数据，显示买卖一档
    tick_info = ""
    if tick_data and 'quotes' in tick_data and tick_data['quotes']:
        quote = tick_data['quotes'][0]
        bid_p = quote.get('bid_p', 0)
        ask_p = quote.get('ask_p', 0)
        if bid_p > 0 and ask_p > 0:
            tick_info = f" 买一:{bid_p:.2f} 卖一:{ask_p:.2f}"

    print(f"{name:<12} {price:<10.2f} {change_str:<10} {day_change_str:<10} {strength:<12.1f} {trend_str:<10} {mom_str:<10} {vol_str:<10} {rating:<10}{tick_info}")


def check_alert(symbol, name, analysis, current_time):
    """检查告警"""
    alerts = []

    # 检查告警冷却时间（5分钟）
    if symbol in last_alert_time:
        time_diff = (current_time - last_alert_time[symbol]).total_seconds()
        if time_diff < 300:  # 5分钟内不重复告警
            return

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
        last_alert_time[symbol] = current_time
        for alert in alerts:
            print(f"    >>> !ALERT! {name} {alert}")


def main():
    """主函数"""
    # 动态生成监控股票列表字符串
    stock_list_str = "、".join([STOCK_NAMES[s] for s in SYMBOLS])

    print("\n监控股票:", stock_list_str)
    print("启动时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("="*130)

    # 初始化历史数据
    init_price_history()

    print("\n模式说明:")
    print("  - 使用 current() 函数获取实时行情快照")
    print("  - 每3秒更新一次数据")
    print("  - 在交易时间内会显示实时行情")
    print("  - 非交易时间可能无数据或显示最后收盘价")
    print("\n按 Ctrl+C 停止监控\n")

    print_header()

    try:
        update_count = 0
        while True:
            current_time = datetime.now()
            now_str = current_time.strftime('%H:%M:%S')
            update_count += 1

            print(f"\n[{now_str}] 第 {update_count} 次更新 (使用 current 函数):")

            # 获取实时行情快照
            try:
                tick_data_list = current(symbols=SYMBOLS)

                if tick_data_list is None or len(tick_data_list) == 0:
                    print("  未获取到实时数据（可能非交易时间）")
                else:
                    # 处理每个股票的实时数据
                    for tick_data in tick_data_list:
                        symbol = tick_data.get('symbol', '')
                        name = STOCK_NAMES.get(symbol, symbol)

                        if symbol and symbol in price_history:
                            # 用实时数据更新历史数据
                            price = update_with_current_tick(symbol, tick_data)

                            # 计算涨跌幅（相对于上次收盘价）
                            if symbol in last_close_price and last_close_price[symbol] > 0:
                                real_change_pct = ((price - last_close_price[symbol]) / last_close_price[symbol]) * 100
                            else:
                                real_change_pct = 0

                            # 分析
                            df = price_history[symbol]
                            if len(df) >= 30:
                                analysis = calculate_strength(df)
                                if analysis:
                                    # 使用实时计算的涨跌幅
                                    analysis['change_pct'] = real_change_pct
                                    print_result(symbol, name, analysis, tick_data)
                                    check_alert(symbol, name, analysis, current_time)

                            # 更新上次收盘价
                            last_close_price[symbol] = price

            except Exception as e:
                print(f"  获取实时数据失败: {e}")
                import traceback
                traceback.print_exc()

            # 等待3秒
            print("\n等待3秒后继续...")
            time.sleep(3)

    except KeyboardInterrupt:
        print("\n\n" + "="*150)
        print("监控已停止")
        print("="*150)


if __name__ == "__main__":
    main()
