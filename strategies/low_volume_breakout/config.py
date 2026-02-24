# -*- coding: utf-8 -*-
"""
低位放量突破策略 - 参数配置模块

定义策略的所有可配置参数
"""
from dataclasses import dataclass
from typing import Tuple


@dataclass
class StrategyConfig:
    """
    策略参数配置类 - 机构级版本

    策略核心：寻找长期低位震荡（2年低位）的中小盘股票，在近期逐步放量时捕捉机会

    机构级优化：
    - 严格的市值范围（30-300亿）
    - 更严格的低位阈值（40%）
    - 更高的放量倍数（2倍）
    - 趋势过滤（MA20 > MA60）
    - 波动率压缩（20日振幅 < 30%）
    - 换手率过滤（> 1%）
    - 成交量连续放大验证

    Attributes:
        # 选股参数
        min_market_cap: 最小市值（亿元）
        max_market_cap: 最大市值（亿元）
        low_threshold: 低位阈值（当前价格/730日最高价，机构级建议40%）
        volume_ratio: 放量倍数（5日均量/20日均量，机构级建议2倍）

        # 数据参数
        data_period: 获取历史数据天数
        min_data_points: 最小数据点数（730天，确保能计算2年指标）

        # 技术指标参数
        ma_short: 短期均线周期
        ma_mid: 中期均线周期
        ma_long: 长期均线周期
        ma_trend: 趋势均线周期（MA730两年线）
        volume_ma_short: 短期均量周期
        volume_ma_mid: 中期均量周期
        volume_ma_long: 长期均量周期
        high_period: 730日最高价周期

        # 机构级过滤参数
        require_trend_filter: 是否启用趋势过滤（MA20 > MA60）
        min_turnover_rate: 最低换手率要求
        max_volatility_20d: 20日最大振幅（波动率压缩）
        require_volume_progressive: 是否要求成交量连续放大

        # 过滤参数
        min_listing_days: 剔除上市不足N天的次新股
        skip_st: 剔除ST股
        skip_suspended: 剔除停牌股

        # 并发参数
        max_workers: 并发处理线程数

        # 输出参数
        output_dir: 输出目录
        top_n: 输出Top N股票

        # 信号生成参数
        buy_threshold: 买入信号阈值（得分高于此值生成买入信号）

        # 安全检查参数
        rsi_overbought: RSI超买阈值
        rsi_period: RSI周期
        boll_period: BOLL周期
        boll_std: BOLL标准差倍数
        recent_return_threshold: 近期涨幅阈值（5日涨幅超过此值警告）
    """

    # ==================== 机构级选股参数 ====================
    min_market_cap: float = 30.0  # 最小市值（亿元）- 机构级优化
    max_market_cap: float = 300.0  # 最大市值（亿元）- 机构级优化
    low_threshold: float = 0.4  # 低位阈值：当前价格/730日最高价 - 机构级40%
    volume_ratio: float = 2.0  # 5日均量 > 20日均量 * N - 机构级2倍

    # 数据参数
    data_period: int = 1000  # 获取历史数据天数（增加缓冲区，确保有足够数据）
    min_data_points: int = 730  # 最小数据点数（用于计算730日指标）

    # 技术指标参数
    ma_short: int = 5  # MA5
    ma_mid: int = 20  # MA20
    ma_long: int = 60  # MA60
    ma_trend: int = 730  # MA730（两年线）
    volume_ma_short: int = 5  # 5日均量
    volume_ma_mid: int = 20  # 20日均量
    volume_ma_long: int = 60  # 60日均量
    high_period: int = 730  # 730日最高价周期（两年最高价）

    # ==================== 机构级过滤参数 ====================
    require_trend_filter: bool = True  # 趋势过滤：要求MA20 > MA60（避免下跌中继）
    min_turnover_rate: float = 0.01  # 最低换手率要求（1%）- 反映真实资金参与
    max_volatility_20d: float = 0.30  # 20日最大振幅（30%）- 波动率压缩
    require_volume_progressive: bool = True  # 成交量连续放大（VOL5>VOL20>VOL60）

    # 过滤参数
    min_listing_days: int = 365  # 剔除上市不足365天的次新股（约1年）
    skip_st: bool = True  # 剔除ST股
    skip_suspended: bool = True  # 剔除停牌股
    skip_chinext: bool = True  # 剔除创业板股票（300开头）

    # 并发参数
    max_workers: int = 8  # 并发处理线程数

    # 输出参数
    output_dir: str = "outputs/low_volume_breakout"  # 输出目录
    top_n: int = 50  # 输出Top N股票

    # 信号生成参数
    buy_threshold: float = 50.0  # 买入信号阈值（得分高于此值生成买入信号）

    # 安全检查参数
    rsi_overbought: float = 70.0  # RSI超买阈值
    rsi_period: int = 14  # RSI周期
    boll_period: int = 20  # BOLL周期
    boll_std: float = 2.0  # BOLL标准差倍数
    recent_return_threshold: float = 0.2  # 近期涨幅阈值（5日涨幅超过此值警告）

    def __post_init__(self):
        """配置参数后处理和验证"""
        # 验证市值范围
        if self.min_market_cap >= self.max_market_cap:
            raise ValueError(f"最小市值({self.min_market_cap})必须小于最大市值({self.max_market_cap})")

        # 验证低位阈值
        if not 0 < self.low_threshold < 1:
            raise ValueError(f"低位阈值({self.low_threshold})必须在0到1之间")

        # 验证放量倍数
        if self.volume_ratio <= 0:
            raise ValueError(f"放量倍数({self.volume_ratio})必须大于0")

        # 验证均线周期
        if not (self.ma_short < self.ma_mid < self.ma_long):
            raise ValueError("均线周期必须满足: short < mid < long")

    @classmethod
    def from_args(cls, **kwargs) -> 'StrategyConfig':
        """
        从命令行参数创建配置

        Args:
            **kwargs: 命令行参数

        Returns:
            StrategyConfig实例
        """
        return cls(
            min_market_cap=kwargs.get('min_cap', cls.min_market_cap),
            max_market_cap=kwargs.get('max_cap', cls.max_market_cap),
            low_threshold=kwargs.get('low_threshold', cls.low_threshold),
            volume_ratio=kwargs.get('volume_ratio', cls.volume_ratio),
            data_period=kwargs.get('data_period', cls.data_period),
            max_workers=kwargs.get('max_workers', cls.max_workers),
            top_n=kwargs.get('top_n', cls.top_n),
        )

    def get_display_params(self) -> dict:
        """
        获取用于显示的参数字典（机构级版本）

        Returns:
            格式化的参数字典
        """
        params = {
            '策略版本': '[机构级]',
            '市值范围': f'{self.min_market_cap}亿 - {self.max_market_cap}亿',
            '低位阈值': f'{self.low_threshold:.0%}',
            '放量倍数': f'{self.volume_ratio:.1f}x',
            '数据周期': f'{self.data_period}天',
            '均线周期': f'MA{self.ma_short}/MA{self.ma_mid}/MA{self.ma_long}',
            '均量周期': f'VOL{self.volume_ma_short}/VOL{self.volume_ma_mid}/VOL{self.volume_ma_long}',
            '最高价周期': f'{self.high_period}日',
            '趋势过滤': '[启用]' if self.require_trend_filter else '[关闭]',
            '换手率要求': f'>={self.min_turnover_rate:.1%}' if self.min_turnover_rate > 0 else '关闭',
            '波动率上限': f'<{self.max_volatility_20d:.0%}' if self.max_volatility_20d < 1 else '关闭',
            '量能递进': '[启用]' if self.require_volume_progressive else '[关闭]',
        }
        return params


# 默认配置实例
default_config = StrategyConfig()


if __name__ == '__main__':
    # 测试配置
    config = StrategyConfig()
    print("策略默认配置:")
    for key, value in config.get_display_params().items():
        print(f"  {key}: {value}")

    # 测试从参数创建
    print("\n从参数创建配置:")
    custom_config = StrategyConfig.from_args(
        min_cap=30,
        max_cap=150,
        low_threshold=0.55,
        volume_ratio=2.0
    )
    for key, value in custom_config.get_display_params().items():
        print(f"  {key}: {value}")
