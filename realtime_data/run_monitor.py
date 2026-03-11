#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时监控启动脚本
使用掘金SDK运行实时监控策略
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入配置
from data.config_data_source import DATA_SOURCE_CONFIG

# 设置Token
from gm.api import set_token
token = DATA_SOURCE_CONFIG['sources']['diggold']['token']
if not token:
    print("错误: DIGGOLD_TOKEN 未配置")
    sys.exit(1)

set_token(token)
print(f"掘金SDK已初始化 (Token: {token[:16]}...)")

# 导入并运行策略
# 方法：直接导入策略模块并调用掘金API的subscribe函数
from gm.api import history_n, subscribe
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

# 全局状态
price_data = {}


def calculate_strength(close, high, low, volume):
    """计算强弱指标"""
    # RSI
    delta = pd.Series(close).diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]

    # MA
    ma_short = pd.Series(close).rolling(window=MA_SHORT).mean().iloc[-1]
    ma_long = pd.Series(close).rolling(window=MA_LONG).mean().iloc[-1]

    # 涨跌幅
    change_pct = ((close[-1] - close[-2]) / close[-2]) * 100 if len(close) >= 2 else 0

    # 趋势评分
    trend_score = 70 if ma_short > ma_long else 30

    # 动量评分
    momentum_score = min(100, max(0, rsi))

    # 成交量评分
    if len(volume) >= 5:
        recent_vol = volume[-1]
        avg_vol = np.mean(volume[-5:])
        if avg_vol > 0:
            if recent_vol > avg_vol * 1.2:
                volume_score = 75
            elif recent_vol < avg_vol * 0.8:
                volume_score = 25
            else:
                volume_score = 50
        else:
            volume_score = 50
    else:
        volume_score = 50

    # 综合评分
    overall_strength = trend_score * 0.4 + momentum_score * 0.4 + volume_score * 0.2

    return {
        'price': close[-1],
        'change_pct': change_pct,
        'trend_score': trend_score,
        'momentum_score': momentum_score,
        'volume_score': volume_score,
        'overall_strength': overall_strength,
        'rsi': rsi,
        'ma_diff_pct': ((ma_short / ma_long) - 1) * 100 if ma_long > 0 else 0
    }


def print_header():
    print("\n" + "="*110)
    print(f"{'股票':<12} {'价格':<10} {'涨跌':<10} {'综合评分':<12} {'趋势':<10} {'动量(RSI)':<12} {'成交量':<10} {'评级':<10}")
    print("="*110)


def print_result(symbol, name, analysis):
    strength = analysis['overall_strength']
    price = analysis['price']
    change_pct = analysis.get('change_pct', 0)

    change_str = f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%"

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

    trend_str = "[多头]" if analysis['trend_score'] > 55 else "[空头]" if analysis['trend_score'] < 45 else "[震荡]"
    mom_str = f"{analysis['rsi']:.1f}"
    vol_str = "[放量]" if analysis['volume_score'] > 55 else "[缩量]" if analysis['volume_score'] < 45 else "[平稳]"

    print(f"{name:<12} {price:<10.2f} {change_str:<10} {strength:<12.1f} {trend_str:<10} {mom_str:<12} {vol_str:<10} {rating:<10}")


print("\n" + "="*110)
print("  实时股票强弱监控系统 - 轮询模式")
print("  监控股票: 乐山电力、航锦科技、金风科技、华工科技")
print("  启动时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print("="*110)
print("\n注意: 由于掘金SDK限制，当前使用轮询模式获取最新数据")
print("      每5秒更新一次数据")
print("      按 Ctrl+C 停止监控\n")

print_header()

try:
    while True:
        now_str = datetime.now().strftime('%H:%M:%S')
        print(f"\n[{now_str}] 获取最新数据...")

        for symbol in SYMBOLS:
            name = STOCK_NAMES.get(symbol, symbol)

            try:
                # 获取最近100条数据
                end_date = datetime.now().strftime('%Y-%m-%d')
                data = history_n(
                    symbol=symbol,
                    frequency='60s',
                    count=100,
                    end_time=end_date,
                    df=True
                )

                if data is not None and not data.empty and len(data) >= 30:
                    # 确保列名正确
                    if 'eob' in data.columns:
                        data['datetime'] = pd.to_datetime(data['eob'])

                    # 分析
                    analysis = calculate_strength(
                        data['close'].values,
                        data['high'].values,
                        data['low'].values,
                        data['volume'].values
                    )

                    print_result(symbol, name, analysis)

            except Exception as e:
                print(f"  {name}: 获取数据失败 - {e}")

        print("\n等待5秒后继续...")
        time.sleep(5)

except KeyboardInterrupt:
    print("\n\n监控已停止")
except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()
