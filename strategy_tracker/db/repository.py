"""
数据库操作封装
提供CRUD操作的便捷方法
兼容 SQLite 和 MySQL
"""
from datetime import datetime, date as date_type, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, and_, or_, func, cast, Date
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from ..config import get_database_url, DB_CONFIG
from .models import (
    Base, ScreeningRecord, StockPosition, ReturnRecord,
    BenchmarkData, StrategyStats
)


def _date_filter(column, target_date: datetime):
    """
    创建兼容 SQLite 和 MySQL 的日期过滤条件

    SQLite: datetime 存储为字符串，需要字符串比较
    MySQL: 支持 func.date() 函数
    """
    if DB_CONFIG['type'] == 'sqlite':
        # SQLite: 使用日期范围比较
        startOfDay = datetime(target_date.year, target_date.month, target_date.day)
        nextDay = startOfDay + timedelta(days=1)
        return and_(column >= startOfDay, column < nextDay)
    else:
        # MySQL/PostgreSQL: 使用 func.date()
        return func.date(column) == target_date.date()


class DatabaseRepository:
    """数据库仓库类 - 封装所有数据库操作"""

    def __init__(self):
        """初始化数据库连接"""
        db_url = get_database_url()
        # SQLite 需要特殊配置
        if DB_CONFIG['type'] == 'sqlite':
            self.engine = create_engine(
                db_url,
                echo=False,
                connect_args={"check_same_thread": False}  # SQLite 多线程支持
            )
        else:
            self.engine = create_engine(db_url, echo=False, pool_pre_ping=True)

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    @contextmanager
    def get_session(self):
        """获取数据库会话（上下文管理器）"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(self.engine)

    def drop_tables(self):
        """删除所有表（谨慎使用）"""
        Base.metadata.drop_all(self.engine)

    # ========== ScreeningRecord 操作 ==========

    def create_screening_record(
        self,
        strategy_type: str,
        screen_date: datetime,
        generated_at: datetime,
        total_stocks: int = 0,
        strategy_params: Optional[str] = None
    ) -> int:
        """创建筛选记录"""
        with self.get_session() as session:
            record = ScreeningRecord(
                strategy_type=strategy_type,
                screen_date=screen_date,
                generated_at=generated_at,
                total_stocks=total_stocks,
                strategy_params=strategy_params
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id

    def get_screening_record(self, record_id: int) -> Optional[ScreeningRecord]:
        """获取筛选记录"""
        with self.get_session() as session:
            return session.query(ScreeningRecord).filter_by(id=record_id).first()

    def get_screening_by_date_and_strategy(
        self,
        strategy_type: str,
        screen_date: datetime
    ) -> Optional[ScreeningRecord]:
        """根据日期和策略类型获取筛选记录"""
        with self.get_session() as session:
            return session.query(ScreeningRecord).filter(
                and_(
                    ScreeningRecord.strategy_type == strategy_type,
                    _date_filter(ScreeningRecord.screen_date, screen_date)
                )
            ).first()

    def list_screening_records(
        self,
        strategy_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ScreeningRecord]:
        """列出筛选记录"""
        with self.get_session() as session:
            query = session.query(ScreeningRecord)

            if strategy_type:
                query = query.filter(ScreeningRecord.strategy_type == strategy_type)
            if start_date:
                query = query.filter(ScreeningRecord.screen_date >= start_date)
            if end_date:
                query = query.filter(ScreeningRecord.screen_date <= end_date)

            return query.order_by(ScreeningRecord.screen_date.desc()).limit(limit).all()

    # ========== StockPosition 操作 ==========

    def create_position(
        self,
        screening_id: int,
        stock_code: str,
        stock_name: Optional[str] = None,
        screen_date: Optional[datetime] = None,
        screen_price: Optional[float] = None,
        score: Optional[float] = None,
        reason: Optional[str] = None
    ) -> int:
        """创建股票持仓"""
        with self.get_session() as session:
            position = StockPosition(
                screening_id=screening_id,
                stock_code=stock_code,
                stock_name=stock_name,
                screen_date=screen_date,
                screen_price=screen_price,
                score=score,
                reason=reason
            )
            session.add(position)
            session.commit()
            session.refresh(position)
            return position.id

    def bulk_create_positions(self, positions_data: List[Dict[str, Any]]) -> int:
        """批量创建持仓"""
        with self.get_session() as session:
            positions = [
                StockPosition(**data)
                for data in positions_data
            ]
            session.add_all(positions)
            session.commit()
            return len(positions)

    def get_position(self, position_id: int) -> Optional[StockPosition]:
        """获取持仓"""
        with self.get_session() as session:
            return session.query(StockPosition).filter_by(id=position_id).first()

    def get_positions_by_screening(self, screening_id: int) -> List[StockPosition]:
        """获取筛选记录的所有持仓"""
        with self.get_session() as session:
            return session.query(StockPosition).filter_by(screening_id=screening_id).all()

    def get_positions_by_stock(self, stock_code: str) -> List[StockPosition]:
        """获取股票的所有持仓记录"""
        with self.get_session() as session:
            return session.query(StockPosition).filter_by(stock_code=stock_code).all()

    def get_positions_need_update(
        self,
        holding_days: int,
        check_date: datetime
    ) -> List[StockPosition]:
        """获取需要更新收益的持仓"""
        with self.get_session() as session:
            # 找出没有对应holding_days收益记录的持仓ID
            position_ids_with_return = session.query(ReturnRecord.position_id).filter(
                and_(
                    ReturnRecord.holding_days == holding_days,
                    _date_filter(ReturnRecord.check_date, check_date)
                )
            ).all()

            existing_ids = [pid[0] for pid in position_ids_with_return]

            # 获取所有符合条件的持仓（screen_date <= check_date 且没有收益记录）
            positions = session.query(StockPosition).filter(
                and_(
                    StockPosition.screen_date <= check_date,
                    ~StockPosition.id.in_(existing_ids) if existing_ids else True
                )
            ).all()

            # 将对象转换为字典列表，避免 detached instance 问题
            result = []
            for p in positions:
                result.append({
                    'id': p.id,
                    'screening_id': p.screening_id,
                    'stock_code': p.stock_code,
                    'stock_name': p.stock_name,
                    'screen_date': p.screen_date,
                    'screen_price': p.screen_price,
                    'score': p.score,
                    'reason': p.reason,
                    'status': p.status,
                    'created_at': p.created_at
                })

            return result

    # ========== ReturnRecord 操作 ==========

    def create_return_record(
        self,
        position_id: int,
        holding_days: int,
        check_date: datetime,
        close_price: Optional[float] = None,
        return_rate: Optional[float] = None,
        benchmark_return: Optional[float] = None,
        excess_return: Optional[float] = None,
        is_trading_day: bool = True,
        notes: Optional[str] = None
    ) -> Optional[int]:
        """创建收益记录"""
        with self.get_session() as session:
            record = ReturnRecord(
                position_id=position_id,
                holding_days=holding_days,
                check_date=check_date,
                close_price=close_price,
                return_rate=return_rate,
                benchmark_return=benchmark_return,
                excess_return=excess_return,
                is_trading_day=is_trading_day,
                notes=notes
            )
            session.add(record)
            try:
                session.commit()
                session.refresh(record)
                return record.id
            except IntegrityError:
                # 唯一约束冲突，记录已存在
                session.rollback()
                return None

    def bulk_create_return_records(self, records_data: List[Dict[str, Any]]) -> int:
        """批量创建收益记录"""
        with self.get_session() as session:
            records = [
                ReturnRecord(**data)
                for data in records_data
            ]
            session.add_all(records)
            try:
                session.commit()
                return len(records)
            except IntegrityError:
                session.rollback()
                return 0

    def get_returns_by_position(self, position_id: int) -> List[ReturnRecord]:
        """获取持仓的所有收益记录"""
        with self.get_session() as session:
            return session.query(ReturnRecord).filter_by(
                position_id=position_id
            ).order_by(ReturnRecord.holding_days).all()

    def get_return_record(
        self,
        position_id: int,
        holding_days: int
    ) -> Optional[ReturnRecord]:
        """获取特定持仓天数的收益记录"""
        with self.get_session() as session:
            return session.query(ReturnRecord).filter(
                and_(
                    ReturnRecord.position_id == position_id,
                    ReturnRecord.holding_days == holding_days
                )
            ).first()

    # ========== BenchmarkData 操作 ==========

    def create_benchmark_data(
        self,
        trade_date: datetime,
        open_price: Optional[float] = None,
        close_price: Optional[float] = None,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
        volume: Optional[float] = None,
        daily_return: Optional[float] = None
    ) -> Optional[int]:
        """创建基准数据"""
        with self.get_session() as session:
            data = BenchmarkData(
                trade_date=trade_date,
                open_price=open_price,
                close_price=close_price,
                high_price=high_price,
                low_price=low_price,
                volume=volume,
                daily_return=daily_return
            )
            session.add(data)
            try:
                session.commit()
                session.refresh(data)
                return data.id
            except IntegrityError:
                session.rollback()
                return None

    def bulk_create_benchmark_data(self, data_list: List[Dict[str, Any]]) -> int:
        """批量创建基准数据"""
        with self.get_session() as session:
            data_objects = [BenchmarkData(**d) for d in data_list]
            session.add_all(data_objects)
            try:
                session.commit()
                return len(data_objects)
            except IntegrityError:
                session.rollback()
                return 0

    def get_benchmark_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[BenchmarkData]:
        """获取基准数据"""
        with self.get_session() as session:
            query = session.query(BenchmarkData)

            if start_date:
                query = query.filter(BenchmarkData.trade_date >= start_date)
            if end_date:
                query = query.filter(BenchmarkData.trade_date <= end_date)

            return query.order_by(BenchmarkData.trade_date).all()

    def get_benchmark_by_date(self, trade_date: datetime) -> Optional[BenchmarkData]:
        """获取特定日期的基准数据"""
        with self.get_session() as session:
            return session.query(BenchmarkData).filter(
                _date_filter(BenchmarkData.trade_date, trade_date)
            ).first()

    def calculate_benchmark_return(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[float]:
        """计算基准收益率"""
        with self.get_session() as session:
            start_data = session.query(BenchmarkData).filter(
                _date_filter(BenchmarkData.trade_date, start_date)
            ).first()

            end_data = session.query(BenchmarkData).filter(
                _date_filter(BenchmarkData.trade_date, end_date)
            ).first()

            if start_data and end_data:
                if start_data.close_price and end_data.close_price:
                    return ((end_data.close_price - start_data.close_price) / start_data.close_price) * 100

            return None

    # ========== StrategyStats 操作 ==========

    def create_strategy_stats(
        self,
        stat_date: datetime,
        strategy_type: str,
        holding_days: int,
        total_positions: int = 0,
        winning_positions: int = 0,
        win_rate: Optional[float] = None,
        avg_return: Optional[float] = None,
        median_return: Optional[float] = None,
        max_return: Optional[float] = None,
        min_return: Optional[float] = None,
        avg_benchmark_return: Optional[float] = None,
        avg_excess_return: Optional[float] = None
    ) -> Optional[int]:
        """创建策略统计"""
        with self.get_session() as session:
            stats = StrategyStats(
                stat_date=stat_date,
                strategy_type=strategy_type,
                holding_days=holding_days,
                total_positions=total_positions,
                winning_positions=winning_positions,
                win_rate=win_rate,
                avg_return=avg_return,
                median_return=median_return,
                max_return=max_return,
                min_return=min_return,
                avg_benchmark_return=avg_benchmark_return,
                avg_excess_return=avg_excess_return
            )
            session.add(stats)
            try:
                session.commit()
                session.refresh(stats)
                return stats.id
            except IntegrityError:
                # 统计已存在，更新
                session.rollback()
                return self.update_strategy_stats(
                    stat_date, strategy_type, holding_days,
                    total_positions=total_positions,
                    winning_positions=winning_positions,
                    win_rate=win_rate,
                    avg_return=avg_return,
                    median_return=median_return,
                    max_return=max_return,
                    min_return=min_return,
                    avg_benchmark_return=avg_benchmark_return,
                    avg_excess_return=avg_excess_return
                )

    def update_strategy_stats(
        self,
        stat_date: datetime,
        strategy_type: str,
        holding_days: int,
        **kwargs
    ) -> Optional[int]:
        """更新策略统计"""
        with self.get_session() as session:
            stats = session.query(StrategyStats).filter(
                and_(
                    _date_filter(StrategyStats.stat_date, stat_date),
                    StrategyStats.strategy_type == strategy_type,
                    StrategyStats.holding_days == holding_days
                )
            ).first()

            if stats:
                for key, value in kwargs.items():
                    if hasattr(stats, key) and value is not None:
                        setattr(stats, key, value)
                session.commit()
                return stats.id
            return None

    def get_strategy_stats(
        self,
        strategy_type: Optional[str] = None,
        holding_days: Optional[int] = None,
        stat_date: Optional[datetime] = None
    ) -> List[StrategyStats]:
        """获取策略统计"""
        with self.get_session() as session:
            query = session.query(StrategyStats)

            if strategy_type:
                query = query.filter(StrategyStats.strategy_type == strategy_type)
            if holding_days:
                query = query.filter(StrategyStats.holding_days == holding_days)
            if stat_date:
                query = query.filter(_date_filter(StrategyStats.stat_date, stat_date))

            return query.order_by(
                StrategyStats.stat_date.desc(),
                StrategyStats.strategy_type,
                StrategyStats.holding_days
            ).all()

    def calculate_stats_from_returns(
        self,
        strategy_type: str,
        holding_days: int,
        stat_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """从收益记录计算统计数据"""
        with self.get_session() as session:
            # 获取所有相关持仓的收益记录
            query = session.query(ReturnRecord, StockPosition, ScreeningRecord).join(
                StockPosition, ReturnRecord.position_id == StockPosition.id
            ).join(
                ScreeningRecord, StockPosition.screening_id == ScreeningRecord.id
            ).filter(
                and_(
                    ScreeningRecord.strategy_type == strategy_type,
                    ReturnRecord.holding_days == holding_days,
                    ReturnRecord.is_trading_day == True
                )
            )

            results = query.all()

            if not results:
                return None

            # 提取收益率
            returns = [r[0].return_rate for r in results if r[0].return_rate is not None]
            benchmark_returns = [r[0].benchmark_return for r in results if r[0].benchmark_return is not None]
            excess_returns = [r[0].excess_return for r in results if r[0].excess_return is not None]

            if not returns:
                return None

            # 计算统计指标
            winning_count = sum(1 for r in returns if r > 0)
            total_count = len(returns)

            import statistics
            stats_data = {
                'total_positions': total_count,
                'winning_positions': winning_count,
                'win_rate': (winning_count / total_count * 100) if total_count > 0 else 0,
                'avg_return': statistics.mean(returns),
                'median_return': statistics.median(returns),
                'max_return': max(returns),
                'min_return': min(returns),
            }

            if benchmark_returns:
                stats_data['avg_benchmark_return'] = statistics.mean(benchmark_returns)

            if excess_returns:
                stats_data['avg_excess_return'] = statistics.mean(excess_returns)

            return stats_data


# 全局仓库实例
_repo = None


def get_repository() -> DatabaseRepository:
    """获取数据库仓库实例（单例）"""
    global _repo
    if _repo is None:
        _repo = DatabaseRepository()
    return _repo
