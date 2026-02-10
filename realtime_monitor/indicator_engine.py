"""
技术指标计算引擎

从 jinfeng_realtime.py 提取指标计算逻辑，供轮询和事件驱动模式共享。

支持指标：
- 均线系统：MA5, MA10, MA20, MA60
- MACD：DIF, DEA, MACD柱
- RSI：RSI(6), RSI(14)
- KDJ：K, D, J
- 布林带：上轨、中轨、下轨
- ATR：真实波幅
- 成交量指标：量比
- ADX：趋势强度
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, Optional


class IndicatorEngine:
    """技术指标计算引擎"""

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有技术指标

        参数:
            df: 包含 OHLCV 数据的 DataFrame

        返回:
            添加了指标列的 DataFrame
        """
        if df is None or df.empty:
            raise ValueError("数据为空，无法计算指标")

        if len(df) < 20:
            raise ValueError("数据不足，无法计算指标（至少需要20条数据）")

        # 确保数值列是 float 类型
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        volume = df['volume'].values.astype(float)

        # ========== 均线系统 ==========
        df['ma5'] = talib.SMA(close, timeperiod=5)
        df['ma10'] = talib.SMA(close, timeperiod=10)
        df['ma20'] = talib.SMA(close, timeperiod=20)

        if len(df) >= 60:
            df['ma60'] = talib.SMA(close, timeperiod=60)
        else:
            df['ma60'] = np.nan

        # ========== MACD ==========
        macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist

        # ========== RSI ==========
        df['rsi'] = talib.RSI(close, timeperiod=14)
        df['rsi_6'] = talib.RSI(close, timeperiod=6)

        # ========== KDJ ==========
        slowk, slowd = talib.STOCH(high, low, close, fastk_period=9,
                                    slowk_period=3, slowd_period=3)
        df['kdj_k'] = slowk
        df['kdj_d'] = slowd
        df['kdj_j'] = 3 * slowk - 2 * slowd

        # ========== 布林带 ==========
        boll_upper, boll_mid, boll_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
        df['boll_upper'] = boll_upper
        df['boll_mid'] = boll_mid
        df['boll_lower'] = boll_lower

        # ========== ATR（真实波幅）==========
        df['atr'] = talib.ATR(high, low, close, timeperiod=14)

        # ========== 成交量指标 ==========
        df['volume_ma5'] = talib.SMA(volume, timeperiod=5)
        df['volume_ratio'] = df['volume'] / df['volume_ma5']

        # ========== ADX（趋势强度）==========
        df['adx'] = talib.ADX(high, low, close, timeperiod=14)

        return df

    @staticmethod
    def generate_signal(df: pd.DataFrame) -> Dict:
        """
        生成交易信号

        基于6个技术指标进行综合评分：
        1. 均线趋势（1分）：短期均线多头
        2. MACD（1分）：金叉且红柱
        3. RSI（1分）：健康区间（30-70）
        4. KDJ（1分）：金叉且J值向上
        5. 布林带（1分）：价格在中下轨之间
        6. 成交量（1分）：成交量放大（量比>1.2）

        参数:
            df: 包含技术指标的 DataFrame

        返回:
            {
                'signal': 'buy' | 'sell' | 'hold',
                'score': 0-6,
                'reason': '信号原因描述'
            }
        """
        if df is None or df.empty:
            return {'signal': 'hold', 'score': 0, 'reason': '无数据'}

        latest = df.iloc[-1]

        # 检查数据有效性
        if pd.isna(latest.get('ma5', np.nan)):
            return {'signal': 'hold', 'score': 0, 'reason': '数据不足'}

        score = 0
        reasons = []

        # 1. 均线趋势
        if not pd.isna(latest['ma5']) and not pd.isna(latest['ma10']):
            if latest['close'] > latest['ma5'] > latest['ma10']:
                score += 1
                reasons.append("短期均线多头")

        # 2. MACD
        if not pd.isna(latest['macd']) and not pd.isna(latest['macd_signal']):
            if latest['macd'] > latest['macd_signal'] and latest['macd_hist'] > 0:
                score += 1
                reasons.append("MACD金叉且红柱")

        # 3. RSI
        if not pd.isna(latest['rsi']):
            if 30 < latest['rsi'] < 70:
                score += 1
                reasons.append("RSI健康区间")

        # 4. KDJ
        if not pd.isna(latest['kdj_k']) and not pd.isna(latest['kdj_d']) and not pd.isna(latest['kdj_j']):
            if latest['kdj_k'] > latest['kdj_d'] and latest['kdj_j'] > latest['kdj_k']:
                score += 1
                reasons.append("KDJ金叉且J值向上")

        # 5. 布林带
        if not pd.isna(latest['boll_lower']) and not pd.isna(latest['boll_mid']) and not pd.isna(latest['boll_upper']):
            if latest['boll_lower'] < latest['close'] < latest['boll_mid']:
                score += 1
                reasons.append("价格在中下轨之间")

        # 6. 成交量
        if not pd.isna(latest['volume_ratio']):
            if latest['volume_ratio'] > 1.2:
                score += 1
                reasons.append("成交量放大")

        # 判断信号类型
        if score >= 5:
            signal = 'buy'
        elif score >= 4:
            signal = 'buy'
        elif score <= 2:
            signal = 'sell'
        else:
            signal = 'hold'

        return {
            'signal': signal,
            'score': score,
            'reason': ', '.join(reasons) if reasons else '无明显信号'
        }

    @staticmethod
    def get_signal_emoji(signal: str) -> str:
        """获取信号对应的 emoji"""
        emoji_map = {
            'buy': '🟢',
            'sell': '🔴',
            'hold': '🟡'
        }
        return emoji_map.get(signal, '⚪')

    @staticmethod
    def get_signal_description(signal: str, score: int) -> str:
        """获取信号描述"""
        if score >= 5:
            return "🟢 强烈买入信号"
        elif score >= 4:
            return "🟢 买入信号"
        elif score >= 3:
            return "🟡 观望"
        elif score >= 2:
            return "🟠 谨慎持有"
        else:
            return "🔴 卖出信号"
