# -*- coding: utf-8 -*-
"""
低位放量突破策略 - 技术指标计算模块

负责计算策略所需的各种技术指标
"""
import sys
import os
from typing import Optional, Dict
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 处理相对导入和绝对导入
try:
    from .config import StrategyConfig
except ImportError:
    from strategies.low_volume_breakout.config import StrategyConfig


class IndicatorCalculator:
    """技术指标计算器"""

    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        初始化指标计算器

        Args:
            config: 策略配置
        """
        self.config = config or StrategyConfig()

    def calculate_ma(self, df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
        """
        计算移动平均线

        Args:
            df: 包含close列的DataFrame
            periods: 均线周期列表，默认使用配置中的周期

        Returns:
            添加了MA列的DataFrame
        """
        if periods is None:
            periods = [self.config.ma_short, self.config.ma_mid, self.config.ma_long]

        for period in periods:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()

        return df

    def calculate_volume_ma(self, df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
        """
        计算成交量移动平均线

        Args:
            df: 包含volume列的DataFrame
            periods: 均量周期列表，默认使用配置中的周期

        Returns:
            添加了VOL_MA列的DataFrame
        """
        if periods is None:
            periods = [self.config.volume_ma_short, self.config.volume_ma_mid, self.config.volume_ma_long]

        for period in periods:
            df[f'volume_ma{period}'] = df['volume'].rolling(window=period).mean()

        return df

    def calculate_high_low(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算周期内最高价和最低价

        Args:
            df: 包含high和low列的DataFrame

        Returns:
            添加了最高价和最低价列的DataFrame
        """
        # 730日最高价（两年最高）
        df[f'high_{self.config.high_period}'] = df['high'].rolling(window=self.config.high_period).max()

        # 730日最低价（两年最低）
        df[f'low_{self.config.high_period}'] = df['low'].rolling(window=self.config.high_period).min()

        # 120日最高价和最低价（用于计算振幅）
        df['high_120'] = df['high'].rolling(window=120).max()
        df['low_120'] = df['low'].rolling(window=120).min()

        return df

    def calculate_rsi(self, df: pd.DataFrame, period: int = None) -> pd.DataFrame:
        """
        计算RSI指标

        Args:
            df: 包含close列的DataFrame
            period: RSI周期，默认使用配置中的周期

        Returns:
            添加了RSI列的DataFrame
        """
        if period is None:
            period = self.config.rsi_period

        # 计算价格变化
        delta = df['close'].diff()

        # 分离上涨和下跌
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # 计算RSI
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        return df

    def calculate_bollinger_bands(self, df: pd.DataFrame,
                                  period: int = None,
                                  std_num: float = None) -> pd.DataFrame:
        """
        计算布林带

        Args:
            df: 包含close列的DataFrame
            period: 周期，默认使用配置中的周期
            std_num: 标准差倍数，默认使用配置中的倍数

        Returns:
            添加了BOLL列的DataFrame
        """
        if period is None:
            period = self.config.boll_period
        if std_num is None:
            std_num = self.config.boll_std

        # 中轨
        df['boll_mid'] = df['close'].rolling(window=period).mean()

        # 标准差
        std = df['close'].rolling(window=period).std()

        # 上轨和下轨
        df['boll_upper'] = df['boll_mid'] + (std * std_num)
        df['boll_lower'] = df['boll_mid'] - (std * std_num)

        # 带宽（用于判断波动率）
        df['boll_width'] = (df['boll_upper'] - df['boll_lower']) / df['boll_mid']

        return df

    def calculate_strategy_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算策略特定指标

        Args:
            df: 包含OHLCV数据的DataFrame

        Returns:
            添加了策略指标的DataFrame

        策略指标包括：
        - 价格位置因子：当前价格 / 730日最高价
        - 放量因子：5日均量 / 20日均量
        - 均量趋势因子：20日均量 / 60日均量
        - 趋势因子：收盘价 / MA60
        - 120日振幅：(120日最高 - 120日最低) / 120日最低
        - 730日振幅：(730日最高 - 730日最低) / 730日最低
        """
        if df.empty or len(df) < self.config.high_period:
            return df

        # 计算基础指标
        df = self.calculate_ma(df)
        df = self.calculate_volume_ma(df)
        df = self.calculate_high_low(df)

        # 价格位置因子：当前价格 / 730日最高价（两年位置）
        df['price_position'] = df['close'] / df[f'high_{self.config.high_period}']

        # 放量因子：5日均量 / 20日均量
        df['volume_expansion'] = df[f'volume_ma{self.config.volume_ma_short}'] / df[f'volume_ma{self.config.volume_ma_mid}']

        # 均量趋势因子：20日均量 / 60日均量
        df['volume_trend'] = df[f'volume_ma{self.config.volume_ma_mid}'] / df[f'volume_ma{self.config.volume_ma_long}']

        # 趋势因子：收盘价 / MA60
        df['trend_strength'] = df['close'] / df[f'ma{self.config.ma_long}']

        # 120日振幅
        df['amplitude_120'] = (df['high_120'] - df['low_120']) / df['low_120']

        # 730日振幅（两年振幅）
        df['amplitude_730'] = (df[f'high_{self.config.high_period}'] - df[f'low_{self.config.high_period}']) / df[f'low_{self.config.high_period}']

        # 综合放量指标（满足放量条件时为True）
        df['is_volume_expanding'] = (
            (df['volume_expansion'] >= self.config.volume_ratio) &
            (df['volume_trend'] >= 1.0)
        )

        return df

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有技术指标

        Args:
            df: 包含OHLCV数据的DataFrame

        Returns:
            添加了所有指标的DataFrame
        """
        if df.empty or len(df) < self.config.min_data_points:
            return df

        # 计算策略指标
        df = self.calculate_strategy_indicators(df)

        # 计算安全指标
        df = self.calculate_rsi(df)
        df = self.calculate_bollinger_bands(df)

        # 计算MACD（用于辅助判断）
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp12 - exp26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        return df

    def get_latest_signals(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        获取最新的指标信号值

        Args:
            df: 包含所有指标的DataFrame

        Returns:
            包含最新指标值的字典
        """
        if df.empty:
            return {}

        latest = df.iloc[-1]

        signals = {
            'close': latest['close'],
            'price_position': latest.get('price_position', 0),
            'volume_expansion': latest.get('volume_expansion', 0),
            'volume_trend': latest.get('volume_trend', 0),
            'trend_strength': latest.get('trend_strength', 0),
            'amplitude_120': latest.get('amplitude_120', 0),
            'rsi': latest.get('rsi', 50),
            'boll_width': latest.get('boll_width', 0),
            'boll_position': self._calculate_boll_position(latest),
            'macd_hist': latest.get('macd_hist', 0),
        }

        return signals

    def _calculate_boll_position(self, latest: pd.Series) -> float:
        """
        计算布林带位置（价格在上轨和下轨之间的相对位置）

        Args:
            latest: 最新一行数据

        Returns:
            布林带位置 (0-1之间，0.5表示在中轨)
        """
        close = latest['close']
        boll_upper = latest.get('boll_upper', close)
        boll_lower = latest.get('boll_lower', close)

        # 如果上轨和下轨相等，返回中值0.5
        if boll_upper == boll_lower:
            return 0.5

        # 计算价格在布林带中的相对位置
        boll_position = (close - boll_lower) / (boll_upper - boll_lower)
        return boll_position


# 便捷函数
def calculate_indicators(df: pd.DataFrame,
                         config: Optional[StrategyConfig] = None) -> pd.DataFrame:
    """
    便捷函数：计算所有指标

    Args:
        df: OHLCV数据
        config: 策略配置

    Returns:
        添加了所有指标的DataFrame
    """
    calculator = IndicatorCalculator(config)
    return calculator.calculate_all_indicators(df)


if __name__ == '__main__':
    # 测试指标计算
    print("=" * 60)
    print("指标计算器测试")
    print("=" * 60)

    # 创建测试数据
    dates = pd.date_range('2024-01-01', periods=300, freq='D')
    np.random.seed(42)

    # 生成模拟价格数据
    close = 10 + np.cumsum(np.random.randn(300) * 0.1)
    high = close + np.random.rand(300) * 0.5
    low = close - np.random.rand(300) * 0.5
    open_ = close + np.random.randn(300) * 0.1
    volume = 1000000 + np.random.rand(300) * 500000

    df = pd.DataFrame({
        'date': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    df.set_index('date', inplace=True)

    # 计算指标
    calculator = IndicatorCalculator()
    df = calculator.calculate_all_indicators(df)

    print(f"\n数据行数: {len(df)}")
    print(f"\n指标列: {list(df.columns)}")

    print(f"\n最后5行数据:")
    print(df[['close', 'price_position', 'volume_expansion', 'trend_strength', 'rsi']].tail())

    # 获取最新信号
    signals = calculator.get_latest_signals(df)
    print(f"\n最新信号:")
    for key, value in signals.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
