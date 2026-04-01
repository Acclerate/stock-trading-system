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
from collections import OrderedDict

import pandas as pd
import numpy as np
from collections import defaultdict

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
    """信号生成器（分级评分制）"""

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        self.indicator_calc = IndicatorCalculator(config)
        # 过滤条件统计（用于诊断）
        self._condition_stats = defaultdict(lambda: {'passed': 0, 'failed': 0})
        self._total_evaluated = 0

    def evaluate_conditions(self, df: pd.DataFrame) -> Tuple[float, List[str], List[str]]:
        """
        分级评分制评估所有条件

        每个条件独立评分，不再硬性过滤。只有总得分决定信号类型。

        评分分布（总分100）:
        - 价格位置: 0-30分
        - 成交量放大: 0-20分
        - 均量趋势: 0-10分
        - 量能递进: 0-10分
        - 趋势过滤(MA20>MA60): 0-10分
        - 趋势启动(close>MA60): 0-10分
        - 波动率: 0-5分
        - 市值偏好: 0-5分（由调用方添加）

        Args:
            df: 包含指标的DataFrame

        Returns:
            (总得分, 通过原因列表, 失败原因列表)
        """
        if df.empty or len(df) < 60:
            return 0, [], ["数据不足(需至少60天)"]

        latest = df.iloc[-1]
        score = 0.0
        passed_reasons = []
        failed_reasons = []
        self._total_evaluated += 1

        # ===== 1. 价格位置 (0-30分) =====
        price_position = latest.get('price_position', 0)
        if price_position > 0:
            if price_position < self.config.low_threshold:
                # 低于阈值：得分与低位程度成正比
                s = 30 * (1 - price_position / self.config.low_threshold)
                score += s
                passed_reasons.append(f"低位({price_position:.1%})")
                self._condition_stats['price_position']['passed'] += 1
            else:
                # 高于阈值：部分得分（越高扣越多）
                excess = (price_position - self.config.low_threshold) / max(0.01, 1 - self.config.low_threshold)
                s = max(0, 10 * (1 - excess))
                score += s
                failed_reasons.append(f"价格偏高({price_position:.1%}>={self.config.low_threshold:.0%})")
                self._condition_stats['price_position']['failed'] += 1
        else:
            failed_reasons.append("价位指标缺失")
            self._condition_stats['price_position']['failed'] += 1

        # ===== 2. 成交量放大 (0-20分) =====
        volume_expansion = latest.get('volume_expansion', 0)
        if volume_expansion > 0:
            s = 20 * min(1.5, max(0, volume_expansion / self.config.volume_ratio))
            score += s
            if volume_expansion >= self.config.volume_ratio:
                passed_reasons.append(f"放量({volume_expansion:.1f}x)")
                self._condition_stats['volume_expansion']['passed'] += 1
            else:
                failed_reasons.append(f"放量不足({volume_expansion:.2f}x<{self.config.volume_ratio:.1f}x)")
                self._condition_stats['volume_expansion']['failed'] += 1
        else:
            failed_reasons.append("放量指标缺失")
            self._condition_stats['volume_expansion']['failed'] += 1

        # ===== 3. 均量趋势 (0-10分) =====
        volume_trend = latest.get('volume_trend', 0)
        if volume_trend > 0:
            s = 10 * min(1.0, volume_trend)
            score += s
            if volume_trend >= 1.0:
                passed_reasons.append("均量上升")
                self._condition_stats['volume_trend']['passed'] += 1
            else:
                failed_reasons.append(f"均量下降({volume_trend:.2f})")
                self._condition_stats['volume_trend']['failed'] += 1
        else:
            failed_reasons.append("均量趋势缺失")
            self._condition_stats['volume_trend']['failed'] += 1

        # ===== 4. 量能递进 VOL5>VOL20>VOL60 (0-10分) =====
        vol5 = latest.get(f'volume_ma{self.config.volume_ma_short}', 0)
        vol20 = latest.get(f'volume_ma{self.config.volume_ma_mid}', 0)
        vol60 = latest.get(f'volume_ma{self.config.volume_ma_long}', 0)
        if vol5 > 0 and vol20 > 0 and vol60 > 0:
            if vol5 > vol20 > vol60:
                score += 10
                passed_reasons.append("量能递进")
                self._condition_stats['volume_progressive']['passed'] += 1
            elif vol5 > vol20:
                score += 5  # 部分递进给一半分
                failed_reasons.append("量能部分递进(VOL5>VOL20但VOL20<=VOL60)")
                self._condition_stats['volume_progressive']['failed'] += 1
            else:
                failed_reasons.append("量能未递进")
                self._condition_stats['volume_progressive']['failed'] += 1
        else:
            self._condition_stats['volume_progressive']['failed'] += 1

        # ===== 5. 趋势过滤 MA20>MA60 (0-10分) =====
        ma20 = latest.get(f'ma{self.config.ma_mid}', 0)
        ma60 = latest.get(f'ma{self.config.ma_long}', 0)
        if ma20 > 0 and ma60 > 0:
            if ma20 > ma60:
                score += 10
                passed_reasons.append("趋势向上(MA20>MA60)")
                self._condition_stats['trend_filter']['passed'] += 1
            else:
                # 接近金叉也给部分分
                ratio = ma20 / ma60
                s = max(0, 5 * (ratio - 0.95) / 0.05)
                score += s
                failed_reasons.append(f"MA20<=MA60({ma20:.2f}/{ma60:.2f})")
                self._condition_stats['trend_filter']['failed'] += 1
        else:
            self._condition_stats['trend_filter']['failed'] += 1

        # ===== 6. 趋势启动 close>MA60 (0-10分) =====
        trend_strength = latest.get('trend_strength', 0)
        if trend_strength > 0:
            if trend_strength > 1.0:
                s = min(10, 10 * (trend_strength - 0.8) / 0.4)
                score += s
                passed_reasons.append(f"趋势启动({trend_strength:.1%})")
                self._condition_stats['trend_start']['passed'] += 1
            else:
                s = max(0, 5 * (trend_strength - 0.9) / 0.1)
                score += s
                failed_reasons.append("趋势未启动(收盘<MA60)")
                self._condition_stats['trend_start']['failed'] += 1
        else:
            self._condition_stats['trend_start']['failed'] += 1

        # ===== 7. 波动率 (0-5分) =====
        if self.config.max_volatility_20d < 1.0 and len(df) >= 20:
            vol_20d = self._calculate_volatility_20d(df)
            if vol_20d <= self.config.max_volatility_20d:
                score += 5
                passed_reasons.append(f"波动压缩({vol_20d:.1%})")
                self._condition_stats['volatility']['passed'] += 1
            else:
                # 略超也给部分分
                s = max(0, 3 * (1 - (vol_20d - self.config.max_volatility_20d) / self.config.max_volatility_20d))
                score += s
                failed_reasons.append(f"波动偏高({vol_20d:.1%})")
                self._condition_stats['volatility']['failed'] += 1

        return score, passed_reasons, failed_reasons

    def get_filter_stats(self) -> Dict:
        """获取过滤条件统计（用于诊断）"""
        stats = dict(self._condition_stats)
        # 按失败数排序，找出最严格的条件
        sorted_stats = sorted(stats.items(), key=lambda x: x[1]['failed'], reverse=True)
        return {
            'total_evaluated': self._total_evaluated,
            'conditions': OrderedDict(sorted_stats)
        }

    def format_filter_stats(self) -> str:
        """格式化过滤统计为可读文本"""
        stats = self.get_filter_stats()
        if stats['total_evaluated'] == 0:
            return "暂无统计数据"

        name_map = {
            'price_position': '价格位置',
            'volume_expansion': '成交量放大',
            'volume_trend': '均量趋势',
            'volume_progressive': '量能递进',
            'trend_filter': '趋势过滤(MA20>MA60)',
            'trend_start': '趋势启动(close>MA60)',
            'volatility': '波动率',
        }

        lines = [f"{'条件':<25} {'通过':>8} {'未通过':>8} {'通过率':>8}"]
        lines.append("-" * 55)
        for key, val in stats['conditions'].items():
            name = name_map.get(key, key)
            p, f = val['passed'], val['failed']
            total = p + f
            rate = f"{p/total*100:.1f}%" if total > 0 else "N/A"
            lines.append(f"{name:<25} {p:>8} {f:>8} {rate:>8}")

        lines.append(f"\n共评估 {stats['total_evaluated']} 只股票")
        return "\n".join(lines)

    def _calculate_volatility_20d(self, df: pd.DataFrame) -> float:
        """计算20日振幅"""
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
        检查安全条件（用于标记高风险信号，不作为硬过滤）

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

        # 检查布林带位置
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

    def generate_signal(self, symbol: str, df: pd.DataFrame,
                       market_cap: Optional[float] = None) -> SignalResult:
        """
        生成交易信号（分级评分制）

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

        # 分级评分评估（不再硬过滤）
        score, passed_reasons, failed_reasons = self.evaluate_conditions(df)

        # 市值偏好加分 (0-5分)
        if market_cap is not None:
            if market_cap < 50:
                score += 5
            elif market_cap < 100:
                score += 3

        score = min(100, score)

        # 检查安全条件（仅标记警告）
        is_safe, warnings = self.check_safety_conditions(df)

        # 生成信号
        signal_type = SignalType.BUY if score >= self.config.buy_threshold else SignalType.WAIT

        # 组合原因：BUY显示通过的项，WAIT显示失败项
        if signal_type == SignalType.BUY:
            reasons = passed_reasons
            if warnings:
                reasons.extend([f"[警告]{w}" for w in warnings])
        else:
            reasons = failed_reasons

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
