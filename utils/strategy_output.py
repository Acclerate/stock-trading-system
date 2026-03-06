"""
统一策略输出工具
支持 txt、CSV、SQLite 三种格式输出

使用示例:
    from utils.strategy_output import StrategyOutputManager, StrategyMetadata, StockData
    from strategy_tracker.db.repository import get_repository

    metadata = StrategyMetadata(
        strategy_name="沪深300成分股筛选",
        strategy_type="hs300_screen",
        screen_date=datetime.now(),
        generated_at=datetime.now(),
        scan_count=300,
        match_count=10,
        strategy_params={'pool_id': 'hs300', 'days': 365},
        filter_conditions="至少满足2个买入条件",
        scan_scope="沪深300成分股"
    )

    output_mgr = StrategyOutputManager(metadata)

    # 添加股票数据
    output_mgr.add_stock(StockData(
        stock_code="600519",
        stock_name="贵州茅台",
        screen_price=1850.0,
        score=15.5,
        reason="均线金叉 + MACD金叉",
        extra_fields={'ma5': 1845.0, 'ma10': 1830.0}
    ))

    # 输出所有格式
    repo = get_repository()
    results = output_mgr.output_all(repo=repo)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import pandas as pd
import json


@dataclass
class StrategyMetadata:
    """策略元数据"""
    strategy_name: str          # 策略显示名称
    strategy_type: str          # 策略类型（数据库标识）
    screen_date: datetime       # 筛选日期
    generated_at: datetime      # 生成时间
    scan_count: int             # 扫描股票数量
    match_count: int            # 符合条件数量
    strategy_params: Dict[str, Any]  # 策略参数
    filter_conditions: str      # 筛选条件描述
    scan_scope: str = ""        # 扫描范围描述


@dataclass
class StockData:
    """股票数据"""
    stock_code: str             # 股票代码（6位数字）
    stock_name: str             # 股票名称
    screen_price: Optional[float]  # 筛选价格
    score: Optional[float]      # 评分/收益率
    reason: str                 # 筛选原因/依据
    extra_fields: Dict[str, Any] = field(default_factory=dict)  # 策略特有字段


class StrategyOutputManager:
    """策略输出管理器 - 统一三种格式输出"""

    def __init__(self, metadata: StrategyMetadata, outputs_dir: Path = None):
        """
        初始化输出管理器

        Args:
            metadata: 策略元数据
            outputs_dir: 输出目录，默认为项目根目录下的 outputs/
        """
        self.metadata = metadata
        self.stocks: List[StockData] = []

        # 设置输出目录
        if outputs_dir is None:
            # 默认使用项目根目录下的 outputs/
            project_root = Path(__file__).parent.parent
            outputs_dir = project_root / "outputs"

        self.outputs_dir = Path(outputs_dir)

    def add_stock(self, stock: StockData):
        """
        添加股票数据

        Args:
            stock: StockData 对象
        """
        self.stocks.append(stock)

    def add_stocks(self, stocks: List[StockData]):
        """
        批量添加股票数据

        Args:
            stocks: StockData 对象列表
        """
        self.stocks.extend(stocks)

    def output_txt(self, filepath: Optional[Path] = None,
                   table_formatter: Optional[Callable[[List[StockData]], List[str]]] = None) -> Path:
        """
        输出 txt 格式（保持现有格式兼容）

        Args:
            filepath: 输出文件路径，默认为 outputs/{strategy_type}_YYYYMMDD_HHMMSS.txt
            table_formatter: 自定义表格格式化函数

        Returns:
            输出文件的路径
        """
        if filepath is None:
            timestamp = self.metadata.generated_at.strftime("%Y%m%d_%H%M%S")
            filepath = self.outputs_dir / f"{self.metadata.strategy_type}_{timestamp}.txt"

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines = self._generate_txt_content(table_formatter)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return filepath

    def output_csv(self, filepath: Optional[Path] = None) -> Path:
        """
        输出 CSV 格式

        Args:
            filepath: 输出文件路径，默认为 outputs/csv/{strategy_type}_YYYYMMDD_HHMMSS.csv

        Returns:
            输出文件的路径
        """
        if filepath is None:
            timestamp = self.metadata.generated_at.strftime("%Y%m%d_%H%M%S")
            csv_dir = self.outputs_dir / "csv"
            filepath = csv_dir / f"{self.metadata.strategy_type}_{timestamp}.csv"

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 构建数据行
        rows = []
        base_cols = ['筛选日期', '股票代码', '股票名称', '筛选价格', '评分', '筛选原因']
        extra_cols = set()

        # 收集所有额外的字段
        for stock in self.stocks:
            extra_cols.update(stock.extra_fields.keys())

        extra_cols = sorted(extra_cols)
        all_cols = base_cols + list(extra_cols)

        for stock in self.stocks:
            row = {
                '筛选日期': self.metadata.screen_date.strftime('%Y-%m-%d'),
                '股票代码': stock.stock_code,
                '股票名称': stock.stock_name,
                '筛选价格': stock.screen_price,
                '评分': stock.score,
                '筛选原因': stock.reason,
                **stock.extra_fields
            }
            rows.append(row)

        df = pd.DataFrame(rows, columns=all_cols)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')

        return filepath

    def output_sqlite(self, repo) -> int:
        """
        输出到 SQLite 数据库

        Args:
            repo: DatabaseRepository 实例

        Returns:
            screening_id: 筛选记录ID
        """
        # 将策略参数序列化为 JSON 字符串
        strategy_params_json = json.dumps(
            self.metadata.strategy_params,
            ensure_ascii=False,
            default=str  # 处理 datetime 等不可序列化的类型
        )

        # 创建筛选记录
        screening_id = repo.create_screening_record(
            strategy_type=self.metadata.strategy_type,
            screen_date=self.metadata.screen_date,
            generated_at=self.metadata.generated_at,
            total_stocks=self.metadata.match_count,
            strategy_params=strategy_params_json
        )

        # 批量创建持仓
        positions_data = []
        for stock in self.stocks:
            positions_data.append({
                'screening_id': screening_id,
                'stock_code': stock.stock_code,
                'stock_name': stock.stock_name,
                'screen_date': self.metadata.screen_date,
                'screen_price': stock.screen_price,
                'score': stock.score,
                'reason': stock.reason
            })

        repo.bulk_create_positions(positions_data)

        return screening_id

    def output_all(self, repo=None, txt_path: Optional[Path] = None,
                   csv_path: Optional[Path] = None,
                   table_formatter: Optional[Callable[[List[StockData]], List[str]]] = None) -> Dict[str, Any]:
        """
        同时输出所有格式

        Args:
            repo: DatabaseRepository 实例，如果为 None 则不输出到数据库
            txt_path: txt 文件路径，默认自动生成
            csv_path: csv 文件路径，默认自动生成
            table_formatter: 自定义表格格式化函数

        Returns:
            包含各输出结果的字典
        """
        results = {
            'txt': self.output_txt(txt_path, table_formatter),
            'csv': self.output_csv(csv_path)
        }

        if repo is not None:
            results['screening_id'] = self.output_sqlite(repo)

        return results

    def _generate_txt_content(self,
                              table_formatter: Optional[Callable[[List[StockData]], List[str]]] = None) -> List[str]:
        """
        生成 txt 内容（兼容现有格式）

        Args:
            table_formatter: 自定义表格格式化函数

        Returns:
            txt 内容行列表
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"{self.metadata.strategy_name}筛选结果")
        lines.append(f"生成时间: {self.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"筛选日期: {self.metadata.screen_date.strftime('%Y-%m-%d')}")

        if self.metadata.scan_scope:
            lines.append(f"扫描范围: {self.metadata.scan_scope}")

        lines.append(f"筛选条件: {self.metadata.filter_conditions}")
        lines.append(f"扫描数量: {self.metadata.scan_count} 只")
        lines.append(f"符合数量: {self.metadata.match_count} 只")
        lines.append("=" * 80)
        lines.append("")

        # 表格数据
        lines.append("=== 股票列表 ===")

        if table_formatter:
            lines.extend(table_formatter(self.stocks))
        else:
            lines.extend(self._format_table_rows())

        lines.append("")
        lines.append("=" * 80)

        return lines

    def _format_table_rows(self) -> List[str]:
        """
        格式化表格行（默认格式）

        Returns:
            表格行列表
        """
        rows = []
        for s in self.stocks:
            price_str = f"{s.screen_price:.2f}" if s.screen_price is not None else "N/A"
            score_str = f"{s.score:.2f}" if s.score is not None else "N/A"
            rows.append(f"{s.stock_code} {s.stock_name} 价格:{price_str} 评分:{score_str} {s.reason}")
        return rows

    def get_dataframe(self) -> pd.DataFrame:
        """
        获取股票数据的 DataFrame 表示

        Returns:
            包含所有股票数据的 DataFrame
        """
        rows = []
        for stock in self.stocks:
            row = {
                '股票代码': stock.stock_code,
                '股票名称': stock.stock_name,
                '筛选价格': stock.screen_price,
                '评分': stock.score,
                '筛选原因': stock.reason,
                **stock.extra_fields
            }
            rows.append(row)

        return pd.DataFrame(rows)

    def get_summary(self) -> Dict[str, Any]:
        """
        获取策略执行摘要

        Returns:
            包含摘要信息的字典
        """
        return {
            'strategy_name': self.metadata.strategy_name,
            'strategy_type': self.metadata.strategy_type,
            'screen_date': self.metadata.screen_date.strftime('%Y-%m-%d'),
            'generated_at': self.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'scan_count': self.metadata.scan_count,
            'match_count': self.metadata.match_count,
            'match_rate': f"{self.metadata.match_count / self.metadata.scan_count * 100:.2f}%" if self.metadata.scan_count > 0 else "0%",
            'filter_conditions': self.metadata.filter_conditions,
            'scan_scope': self.metadata.scan_scope
        }
