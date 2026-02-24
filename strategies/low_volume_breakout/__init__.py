# -*- coding: utf-8 -*-
"""
低位放量突破策略 (Low Volume Breakout Strategy)

策略思路：
寻找长期低位震荡的中小盘股票，在近期逐步放量时捕捉潜在机会

核心逻辑：
1. 中小市值：20亿-200亿元
2. 长期低位震荡：当前价格 < 250日最高价的60%
3. 近期逐步放量：5日均量 > 20日均量 * 1.5，且20日均量 > 60日均量
4. 趋势转强：收盘价 > MA60

使用方法：
    from strategies.low_volume_breakout import LowVolumeBreakoutStrategy

    strategy = LowVolumeBreakoutStrategy()
    results = strategy.run()
"""

from .config import StrategyConfig
from .stock_pool import StockPoolManager
from .indicators import IndicatorCalculator
from .signals import SignalGenerator
from .main import main

__version__ = '1.0.0'
__all__ = [
    'StrategyConfig',
    'StockPoolManager',
    'IndicatorCalculator',
    'SignalGenerator',
    'main'
]
