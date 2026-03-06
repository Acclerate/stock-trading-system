"""
数据采集器
获取历史价格数据和基准指数数据
支持多种数据源：缓存、数据库(DataResilient)、stock_tracker.db
"""
import sys
import os
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data.data_resilient import DataResilient
from strategy_tracker.config import BENCHMARK_INDEX, DATE_FORMAT_COMPACT
from strategy_tracker.db import get_repository


# ========== 工具函数 ==========
def normalize_symbol(symbol: str) -> str:
    """
    标准化股票代码格式
    SHSE.600519 -> 600519
    SZSE.000001 -> 000001
    600519 -> 600519
    """
    if '.' in str(symbol):
        return symbol.split('.')[-1]
    return symbol


def load_stock_from_cache(stock_code: str) -> Optional[pd.DataFrame]:
    """
    从缓存加载股票数据
    参考 trend_stocks.py 的实现方式

    Args:
        stock_code: 股票代码

    Returns:
        缓存的DataFrame，如果不存在或加载失败返回None
    """
    cache_dir = Path("cache/stock")

    # 确保缓存目录存在
    if not cache_dir.exists():
        return None

    # 标准化代码（纯数字，用于缓存文件匹配）
    code = normalize_symbol(stock_code)

    # 查找该股票的所有缓存文件
    stock_files = []

    for cache_file in cache_dir.glob(f"{code}_*.pkl"):
        try:
            parts = cache_file.stem.split('_')
            if len(parts) >= 3:
                start_date = parts[1]
                end_date = parts[2]
                stock_files.append((cache_file, start_date, end_date))
        except Exception:
            continue

    if not stock_files:
        return None

    # 按修改时间排序，取最新的
    stock_files.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)
    latest_file, start_date, end_date = stock_files[0]

    try:
        with open(latest_file, 'rb') as f:
            df = pickle.load(f)
        return df
    except Exception:
        return None


class DataCollector:
    """数据采集器 - 获取股票历史价格和基准数据"""

    def __init__(self):
        self.data_resilient = DataResilient()

    def get_stock_price(
        self,
        stock_code: str,
        check_date: datetime,
        screen_date: datetime,
        use_cache: bool = True
    ) -> Optional[float]:
        """
        获取股票在指定日期的收盘价
        优先从缓存读取，缓存不存在时使用 DataResilient

        Args:
            stock_code: 股票代码（6位数字）
            check_date: 检查日期
            screen_date: 筛选日期
            use_cache: 是否使用缓存

        Returns:
            收盘价，如果获取失败返回None
        """
        try:
            # 1. 先尝试从缓存读取（避免网络请求失败）
            if use_cache:
                df = load_stock_from_cache(stock_code)
                if df is not None and not df.empty:
                    # 标准化数据格式
                    df = self._standardize_dataframe(df)
                    # 筛选日期范围
                    start_date = screen_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = check_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    df_filtered = df[(df.index >= start_date) & (df.index <= end_date)]
                    if not df_filtered.empty:
                        close_price = df_filtered.iloc[-1]['close']
                        return float(close_price)

            # 2. 缓存不存在或未启用缓存，使用 DataResilient
            start_date = screen_date.strftime(DATE_FORMAT_COMPACT)
            end_date = check_date.strftime(DATE_FORMAT_COMPACT)

            df = self.data_resilient.fetch_stock_data(
                stock_code, start_date, end_date, use_cache=use_cache
            )

            if df is None or df.empty:
                return None

            # 获取最后一日的收盘价
            close_price = df.iloc[-1]['close']
            return float(close_price)

        except Exception as e:
            print(f"获取 {stock_code} 价格失败: {e}")
            return None

    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化DataFrame格式
        确保有正确的索引和列名
        处理时区问题：将timezone-aware的索引转换为naive datetime
        """
        if df is None or df.empty:
            return df

        # 确保索引是datetime类型
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            elif 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
            else:
                # 尝试将当前索引转换为datetime
                try:
                    df.index = pd.to_datetime(df.index)
                except Exception:
                    pass

        # 处理时区：如果有timezone，转换为naive datetime（去掉时区信息）
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            df.index = df.index.tz_convert(None)  # 转换为naive datetime

        # 标准化列名（小写）
        df.columns = [col.lower() for col in df.columns]

        return df

    def get_stock_prices_range(
        self,
        stock_code: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        获取股票在日期范围内的价格数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            use_cache: 是否使用缓存

        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            start = start_date.strftime(DATE_FORMAT_COMPACT)
            end = end_date.strftime(DATE_FORMAT_COMPACT)

            df = self.data_resilient.fetch_stock_data(
                stock_code, start, end, use_cache=use_cache
            )

            return df

        except Exception as e:
            print(f"获取 {stock_code} 历史数据失败: {e}")
            return None

    def get_benchmark_data(
        self,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        获取沪深300基准指数数据
        仅从缓存读取（避免网络请求失败）

        Args:
            start_date: 开始日期
            end_date: 结束日期
            use_cache: 是否使用缓存

        Returns:
            包含指数数据的DataFrame
        """
        # 仅从缓存读取
        if use_cache:
            df = load_stock_from_cache(BENCHMARK_INDEX)
            if df is not None and not df.empty:
                # 标准化并筛选日期范围
                df = self._standardize_dataframe(df)
                start_norm = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_norm = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                df_filtered = df[(df.index >= start_norm) & (df.index <= end_norm)]
                if not df_filtered.empty:
                    return df_filtered

        # 缓存不存在，返回空DataFrame
        return pd.DataFrame()

    def calculate_benchmark_return(
        self,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True,
        silent: bool = True
    ) -> Optional[float]:
        """
        计算基准收益率
        如果缓存不可用，静默返回None

        Args:
            start_date: 开始日期
            end_date: 结束日期
            use_cache: 是否使用缓存
            silent: 是否静默（不打印错误信息）

        Returns:
            基准收益率（%）
        """
        try:
            # 1. 先尝试从缓存读取基准数据
            if use_cache:
                df = load_stock_from_cache(BENCHMARK_INDEX)
                if df is not None and not df.empty:
                    df = self._standardize_dataframe(df)
                    start_norm = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_norm = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    df_filtered = df[(df.index >= start_norm) & (df.index <= end_norm)]
                    if not df_filtered.empty and len(df_filtered) >= 2:
                        start_price = df_filtered.iloc[0]['close']
                        end_price = df_filtered.iloc[-1]['close']
                        if start_price and end_price and start_price > 0:
                            return ((end_price - start_price) / start_price) * 100

            # 2. 缓存不存在，返回None（不再尝试网络请求）
            if not silent:
                print("基准数据缓存不可用，跳过基准收益率计算")
            return None

        except Exception as e:
            if not silent:
                print(f"计算基准收益率失败: {e}")
            return None

    def is_trading_day(self, date: datetime) -> bool:
        """
        判断是否为交易日
        优先从缓存读取基准数据

        Args:
            date: 待检查的日期

        Returns:
            是否为交易日
        """
        try:
            # 1. 先尝试从缓存读取
            df = load_stock_from_cache(BENCHMARK_INDEX)
            if df is not None and not df.empty:
                df = self._standardize_dataframe(df)
                target_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
                # 对于pandas DatetimeIndex，使用 normalize()
                if hasattr(df.index, 'normalize'):
                    df_date = df.index.normalize()
                else:
                    df_date = df.index
                return target_date in df_date

            # 2. 缓存不存在，使用 DataResilient
            start = (date - timedelta(days=3)).strftime(DATE_FORMAT_COMPACT)
            end = (date + timedelta(days=1)).strftime(DATE_FORMAT_COMPACT)

            df = self.data_resilient.fetch_stock_data(
                BENCHMARK_INDEX, start, end, use_cache=True
            )

            if df is None or df.empty:
                return False

            # 检查目标日期是否在数据中
            if hasattr(df.index, 'normalize'):
                df_date = df.index.normalize()
            else:
                df_date = df.index
            target_date = date.replace(hour=0, minute=0, second=0, microsecond=0)

            return target_date in df_date

        except Exception:
            return False

    def get_next_trading_day(self, date: datetime, max_days: int = 10) -> Optional[datetime]:
        """
        获取下一个交易日

        Args:
            date: 起始日期
            max_days: 最大查找天数

        Returns:
            下一个交易日的日期
        """
        for i in range(1, max_days + 1):
            next_date = date + timedelta(days=i)
            if self.is_trading_day(next_date):
                return next_date
        return None

    def get_nth_trading_day(
        self,
        start_date: datetime,
        n: int,
        max_days: int = 30
    ) -> Optional[datetime]:
        """
        获取第n个交易日

        Args:
            start_date: 起始日期
            n: 第n个交易日
            max_days: 最大查找天数

        Returns:
            第n个交易日的日期
        """
        trading_days_found = 0
        current_date = start_date

        for i in range(1, max_days + 1):
            current_date = start_date + timedelta(days=i)
            if self.is_trading_day(current_date):
                trading_days_found += 1
                if trading_days_found == n:
                    return current_date

        return None

    def bulk_collect_prices(
        self,
        stock_codes: List[str],
        screen_date: datetime,
        check_date: datetime,
        use_cache: bool = True
    ) -> Dict[str, Optional[float]]:
        """
        批量获取股票价格

        Args:
            stock_codes: 股票代码列表
            screen_date: 筛选日期
            check_date: 检查日期
            use_cache: 是否使用缓存

        Returns:
            股票代码到价格的映射字典
        """
        prices = {}

        for code in stock_codes:
            price = self.get_stock_price(code, check_date, screen_date, use_cache)
            prices[code] = price

        return prices


class BenchmarkCollector:
    """基准数据采集器 - 专门用于采集和存储基准指数数据"""

    def __init__(self, repository):
        """
        初始化基准数据采集器

        Args:
            repository: 数据库仓库实例
        """
        self.repository = repository
        self.data_collector = DataCollector()

    def collect_and_store(
        self,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> int:
        """
        采集并存储基准数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            use_cache: 是否使用缓存

        Returns:
            存储的记录数
        """
        df = self.data_collector.get_benchmark_data(start_date, end_date, use_cache)

        if df is None or df.empty:
            print(f"未获取到基准数据: {start_date} ~ {end_date}")
            return 0

        records = []
        for date, row in df.iterrows():
            # 计算日收益率
            daily_return = None
            if hasattr(df.index, 'get_loc'):
                idx = df.index.get_loc(date)
                if idx > 0:
                    prev_close = df.iloc[idx - 1]['close']
                    if prev_close and prev_close > 0:
                        daily_return = ((row['close'] - prev_close) / prev_close) * 100

            record = {
                'trade_date': date,
                'open_price': float(row['open']) if pd.notna(row['open']) else None,
                'close_price': float(row['close']) if pd.notna(row['close']) else None,
                'high_price': float(row['high']) if pd.notna(row['high']) else None,
                'low_price': float(row['low']) if pd.notna(row['low']) else None,
                'volume': float(row['volume']) if pd.notna(row['volume']) else None,
                'daily_return': daily_return
            }
            records.append(record)

        # 批量存储
        count = self.repository.bulk_create_benchmark_data(records)
        print(f"存储基准数据: {count} 条记录")
        return count

    def update_recent_benchmark(self, days: int = 30) -> int:
        """
        更新最近的基准数据

        Args:
            days: 更新最近多少天的数据

        Returns:
            存储的记录数
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 获取数据库中最新日期
        latest = self.repository.get_benchmark_data(
            start_date=start_date,
            end_date=end_date
        )

        if latest:
            latest_date = max([d.trade_date for d in latest])
            start_date = latest_date + timedelta(days=1)

        if start_date >= end_date:
            print("基准数据已是最新")
            return 0

        return self.collect_and_store(start_date, end_date)


class DbDataSource:
    """
    数据库数据源 - 从 stock_tracker.db 直接读取历史数据
    作为独立的数据获取方式，优先级可配置
    """

    def __init__(self, repository=None):
        """
        初始化数据库数据源

        Args:
            repository: 数据库仓库实例，如果为None则自动获取
        """
        self.repository = repository or get_repository()

    def get_stock_price_from_db(
        self,
        stock_code: str,
        check_date: datetime,
        holding_days: int
    ) -> Optional[float]:
        """
        从数据库获取股票在指定持仓天数后的收盘价
        读取 return_records 表中已计算的历史价格

        Args:
            stock_code: 股票代码
            check_date: 检查日期（筛选日期 + holding_days）
            holding_days: 持仓天数

        Returns:
            收盘价，如果未找到返回None
        """
        try:
            from sqlalchemy import and_

            with self.repository.get_session() as session:
                # 通过股票代码和检查日期查找收益记录
                result = session.query(
                    ReturnRecord, StockPosition, ScreeningRecord
                ).join(
                    StockPosition, ReturnRecord.position_id == StockPosition.id
                ).join(
                    ScreeningRecord, StockPosition.screening_id == ScreeningRecord.id
                ).filter(
                    and_(
                        StockPosition.stock_code == stock_code,
                        ReturnRecord.holding_days == holding_days,
                        _date_filter(ReturnRecord.check_date, check_date)
                    )
                ).first()

                if result and result[0].close_price:
                    return float(result[0].close_price)

            return None

        except Exception as e:
            print(f"从数据库获取 {stock_code} 价格失败: {e}")
            return None

    def get_stock_prices_history_from_db(
        self,
        stock_code: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[Dict[int, float]]:
        """
        从数据库获取股票的历史价格数据（按持仓天数）

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            字典 {holding_days: close_price}，如果未找到返回None
        """
        try:
            from sqlalchemy import and_

            with self.repository.get_session() as session:
                results = session.query(
                    ReturnRecord, StockPosition
                ).join(
                    StockPosition, ReturnRecord.position_id == StockPosition.id
                ).filter(
                    and_(
                        StockPosition.stock_code == stock_code,
                        ReturnRecord.check_date >= start_date,
                        ReturnRecord.check_date <= end_date,
                        ReturnRecord.close_price.isnot(None)
                    )
                ).all()

                if results:
                    return {r[0].holding_days: float(r[0].close_price) for r in results}

            return None

        except Exception as e:
            print(f"从数据库获取 {stock_code} 历史价格失败: {e}")
            return None

    def get_benchmark_price_from_db(self, trade_date: datetime) -> Optional[float]:
        """
        从数据库获取基准指数在指定日期的收盘价

        Args:
            trade_date: 交易日期

        Returns:
            收盘价，如果未找到返回None
        """
        try:
            data = self.repository.get_benchmark_by_date(trade_date)
            if data and data.close_price:
                return float(data.close_price)
            return None

        except Exception as e:
            print(f"从数据库获取基准价格失败: {e}")
            return None

    def get_benchmark_prices_range_from_db(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        从数据库获取基准指数在日期范围内的数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            data_list = self.repository.get_benchmark_data(start_date, end_date)

            if not data_list:
                return None

            # 转换为DataFrame
            data = {
                'open': [d.open_price for d in data_list],
                'close': [d.close_price for d in data_list],
                'high': [d.high_price for d in data_list],
                'low': [d.low_price for d in data_list],
                'volume': [d.volume for d in data_list],
            }
            df = pd.DataFrame(data, index=[d.trade_date for d in data_list])
            df.index.name = 'date'

            return df

        except Exception as e:
            print(f"从数据库获取基准历史数据失败: {e}")
            return None

    def calculate_benchmark_return_from_db(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[float]:
        """
        从数据库计算基准收益率

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            基准收益率（%），如果计算失败返回None
        """
        return self.repository.calculate_benchmark_return(start_date, end_date)

    def is_trading_day_from_db(self, date: datetime) -> bool:
        """
        从数据库判断是否为交易日

        Args:
            date: 待检查的日期

        Returns:
            是否为交易日
        """
        try:
            data = self.repository.get_benchmark_by_date(date)
            return data is not None

        except Exception:
            return False

    def get_available_stock_codes(self) -> List[str]:
        """
        获取数据库中所有有记录的股票代码（已去重）

        Returns:
            股票代码列表（去重后）
        """
        try:
            from sqlalchemy import distinct

            with self.repository.get_session() as session:
                codes = session.query(distinct(StockPosition.stock_code)).all()
                return sorted([c[0] for c in codes])

        except Exception:
            return []

    def get_stock_codes_by_strategy(
        self,
        strategy_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[str]:
        """
        按策略类型获取股票代码（已去重）

        Args:
            strategy_type: 策略类型
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            股票代码列表（去重后）
        """
        try:
            from sqlalchemy import distinct, and_

            with self.repository.get_session() as session:
                query = session.query(
                    distinct(StockPosition.stock_code)
                ).join(
                    ScreeningRecord, StockPosition.screening_id == ScreeningRecord.id
                ).filter(
                    ScreeningRecord.strategy_type == strategy_type
                )

                if start_date:
                    query = query.filter(ScreeningRecord.screen_date >= start_date)
                if end_date:
                    query = query.filter(ScreeningRecord.screen_date <= end_date)

                codes = query.all()
                return sorted([c[0] for c in codes])

        except Exception as e:
            print(f"获取策略 {strategy_type} 股票代码失败: {e}")
            return []

    def get_stock_codes_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """
        按日期范围获取股票代码（已去重）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            股票代码列表（去重后）
        """
        try:
            from sqlalchemy import distinct

            with self.repository.get_session() as session:
                codes = session.query(
                    distinct(StockPosition.stock_code)
                ).filter(
                    StockPosition.screen_date >= start_date,
                    StockPosition.screen_date <= end_date
                ).all()
                return sorted([c[0] for c in codes])

        except Exception as e:
            print(f"获取日期范围股票代码失败: {e}")
            return []

    def get_latest_screening_stocks(
        self,
        strategy_type: Optional[str] = None,
        limit_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        获取最新的筛选股票列表（去重）

        Args:
            strategy_type: 策略类型（为空则获取所有策略）
            limit_days: 限制最近多少天的筛选记录

        Returns:
            股票信息列表 [{stock_code, stock_name, latest_screen_date, count}, ...]
        """
        try:
            from sqlalchemy import and_, func
            from datetime import timedelta

            cutoff_date = datetime.now() - timedelta(days=limit_days)

            with self.repository.get_session() as session:
                # 构建查询
                query = session.query(
                    StockPosition.stock_code,
                    StockPosition.stock_name,
                    func.max(StockPosition.screen_date).label('latest_date'),
                    func.count(StockPosition.id).label('screen_count')
                ).filter(
                    StockPosition.screen_date >= cutoff_date
                )

                if strategy_type:
                    query = query.join(
                        ScreeningRecord, StockPosition.screening_id == ScreeningRecord.id
                    ).filter(
                        ScreeningRecord.strategy_type == strategy_type
                    )

                # 按股票代码分组，实现去重
                result = query.group_by(
                    StockPosition.stock_code,
                    StockPosition.stock_name
                ).order_by(
                    func.max(StockPosition.screen_date).desc()
                ).all()

                return [
                    {
                        'stock_code': r.stock_code,
                        'stock_name': r.stock_name,
                        'latest_screen_date': r.latest_date,
                        'count': r.screen_count
                    }
                    for r in result
                ]

        except Exception as e:
            print(f"获取最新筛选股票失败: {e}")
            return []

    def get_stocks_with_return_stats(
        self,
        holding_days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取有收益记录的股票列表（已去重）

        Args:
            holding_days: 持仓天数（为空则获取所有）

        Returns:
            股票统计信息列表
        """
        try:
            from sqlalchemy import distinct, func

            with self.repository.get_session() as session:
                query = session.query(
                    distinct(StockPosition.stock_code),
                    StockPosition.stock_name,
                    func.avg(ReturnRecord.return_rate).label('avg_return'),
                    func.count(ReturnRecord.id).label('return_count')
                ).join(
                    ReturnRecord, StockPosition.id == ReturnRecord.position_id
                )

                if holding_days:
                    query = query.filter(ReturnRecord.holding_days == holding_days)

                result = query.group_by(
                    StockPosition.stock_code,
                    StockPosition.stock_name
                ).all()

                return [
                    {
                        'stock_code': r.stock_code,
                        'stock_name': r.stock_name,
                        'avg_return': float(r.avg_return) if r.avg_return else None,
                        'return_count': r.return_count
                    }
                    for r in result
                ]

        except Exception as e:
            print(f"获取收益统计股票失败: {e}")
            return []

    def get_db_date_range(self) -> Optional[tuple]:
        """
        获取数据库中数据的日期范围

        Returns:
            (earliest_date, latest_date) 或 None
        """
        try:
            from sqlalchemy import func

            with self.repository.get_session() as session:
                # 检查基准数据
                result = session.query(
                    func.min(BenchmarkData.trade_date),
                    func.max(BenchmarkData.trade_date)
                ).first()

                if result and result[0] and result[1]:
                    return (result[0], result[1])

            return None

        except Exception:
            return None


# 导入需要的模型类（放在文件末尾避免循环导入）
from strategy_tracker.db.models import ReturnRecord, StockPosition, ScreeningRecord, BenchmarkData
