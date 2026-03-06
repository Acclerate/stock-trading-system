"""
策略跟踪系统

跟踪股票筛选策略的实际表现，计算收益并生成报告。
"""

__version__ = "1.0.0"

from .config import (
    DB_CONFIG,
    get_database_url,
    STRATEGY_TYPES,
    HOLDING_PERIODS,
    OUTPUTS_DIR,
    FILE_PATTERNS
)

__all__ = [
    'DB_CONFIG',
    'get_database_url',
    'STRATEGY_TYPES',
    'HOLDING_PERIODS',
    'OUTPUTS_DIR',
    'FILE_PATTERNS',
]
