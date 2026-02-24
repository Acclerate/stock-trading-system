# -*- coding: utf-8 -*-
"""
低位放量突破策略 - 股票池获取模块

负责获取全A股股票列表并进行初步筛选
"""
import sys
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

try:
    from gm.api import get_symbols, stk_get_daily_mktvalue_pt
    DIGGOLD_AVAILABLE = True
except ImportError:
    DIGGOLD_AVAILABLE = False
    print("警告: 掘金SDK未安装，股票池获取功能受限")

# 处理相对导入和绝对导入
try:
    from .config import StrategyConfig
except ImportError:
    from strategies.low_volume_breakout.config import StrategyConfig


class StockPoolManager:
    """股票池管理器"""

    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        初始化股票池管理器

        Args:
            config: 策略配置，默认使用default_config
        """
        self.config = config or StrategyConfig()
        self._stock_pool = []
        self._market_cap_data = {}
        self._stock_names = {}  # 股票名称映射

    def get_all_a_stocks(self, trade_date: Optional[str] = None) -> List[str]:
        """
        获取全A股股票列表（剔除ST、停牌、次新股）

        Args:
            trade_date: 交易日期字符串 'YYYY-MM-DD'，默认为当前日期

        Returns:
            股票代码列表（掘金格式：SHSE.600XXX, SZSE.000XXX）
        """
        if not DIGGOLD_AVAILABLE:
            raise RuntimeError("掘金SDK不可用，无法获取股票列表")

        if trade_date is None:
            trade_date = datetime.now().strftime('%Y-%m-%d')

        trade_date_ts = pd.Timestamp(trade_date)

        print(f"获取全A股股票列表（日期: {trade_date}）...")

        try:
            # 使用掘金SDK获取A股股票
            stocks_info = get_symbols(
                sec_type1=1010,  # 股票
                sec_type2=101001,  # A股
                skip_suspended=self.config.skip_suspended,
                skip_st=self.config.skip_st,
                trade_date=trade_date,
                df=True
            )

            if stocks_info.empty:
                print("未获取到股票列表")
                return []

            # 处理日期字段（处理时区信息）
            if 'listed_date' in stocks_info.columns:
                stocks_info['listed_date'] = stocks_info['listed_date'].apply(
                    lambda x: x.replace(tzinfo=None) if hasattr(x, 'tzinfo') and x.tzinfo is not None else x
                )
            if 'delisted_date' in stocks_info.columns:
                stocks_info['delisted_date'] = stocks_info['delisted_date'].apply(
                    lambda x: x.replace(tzinfo=None) if hasattr(x, 'tzinfo') and x.tzinfo is not None else x
                )

            # 剔除次新股和退市股
            cutoff_date = trade_date_ts - pd.Timedelta(days=self.config.min_listing_days)
            valid_stocks = stocks_info[
                (stocks_info['listed_date'] <= cutoff_date) &
                (stocks_info['delisted_date'] > trade_date_ts)
            ]

            # 剔除创业板股票（代码以300开头，如SZSE.300xxx）
            chinext_filtered = 0
            if self.config.skip_chinext:
                before_chinext_count = len(valid_stocks)
                valid_stocks = valid_stocks[~valid_stocks['symbol'].str.contains(r'SZSE\.30\d{3}')]
                chinext_filtered = before_chinext_count - len(valid_stocks)

            all_stocks = list(valid_stocks['symbol'])

            # 保存股票名称映射（使用symbol作为key，确保唯一性）
            if 'sec_name' in valid_stocks.columns:
                # 确保symbol列没有重复，避免映射错误
                valid_stocks = valid_stocks.drop_duplicates(subset=['symbol'], keep='first')
                self._stock_names = dict(zip(valid_stocks['symbol'], valid_stocks['sec_name']))
            else:
                self._stock_names = {}

            filter_desc = f"(剔除次新股<{self.config.min_listing_days}天, 停牌={self.config.skip_suspended}, ST={self.config.skip_st}"
            if self.config.skip_chinext:
                filter_desc += f", 创业板={chinext_filtered}"
            filter_desc += ")"

            print(f"可选股票池数量: {len(all_stocks)} {filter_desc}")

            self._stock_pool = all_stocks
            return all_stocks

        except Exception as e:
            print(f"获取股票列表失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_market_cap_batch(self, symbols: List[str], trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        批量获取股票市值数据

        Args:
            symbols: 股票代码列表
            trade_date: 交易日期 'YYYY-MM-DD'

        Returns:
            包含股票代码和市值的DataFrame
        """
        if not DIGGOLD_AVAILABLE:
            raise RuntimeError("掘金SDK不可用，无法获取市值数据")

        if trade_date is None:
            trade_date = datetime.now().strftime('%Y-%m-%d')

        try:
            mkt_data = stk_get_daily_mktvalue_pt(
                symbols=symbols,
                fields='tot_mv',  # 总市值
                trade_date=trade_date,
                df=True
            )

            if mkt_data.empty:
                print(f"未获取到市值数据")
                return pd.DataFrame(columns=['symbol', 'tot_mv'])

            # 重要：掘金SDK返回的市值单位是"元"，需要转换为"亿元"
            # 先保存原始值（元）
            mkt_data['tot_mv_original'] = mkt_data['tot_mv'].copy()
            # 转换为亿元
            mkt_data['tot_mv'] = mkt_data['tot_mv'] / 1e8  # 元 -> 亿元

            # 调试：打印市值数据范围
            print(f"市值数据样本: {len(mkt_data)} 只股票")
            mv_values = mkt_data['tot_mv'].dropna()
            if len(mv_values) > 0:
                print(f"  市值范围: {mv_values.min():.2f} - {mv_values.max():.2f} 亿元")
                print(f"  市值中位数: {mv_values.median():.2f} 亿元")
            else:
                print(f"  市值数据全部为空")

            # 过滤市值范围（现在tot_mv已经是亿元单位）
            filtered = mkt_data[
                (mkt_data['tot_mv'] >= self.config.min_market_cap) &
                (mkt_data['tot_mv'] <= self.config.max_market_cap)
            ].copy()  # 使用copy避免SettingWithCopyWarning

            print(f"市值筛选: {len(mkt_data)} -> {len(filtered)} "
                  f"({self.config.min_market_cap}亿-{self.config.max_market_cap}亿)")

            # 返回filtered中的symbol和tot_mv（亿元单位）
            return filtered[['symbol', 'tot_mv']]

        except Exception as e:
            print(f"获取市值数据失败: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame(columns=['symbol', 'tot_mv'])

    def filter_by_market_cap(self, stock_pool: List[str], trade_date: Optional[str] = None) -> List[str]:
        """
        按市值范围筛选股票池

        Args:
            stock_pool: 股票代码列表
            trade_date: 交易日期

        Returns:
            筛选后的股票代码列表
        """
        mkt_data = self.get_market_cap_batch(stock_pool, trade_date)

        if mkt_data.empty:
            return []

        # 返回符合市值范围的股票列表
        filtered_symbols = mkt_data['symbol'].tolist()

        # 统计市值分布
        print(f"\n市值分布统计:")
        print(f"  最小市值: {mkt_data['tot_mv'].min():.2f}亿")
        print(f"  最大市值: {mkt_data['tot_mv'].max():.2f}亿")
        print(f"  平均市值: {mkt_data['tot_mv'].mean():.2f}亿")
        print(f"  中位数: {mkt_data['tot_mv'].median():.2f}亿")

        # 保存市值数据供后续使用
        self._market_cap_data = dict(zip(mkt_data['symbol'], mkt_data['tot_mv']))

        return filtered_symbols

    def get_stock_pool(self, trade_date: Optional[str] = None) -> List[str]:
        """
        获取完整的股票池（全A股 + 市值筛选）

        Args:
            trade_date: 交易日期

        Returns:
            筛选后的股票代码列表
        """
        # 1. 获取全A股（剔除ST、停牌、次新股）
        all_stocks = self.get_all_a_stocks(trade_date)

        if not all_stocks:
            return []

        # 2. 按市值筛选
        filtered_stocks = self.filter_by_market_cap(all_stocks, trade_date)

        print(f"\n最终股票池: {len(filtered_stocks)} 只")

        return filtered_stocks

    def get_market_cap(self, symbol: str) -> Optional[float]:
        """
        获取单个股票的市值

        Args:
            symbol: 股票代码

        Returns:
            市值（亿元），如果不存在返回None
        """
        return self._market_cap_data.get(symbol)

    def get_stock_name(self, symbol: str) -> str:
        """
        获取股票名称

        Args:
            symbol: 股票代码

        Returns:
            股票名称，如果不存在返回空字符串
        """
        # 先从缓存中查找
        name = self._stock_names.get(symbol, "")

        # 如果缓存中没有，尝试从掘金SDK实时获取
        if not name and DIGGOLD_AVAILABLE:
            try:
                info = get_symbols(
                    sec_type1=1010,
                    sec_type2=101001,
                    df=True
                )
                if not info.empty:
                    # 查找匹配的股票
                    stock_info = info[info['symbol'] == symbol]
                    if not stock_info.empty:
                        name = stock_info.iloc[0]['sec_name']
                        # 更新缓存
                        self._stock_names[symbol] = name
            except Exception as e:
                pass  # 静默失败，返回空字符串

        return name

    def get_stock_info_batch(self, symbols: List[str]) -> pd.DataFrame:
        """
        批量获取股票基本信息

        Args:
            symbols: 股票代码列表

        Returns:
            包含股票信息的DataFrame
        """
        if not DIGGOLD_AVAILABLE:
            return pd.DataFrame()

        try:
            info = get_symbols(
                sec_type1=1010,
                sec_type2=101001,
                df=True
            )

            if info.empty:
                return pd.DataFrame()

            # 筛选目标股票
            filtered = info[info['symbol'].isin(symbols)]

            return filtered[['symbol', 'sec_name', 'listed_date']]

        except Exception as e:
            print(f"获取股票信息失败: {e}")
            return pd.DataFrame()


# 便捷函数
def get_stock_pool(config: Optional[StrategyConfig] = None,
                   trade_date: Optional[str] = None) -> List[str]:
    """
    便捷函数：获取股票池

    Args:
        config: 策略配置
        trade_date: 交易日期

    Returns:
        股票代码列表
    """
    manager = StockPoolManager(config)
    return manager.get_stock_pool(trade_date)


if __name__ == '__main__':
    # 测试股票池获取
    print("=" * 60)
    print("股票池管理器测试")
    print("=" * 60)

    config = StrategyConfig()
    manager = StockPoolManager(config)

    # 获取股票池
    trade_date = datetime.now().strftime('%Y-%m-%d')
    stock_pool = manager.get_stock_pool(trade_date)

    print(f"\n最终股票池数量: {len(stock_pool)}")

    if stock_pool:
        print(f"\n前10只股票: {stock_pool[:10]}")
