"""
收益计算引擎
计算持仓在指定天数后的收益率
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from strategy_tracker.db.repository import get_repository
from strategy_tracker.db.models import StockPosition, ReturnRecord
from strategy_tracker.data.collector import DataCollector, BenchmarkCollector
from strategy_tracker.config import HOLDING_PERIODS


class ReturnCalculator:
    """收益计算器 - 计算持仓收益和基准对比"""

    def __init__(self, repository=None):
        """
        初始化收益计算器

        Args:
            repository: 数据库仓库实例，如果为None则创建新实例
        """
        self.repository = repository or get_repository()
        self.data_collector = DataCollector()

    def calculate_position_return(
        self,
        position,
        holding_days: int,
        check_date: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        计算单个持仓的收益

        Args:
            position: 股票持仓对象或字典
            holding_days: 持仓天数
            check_date: 检查日期，如果为None则自动计算

        Returns:
            包含收益信息的字典
        """
        try:
            # 兼容字典和对象两种格式
            if isinstance(position, dict):
                position_id = position['id']
                stock_code = position['stock_code']
                screen_date = position['screen_date']
                screen_price = position.get('screen_price')
            else:
                position_id = position.id
                stock_code = position.stock_code
                screen_date = position.screen_date
                screen_price = position.screen_price

            # 确定检查日期
            if check_date is None:
                check_date = self._calculate_check_date(screen_date, holding_days)

            if check_date is None:
                return None

            # 获取当前价格
            current_price = self.data_collector.get_stock_price(
                stock_code,
                check_date,
                screen_date
            )

            if current_price is None:
                return {
                    'position_id': position_id,
                    'holding_days': holding_days,
                    'check_date': check_date,
                    'close_price': None,
                    'return_rate': None,
                    'benchmark_return': None,
                    'excess_return': None,
                    'is_trading_day': False,
                    'notes': '无法获取价格数据'
                }

            # 计算收益率
            if screen_price and screen_price > 0:
                return_rate = ((current_price - screen_price) / screen_price) * 100
            else:
                return_rate = None

            # 计算基准收益率
            benchmark_return = self.data_collector.calculate_benchmark_return(
                screen_date,
                check_date
            )

            # 计算超额收益
            excess_return = None
            if return_rate is not None and benchmark_return is not None:
                excess_return = return_rate - benchmark_return

            # 判断是否为交易日
            is_trading_day = self.data_collector.is_trading_day(check_date)

            return {
                'position_id': position_id,
                'holding_days': holding_days,
                'check_date': check_date,
                'close_price': current_price,
                'return_rate': return_rate,
                'benchmark_return': benchmark_return,
                'excess_return': excess_return,
                'is_trading_day': is_trading_day,
                'notes': None
            }

        except Exception as e:
            print(f"计算持仓 {position.get('id') if isinstance(position, dict) else position.id} 收益失败: {e}")
            return None

    def _calculate_check_date(
        self,
        screen_date: datetime,
        holding_days: int
    ) -> Optional[datetime]:
        """
        计算检查日期（第n个交易日）

        Args:
            screen_date: 筛选日期
            holding_days: 持仓天数

        Returns:
            检查日期
        """
        return self.data_collector.get_nth_trading_day(screen_date, holding_days)

    def calculate_and_store(
        self,
        position,
        holding_days: int,
        check_date: Optional[datetime] = None,
        force_update: bool = False
    ) -> Optional[int]:
        """
        计算并存储收益记录

        Args:
            position: 股票持仓对象或字典
            holding_days: 持仓天数
            check_date: 检查日期
            force_update: 是否强制更新已存在的记录

        Returns:
            收益记录ID，如果失败返回None
        """
        # 兼容字典和对象两种格式
        if isinstance(position, dict):
            position_id = position['id']
        else:
            position_id = position.id

        # 检查是否已存在记录
        if not force_update:
            existing = self.repository.get_return_record(position_id, holding_days)
            if existing:
                return existing.id

        # 计算收益
        result = self.calculate_position_return(position, holding_days, check_date)

        if result is None:
            return None

        # 存储到数据库
        record_id = self.repository.create_return_record(**result)
        return record_id

    def calculate_all_positions(
        self,
        holding_days: int,
        check_date: Optional[datetime] = None,
        force_update: bool = False
    ) -> Dict[str, int]:
        """
        计算所有持仓的收益

        Args:
            holding_days: 持仓天数
            check_date: 检查日期
            force_update: 是否强制更新

        Returns:
            统计信息字典
        """
        # 确定检查日期
        if check_date is None:
            check_date = datetime.now()

        # 获取需要更新的持仓
        positions = self.repository.get_positions_need_update(holding_days, check_date)

        if not positions:
            print(f"没有需要计算 {holding_days} 天收益的持仓")
            return {'total': 0, 'success': 0, 'failed': 0}

        stats = {'total': len(positions), 'success': 0, 'failed': 0}

        print(f"开始计算 {len(positions)} 个持仓的 {holding_days} 天收益...")

        for i, position in enumerate(positions):
            if (i + 1) % 50 == 0:
                print(f"进度: {i + 1}/{len(positions)}")

            result = self.calculate_and_store(position, holding_days, check_date, force_update)

            if result:
                stats['success'] += 1
            else:
                stats['failed'] += 1

        print(f"计算完成: 成功 {stats['success']}, 失败 {stats['failed']}")
        return stats

    def calculate_all_holding_periods(
        self,
        check_date: Optional[datetime] = None,
        force_update: bool = False
    ) -> Dict[int, Dict[str, int]]:
        """
        计算所有持仓周期的收益

        Args:
            check_date: 检查日期
            force_update: 是否强制更新

        Returns:
            各持仓周期的统计信息
        """
        all_stats = {}

        for holding_days in HOLDING_PERIODS:
            print(f"\n计算 {holding_days} 天持仓收益...")
            stats = self.calculate_all_positions(holding_days, check_date, force_update)
            all_stats[holding_days] = stats

        return all_stats

    def update_pending_returns(self, check_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        更新所有待计算的收益记录

        Args:
            check_date: 检查日期

        Returns:
            统计信息
        """
        if check_date is None:
            check_date = datetime.now()

        print("=" * 60)
        print("更新待计算的收益记录")
        print("=" * 60)
        print(f"检查日期: {check_date.strftime('%Y-%m-%d')}")
        print()

        all_stats = {}

        for holding_days in HOLDING_PERIODS:
            print(f"\n--- {holding_days} 天持仓 ---")
            stats = self.calculate_all_positions(holding_days, check_date, force_update=False)
            all_stats[holding_days] = stats

        # 汇总统计
        total_success = sum(s['success'] for s in all_stats.values())
        total_failed = sum(s['failed'] for s in all_stats.values())

        print()
        print("=" * 60)
        print("更新完成")
        print(f"总计: 成功 {total_success}, 失败 {total_failed}")
        print("=" * 60)

        return {
            'by_period': all_stats,
            'total_success': total_success,
            'total_failed': total_failed
        }

    def recalculate_position(self, position_id: int) -> bool:
        """
        重新计算指定持仓的所有收益

        Args:
            position_id: 持仓ID

        Returns:
            是否成功
        """
        position = self.repository.get_position(position_id)
        if not position:
            print(f"持仓 {position_id} 不存在")
            return False

        print(f"重新计算持仓 {position_id} ({position.stock_code}) 的收益...")

        success_count = 0
        for holding_days in HOLDING_PERIODS:
            result = self.calculate_and_store(position, holding_days, force_update=True)
            if result:
                success_count += 1

        print(f"完成: {success_count}/{len(HOLDING_PERIODS)} 个周期")
        return success_count > 0

    def get_position_returns(self, position_id: int) -> List[ReturnRecord]:
        """
        获取持仓的所有收益记录

        Args:
            position_id: 持仓ID

        Returns:
            收益记录列表
        """
        return self.repository.get_returns_by_position(position_id)

    def get_return_summary(
        self,
        strategy_type: str,
        holding_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        获取策略收益汇总

        Args:
            strategy_type: 策略类型
            holding_days: 持仓天数

        Returns:
            汇总信息
        """
        stats = self.repository.calculate_stats_from_returns(
            strategy_type,
            holding_days,
            datetime.now()
        )

        return stats


class StatisticsCalculator:
    """统计计算器 - 计算策略表现统计"""

    def __init__(self, repository=None):
        """
        初始化统计计算器

        Args:
            repository: 数据库仓库实例
        """
        self.repository = repository or get_repository()

    def calculate_strategy_stats(
        self,
        strategy_type: str,
        stat_date: Optional[datetime] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        计算策略统计数据

        Args:
            strategy_type: 策略类型
            stat_date: 统计日期

        Returns:
            各持仓周期的统计数据
        """
        if stat_date is None:
            stat_date = datetime.now()

        stats_by_period = {}

        for holding_days in HOLDING_PERIODS:
            # 获取原始统计数据
            raw_stats = self.repository.calculate_stats_from_returns(
                strategy_type,
                holding_days,
                stat_date
            )

            if raw_stats:
                # 存储到数据库
                self.repository.create_strategy_stats(
                    stat_date=stat_date,
                    strategy_type=strategy_type,
                    holding_days=holding_days,
                    **raw_stats
                )

                stats_by_period[holding_days] = raw_stats

        return stats_by_period

    def calculate_all_strategies(
        self,
        stat_date: Optional[datetime] = None
    ) -> Dict[str, Dict[int, Dict[str, Any]]]:
        """
        计算所有策略的统计数据

        Args:
            stat_date: 统计日期

        Returns:
            所有策略的统计数据
        """
        from strategy_tracker.config import STRATEGY_TYPES

        all_stats = {}

        for strategy_type in STRATEGY_TYPES.keys():
            print(f"计算 {strategy_type} 统计...")
            stats = self.calculate_strategy_stats(strategy_type, stat_date)
            if stats:
                all_stats[strategy_type] = stats

        return all_stats

    def get_latest_stats(
        self,
        strategy_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取最新的统计数据

        Args:
            strategy_type: 策略类型，如果为None则获取所有策略

        Returns:
            统计数据列表
        """
        stats = self.repository.get_strategy_stats(
            strategy_type=strategy_type
        )

        return [{
            'strategy_type': s.strategy_type,
            'holding_days': s.holding_days,
            'total_positions': s.total_positions,
            'winning_positions': s.winning_positions,
            'win_rate': s.win_rate,
            'avg_return': s.avg_return,
            'median_return': s.median_return,
            'max_return': s.max_return,
            'min_return': s.min_return,
            'avg_benchmark_return': s.avg_benchmark_return,
            'avg_excess_return': s.avg_excess_return,
            'stat_date': s.stat_date
        } for s in stats]
