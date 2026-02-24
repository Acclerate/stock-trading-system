# -*- coding: utf-8 -*-
"""
低位放量突破策略 - 信号生成模块

负责生成买入信号和执行安全检查
"""
import sys
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 处理相对导入和绝对导入
try:
    from .config import StrategyConfig
    from .indicators import IndicatorCalculator
except ImportError:
    from strategies.low_volume_breakout.config import StrategyConfig
    from strategies.low_volume_breakout.indicators import IndicatorCalculator


class SignalType(Enum):
    """信号类型"""
    BUY = "买入"
    WAIT = "观望"
    SELL = "卖出"


@dataclass
class SignalResult:
    """信号结果"""
    symbol: str
    signal_type: SignalType
    score: float
    reasons: List[str]
    indicators: Dict[str, float]
    market_cap: Optional[float] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'score': self.score,
            'reasons': ' + '.join(self.reasons),
            'market_cap': self.market_cap,
            **self.indicators
        }


class SignalGenerator:
    """信号生成器"""

    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        初始化信号生成器

        Args:
            config: 策略配置
        """
        self.config = config or StrategyConfig()
        self.indicator_calc = IndicatorCalculator(config)

    def check_basic_conditions(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        检查基本条件（必须全部满足）- 机构级版本

        Args:
            df: 包含指标的DataFrame

        Returns:
            (是否满足, 原因列表)
        """
        if df.empty or len(df) < self.config.min_data_points:
            return False, ["数据不足"]

        latest = df.iloc[-1]
        reasons = []

        # ==================== 机构级条件1：趋势过滤 ====================
        if self.config.require_trend_filter:
            ma20 = latest.get(f'ma{self.config.ma_mid}', 0)
            ma60 = latest.get(f'ma{self.config.ma_long}', 0)
            if ma20 <= 0 or ma60 <= 0:
                return False, ["均线指标未计算（数据不足60天）"]
            if ma20 <= ma60:
                return False, [f"趋势未转强 (MA20={ma20:.2f} <= MA60={ma60:.2f})，避免下跌中继"]
            reasons.append(f"趋势向上(MA20>MA60)")

        # ==================== 机构级条件2：长期低位震荡（两年低位）====================
        price_position = latest.get('price_position', 0)
        if price_position <= 0:
            return False, ["指标未计算（数据不足730天）"]
        if price_position >= self.config.low_threshold:
            return False, [f"价格位置过高 ({price_position:.1%} >= {self.config.low_threshold:.0%})"]
        reasons.append(f"两年低位({price_position:.1%})")

        # ==================== 机构级条件3：成交量连续放大验证 ====================
        if self.config.require_volume_progressive:
            vol5 = latest.get(f'volume_ma{self.config.volume_ma_short}', 0)
            vol20 = latest.get(f'volume_ma{self.config.volume_ma_mid}', 0)
            vol60 = latest.get(f'volume_ma{self.config.volume_ma_long}', 0)

            if vol5 <= 0 or vol20 <= 0 or vol60 <= 0:
                return False, ["均量指标未计算（数据不足60天）"]
            if vol5 <= vol20 or vol20 <= vol60:
                return False, [f"成交量未连续放大 (VOL5={vol5:.0f} <= VOL20={vol20:.0f} 或 VOL20 <= VOL60={vol60:.0f})"]
            reasons.append("量能递进")

        # ==================== 条件4：近期逐步放量 ====================
        volume_expansion = latest.get('volume_expansion', 0)
        volume_trend = latest.get('volume_trend', 0)

        if volume_expansion <= 0 or volume_trend <= 0:
            return False, ["放量指标未计算（数据不足60天）"]

        if volume_expansion < self.config.volume_ratio:
            return False, [f"放量不足 ({volume_expansion:.2f}x < {self.config.volume_ratio:.1f}x)"]

        if volume_trend < 1.0:
            return False, [f"均量趋势向下 ({volume_trend:.2f} < 1.0)"]

        reasons.append(f"放量({volume_expansion:.1f}x)")

        # ==================== 机构级条件5：换手率过滤 ====================
        if self.config.min_turnover_rate > 0:
            # 计算当日换手率
            if len(df) >= 1:
                turnover_rate = self._calculate_turnover_rate(latest, df)
                if turnover_rate < self.config.min_turnover_rate:
                    return False, [f"换手率过低 ({turnover_rate:.2%} < {self.config.min_turnover_rate:.1%})"]
                reasons.append(f"换手率({turnover_rate:.1%})")

        # ==================== 机构级条件6：波动率压缩 ====================
        if self.config.max_volatility_20d < 1.0:  # 启用波动率过滤
            if len(df) >= 20:
                volatility_20d = self._calculate_volatility_20d(df)
                if volatility_20d > self.config.max_volatility_20d:
                    return False, [f"波动率过高 ({volatility_20d:.1%} > {self.config.max_volatility_20d:.0%})"]
                reasons.append(f"波动压缩({volatility_20d:.1%})")

        # ==================== 条件7：趋势启动确认 ====================
        trend_strength = latest.get('trend_strength', 0)
        if trend_strength <= 0:
            return False, ["趋势指标未计算（数据不足）"]
        if trend_strength <= 1.0:
            return False, [f"趋势未转强 (收盘价 < MA{self.config.ma_long})"]
        reasons.append(f"趋势启动({trend_strength:.1%})")

        return True, reasons

    def _calculate_turnover_rate(self, latest: pd.Series, df: pd.DataFrame) -> float:
        """
        计算换手率

        Args:
            latest: 最新一行数据
            df: 完整的DataFrame

        Returns:
            换手率（使用成交量估算）
        """
        try:
            # 使用当日成交量 / 流通市值估算换手率
            volume = latest.get('volume', 0)
            # 简化处理：假设平均流通股本，实际应从数据源获取
            # 这里使用相对换手率 = 当日成交量 / 20日平均成交量
            avg_volume_20d = df['volume'].tail(20).mean()
            if avg_volume_20d > 0:
                return volume / avg_volume_20d * 0.05  # 校准系数
            return 0
        except:
            return 0

    def _calculate_volatility_20d(self, df: pd.DataFrame) -> float:
        """
        计算20日振幅

        Args:
            df: 包含OHLC数据的DataFrame

        Returns:
            20日振幅（百分比）
        """
        try:
            df_20d = df.tail(20)
            high_20d = df_20d['high'].max()
            low_20d = df_20d['low'].min()

            if low_20d > 0:
                return (high_20d - low_20d) / low_20d
            return 0
        except:
            return 0

    def check_safety_conditions(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        检查安全条件（用于过滤高风险信号）

        Args:
            df: 包含指标的DataFrame

        Returns:
            (是否安全, 警告列表)
        """
        latest = df.iloc[-1]
        warnings = []

        # 检查RSI超买
        rsi = latest.get('rsi', 50)
        if rsi >= self.config.rsi_overbought:
            warnings.append(f"RSI超买({rsi:.1f})")

        # 检查布林带位置（价格是否过度偏离中轨）
        boll_mid = latest.get('boll_mid', latest['close'])
        boll_upper = latest.get('boll_upper', latest['close'] * 1.1)
        boll_lower = latest.get('boll_lower', latest['close'] * 0.9)

        if boll_upper != boll_lower:
            boll_position = (latest['close'] - boll_lower) / (boll_upper - boll_lower)
            if boll_position > 0.8:
                warnings.append(f"价格接近BOLL上轨({boll_position:.1%})")

        # 检查近期涨幅是否过大
        if len(df) >= 5:
            recent_return = (latest['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close']
            if recent_return > self.config.recent_return_threshold:
                warnings.append(f"近期涨幅过大({recent_return:.1%})")

        is_safe = len(warnings) == 0
        return is_safe, warnings

    def calculate_score(self, df: pd.DataFrame, market_cap: Optional[float] = None) -> float:
        """
        计算股票综合得分

        Args:
            df: 包含指标的DataFrame
            market_cap: 市值（亿元）

        Returns:
            综合得分 (0-100)
        """
        latest = df.iloc[-1]
        score = 0

        # 1. 位置得分 (0-30分)
        price_position = latest.get('price_position', 0.5)
        position_score = 30 * (1 - price_position / self.config.low_threshold)
        score += max(0, min(30, position_score))

        # 2. 放量得分 (0-40分)
        volume_expansion = latest.get('volume_expansion', 0)
        volume_trend = latest.get('volume_trend', 0)
        expansion_score = 20 * min(2, volume_expansion / self.config.volume_ratio)
        trend_score = 20 * min(1.5, volume_trend)
        score += max(0, min(40, expansion_score + trend_score))

        # 3. 趋势得分 (0-20分)
        trend_strength = latest.get('trend_strength', 1.0)
        trend_score = 20 * min(1.2, trend_strength - 0.8) / 0.4
        score += max(0, min(20, trend_score))

        # 4. 市值得分 (0-10分)
        if market_cap is not None:
            # 中小市值适当加分
            if market_cap < 50:
                score += 10
            elif market_cap < 100:
                score += 5

        return min(100, score)

    def generate_signal(self, symbol: str, df: pd.DataFrame,
                       market_cap: Optional[float] = None) -> SignalResult:
        """
        生成交易信号

        Args:
            symbol: 股票代码
            df: 包含OHLCV数据的DataFrame
            market_cap: 市值（亿元）

        Returns:
            信号结果
        """
        # 计算所有指标
        df = self.indicator_calc.calculate_all_indicators(df)

        if df.empty:
            return SignalResult(
                symbol=symbol,
                signal_type=SignalType.WAIT,
                score=0,
                reasons=["数据不足"],
                indicators={}
            )

        # 获取最新指标值
        indicators = self.indicator_calc.get_latest_signals(df)

        # 检查基本条件
        passed, reasons = self.check_basic_conditions(df)

        if not passed:
            return SignalResult(
                symbol=symbol,
                signal_type=SignalType.WAIT,
                score=0,
                reasons=reasons,
                indicators=indicators,
                market_cap=market_cap
            )

        # 检查安全条件
        is_safe, warnings = self.check_safety_conditions(df)

        if not is_safe:
            reasons.extend(warnings)

        # 计算得分
        score = self.calculate_score(df, market_cap)

        # 生成信号
        signal_type = SignalType.BUY if score > self.config.buy_threshold else SignalType.WAIT

        return SignalResult(
            symbol=symbol,
            signal_type=signal_type,
            score=score,
            reasons=reasons,
            indicators=indicators,
            market_cap=market_cap
        )

    def generate_signals_batch(self, data_dict: Dict[str, pd.DataFrame],
                              market_cap_dict: Optional[Dict[str, float]] = None) -> List[SignalResult]:
        """
        批量生成交易信号

        Args:
            data_dict: 股票代码到DataFrame的映射
            market_cap_dict: 股票代码到市值的映射

        Returns:
            信号结果列表
        """
        results = []

        for symbol, df in data_dict.items():
            market_cap = market_cap_dict.get(symbol) if market_cap_dict else None
            result = self.generate_signal(symbol, df, market_cap)
            results.append(result)

        # 按得分排序
        results.sort(key=lambda x: x.score, reverse=True)

        return results


# 便捷函数
def generate_signal(symbol: str, df: pd.DataFrame,
                   config: Optional[StrategyConfig] = None,
                   market_cap: Optional[float] = None) -> SignalResult:
    """
    便捷函数：生成单个股票的信号

    Args:
        symbol: 股票代码
        df: OHLCV数据
        config: 策略配置
        market_cap: 市值

    Returns:
        信号结果
    """
    generator = SignalGenerator(config)
    return generator.generate_signal(symbol, df, market_cap)


if __name__ == '__main__':
    # 测试信号生成
    print("=" * 60)
    print("信号生成器测试")
    print("=" * 60)

    # 创建测试数据 - 模拟符合条件的股票
    dates = pd.date_range('2024-01-01', periods=300, freq='D')
    np.random.seed(42)

    # 生成一个"低位放量突破"的模拟场景
    # 前200天：从15跌到8（低位）
    # 后100天：逐步放量反弹

    base_price = 8.0
    close = []
    volume = []

    for i in range(300):
        if i < 200:
            # 下跌阶段
            price = 15 - (i / 200) * 7 + np.random.randn() * 0.3
            vol = 500000 + np.random.rand() * 300000
        else:
            # 反弹阶段 - 逐步放量
            progress = (i - 200) / 100
            price = 8 + progress * 2 + np.random.randn() * 0.2
            vol = 800000 + progress * 1500000 + np.random.rand() * 500000

        close.append(max(1, price))
        volume.append(max(100000, vol))

    close = np.array(close)
    high = close + np.random.rand(300) * 0.3
    low = close - np.random.rand(300) * 0.3
    open_ = close + np.random.randn(300) * 0.1
    volume = np.array(volume)

    df = pd.DataFrame({
        'date': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    df.set_index('date', inplace=True)

    # 生成信号
    generator = SignalGenerator()
    result = generator.generate_signal('TEST.000001', df, market_cap=45.5)

    print(f"\n股票: {result.symbol}")
    print(f"信号: {result.signal_type.value}")
    print(f"得分: {result.score:.2f}")
    print(f"原因: {' + '.join(result.reasons)}")
    print(f"\n指标:")
    for key, value in result.indicators.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
