"""
监控配置管理模块

加载和管理自选股列表、监控参数。
支持 YAML 配置文件和代码配置。
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class StockConfig:
    """单股票配置"""
    symbol: str
    name: str
    enabled: bool = True
    position_price: Optional[float] = None  # 持仓成本价

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'name': self.name,
            'enabled': self.enabled,
            'position_price': self.position_price
        }


@dataclass
class MonitorConfig:
    """监控配置"""
    stocks: List[StockConfig] = field(default_factory=list)
    interval_seconds: int = 30
    max_updates_per_stock: Optional[int] = None
    max_workers: int = 8

    @classmethod
    def from_yaml(cls, config_path: str) -> 'MonitorConfig':
        """
        从 YAML 文件加载配置

        参数:
            config_path: 配置文件路径

        返回:
            MonitorConfig 实例
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        stocks = []
        for item in data.get('stocks', []):
            stocks.append(StockConfig(
                symbol=item['symbol'],
                name=item['name'],
                enabled=item.get('enabled', True),
                position_price=item.get('position_price')
            ))

        return cls(
            stocks=stocks,
            interval_seconds=data.get('interval_seconds', 30),
            max_updates_per_stock=data.get('max_updates_per_stock'),
            max_workers=data.get('max_workers', 8)
        )

    def get_enabled_stocks(self) -> List[StockConfig]:
        """获取启用的股票列表"""
        return [s for s in self.stocks if s.enabled]

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'stocks': [s.to_dict() for s in self.stocks],
            'interval_seconds': self.interval_seconds,
            'max_updates_per_stock': self.max_updates_per_stock,
            'max_workers': self.max_workers
        }


def load_watchlist(config_path: str) -> List[Dict]:
    """
    加载自选股列表（用于事件驱动模式）

    参数:
        config_path: 配置文件路径

    返回:
        [{'symbol': '600519', 'name': '贵州茅台'}, ...]
    """
    config = MonitorConfig.from_yaml(config_path)
    return [
        {'symbol': s.symbol, 'name': s.name}
        for s in config.get_enabled_stocks()
    ]


def create_default_watchlist(path: str = 'strategies/watchlist.yaml'):
    """
    创建默认的自选股配置文件

    参数:
        path: 配置文件路径
    """
    default_config = {
        'stocks': [
            {'symbol': '002202', 'name': '金风科技', 'enabled': True},
            {'symbol': '002459', 'name': '晶澳科技', 'enabled': True},
            {'symbol': '600489', 'name': '中金黄金', 'enabled': False},
        ],
        'interval_seconds': 30,
        'max_updates_per_stock': None,
        'max_workers': 8
    }

    # 确保目录存在
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)

    print(f"✅ 已创建默认配置文件: {path}")


def create_default_monitoring_config(path: str = 'config/monitoring.yaml'):
    """
    创建默认的监控参数配置文件

    参数:
        path: 配置文件路径
    """
    default_config = {
        'monitoring': {
            'polling': {
                'interval_seconds': 30,
                'max_workers': 8,
                'retry_attempts': 3,
                'retry_delay': 5
            },
            'event_driven': {
                'frequency': '60s',
                'bar_count': 120,
                'subscribe_fields': [
                    'symbol', 'eob', 'open', 'high', 'low', 'close', 'volume', 'amount'
                ]
            }
        },
        'alerts': {
            'console': True,
            'log_file': True,
            'log_dir': 'logs/signals',
            'thresholds': {
                'buy_score': 4,
                'sell_score': 2
            }
        }
    }

    # 确保目录存在
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)

    print(f"✅ 已创建默认监控配置文件: {path}")


# ========== 测试代码 ==========
if __name__ == "__main__":
    # 创建默认配置文件
    print("创建默认配置文件...")
    create_default_watchlist()
    create_default_monitoring_config()

    # 测试加载配置
    print("\n测试加载配置...")
    config = MonitorConfig.from_yaml('strategies/watchlist.yaml')
    print(f"加载了 {len(config.stocks)} 只股票")
    print(f"启用的股票: {len(config.get_enabled_stocks())} 只")
    print(f"更新间隔: {config.interval_seconds} 秒")
    print(f"并发线程: {config.max_workers}")

    for stock in config.get_enabled_stocks():
        print(f"  - {stock.name} ({stock.symbol})")
