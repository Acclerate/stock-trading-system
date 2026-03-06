"""
策略跟踪系统数据库模型
使用SQLAlchemy ORM定义数据表结构
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class ScreeningRecord(Base):
    """筛选记录表 - 记录每次策略筛选的结果"""
    __tablename__ = 'screening_records'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    strategy_type = Column(String(50), nullable=False, index=True, comment='策略类型')
    screen_date = Column(DateTime, nullable=False, index=True, comment='筛选日期')
    generated_at = Column(DateTime, nullable=False, comment='生成时间')
    total_stocks = Column(Integer, default=0, comment='筛选到的股票数量')
    strategy_params = Column(Text, nullable=True, comment='策略参数(JSON格式)')
    created_at = Column(DateTime, default=datetime.now, comment='记录创建时间')

    # 关联股票持仓
    positions = relationship("StockPosition", back_populates="screening", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_strategy_date', 'strategy_type', 'screen_date'),
        {'comment': '筛选记录表'},
    )


class StockPosition(Base):
    """股票持仓表 - 记录筛选出的具体股票"""
    __tablename__ = 'stock_positions'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    screening_id = Column(Integer, ForeignKey('screening_records.id', ondelete='CASCADE'),
                          nullable=False, index=True, comment='筛选记录ID')
    stock_code = Column(String(10), nullable=False, index=True, comment='股票代码')
    stock_name = Column(String(50), nullable=True, comment='股票名称')
    screen_date = Column(DateTime, nullable=False, index=True, comment='筛选日期')
    screen_price = Column(Float, nullable=True, comment='筛选时价格')
    score = Column(Float, nullable=True, comment='评分(如果有)')
    reason = Column(Text, nullable=True, comment='筛选原因/依据')
    status = Column(String(20), default='active', comment='状态: active/expired/delisted')
    created_at = Column(DateTime, default=datetime.now, comment='记录创建时间')

    # 关联筛选记录
    screening = relationship("ScreeningRecord", back_populates="positions")
    # 关联收益记录
    return_records = relationship("ReturnRecord", back_populates="position", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_stock_date', 'stock_code', 'screen_date'),
        Index('idx_screening_date', 'screening_id', 'screen_date'),
        {'comment': '股票持仓表'},
    )


class ReturnRecord(Base):
    """收益记录表 - 记录持仓在特定时间的收益情况"""
    __tablename__ = 'return_records'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    position_id = Column(Integer, ForeignKey('stock_positions.id', ondelete='CASCADE'),
                         nullable=False, index=True, comment='持仓ID')
    holding_days = Column(Integer, nullable=False, comment='持仓天数')
    check_date = Column(DateTime, nullable=False, index=True, comment='检查日期')
    close_price = Column(Float, nullable=True, comment='当日收盘价')
    return_rate = Column(Float, nullable=True, comment='收益率(%)')
    benchmark_return = Column(Float, nullable=True, comment='基准收益率(%)')
    excess_return = Column(Float, nullable=True, comment='超额收益率(%)')
    is_trading_day = Column(Boolean, default=True, comment='是否为交易日')
    notes = Column(String(200), nullable=True, comment='备注')
    created_at = Column(DateTime, default=datetime.now, comment='记录创建时间')

    # 关联持仓
    position = relationship("StockPosition", back_populates="return_records")

    __table_args__ = (
        UniqueConstraint('position_id', 'holding_days', name='uk_position_days'),
        Index('idx_check_date', 'check_date'),
        Index('idx_holding_days', 'holding_days'),
        {'comment': '收益记录表'},
    )


class BenchmarkData(Base):
    """基准数据表 - 沪深300指数数据"""
    __tablename__ = 'benchmark_data'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    trade_date = Column(DateTime, nullable=False, unique=True, index=True, comment='交易日期')
    open_price = Column(Float, nullable=True, comment='开盘价')
    close_price = Column(Float, nullable=True, comment='收盘价')
    high_price = Column(Float, nullable=True, comment='最高价')
    low_price = Column(Float, nullable=True, comment='最低价')
    volume = Column(Float, nullable=True, comment='成交量')
    daily_return = Column(Float, nullable=True, comment='日收益率(%)')
    created_at = Column(DateTime, default=datetime.now, comment='记录创建时间')

    __table_args__ = (
        Index('idx_trade_date', 'trade_date'),
        {'comment': '基准数据表(沪深300)'},
    )


class StrategyStats(Base):
    """策略统计表 - 汇总策略表现统计"""
    __tablename__ = 'strategy_stats'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    stat_date = Column(DateTime, nullable=False, index=True, comment='统计日期')
    strategy_type = Column(String(50), nullable=False, index=True, comment='策略类型')
    holding_days = Column(Integer, nullable=False, comment='持仓周期')
    total_positions = Column(Integer, default=0, comment='总持仓数')
    winning_positions = Column(Integer, default=0, comment='盈利持仓数')
    win_rate = Column(Float, nullable=True, comment='胜率(%)')
    avg_return = Column(Float, nullable=True, comment='平均收益率(%)')
    median_return = Column(Float, nullable=True, comment='中位数收益率(%)')
    max_return = Column(Float, nullable=True, comment='最大收益率(%)')
    min_return = Column(Float, nullable=True, comment='最小收益率(%)')
    avg_benchmark_return = Column(Float, nullable=True, comment='平均基准收益率(%)')
    avg_excess_return = Column(Float, nullable=True, comment='平均超额收益率(%)')
    created_at = Column(DateTime, default=datetime.now, comment='记录创建时间')

    __table_args__ = (
        UniqueConstraint('stat_date', 'strategy_type', 'holding_days', name='uk_stat_unique'),
        Index('idx_stat_strategy', 'stat_date', 'strategy_type', 'holding_days'),
        {'comment': '策略统计表'},
    )
