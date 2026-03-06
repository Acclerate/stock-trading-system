"""
报告生成器
生成策略表现报告和CSV导出
"""
import csv
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from strategy_tracker.db.repository import get_repository
from strategy_tracker.core.calculator import StatisticsCalculator
from strategy_tracker.config import STRATEGY_TYPES, HOLDING_PERIODS, OUTPUTS_DIR


class ReportGenerator:
    """报告生成器 - 生成文本报告和CSV导出"""

    def __init__(self, repository=None):
        """
        初始化报告生成器

        Args:
            repository: 数据库仓库实例
        """
        self.repository = repository or get_repository()
        self.stats_calculator = StatisticsCalculator(self.repository)

    def format_percentage(self, value: Optional[float], decimals: int = 2) -> str:
        """格式化百分比值"""
        if value is None:
            return "N/A"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.{decimals}f}%"

    def format_number(self, value: Optional[float], decimals: int = 2) -> str:
        """格式化数值"""
        if value is None:
            return "N/A"
        return f"{value:.{decimals}f}"

    def generate_text_report(
        self,
        strategy_types: Optional[List[str]] = None,
        output_file: Optional[Path] = None
    ) -> str:
        """
        生成文本格式报告

        Args:
            strategy_types: 策略类型列表，如果为None则生成所有策略
            output_file: 输出文件路径

        Returns:
            报告内容字符串
        """
        if strategy_types is None:
            strategy_types = list(STRATEGY_TYPES.keys())

        lines = []
        lines.append("=" * 120)
        lines.append("股票策略表现跟踪报告")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 120)
        lines.append("")

        for strategy_type in strategy_types:
            strategy_name = STRATEGY_TYPES.get(strategy_type, strategy_type)
            lines.extend(self._generate_strategy_section(strategy_type, strategy_name))
            lines.append("")

        # 添加说明
        lines.append("=" * 120)
        lines.append("指标说明:")
        lines.append("  - 持仓周期: 从筛选日到检查日的交易日天数")
        lines.append("  - 样本数: 该策略筛选出的股票数量")
        lines.append("  - 盈利数: 收益率为正的股票数量")
        lines.append("  - 胜率: 盈利数 / 样本数")
        lines.append("  - 平均收益: 所有股票的平均收益率")
        lines.append("  - 超额收益: 平均收益 - 基准收益(沪深300)")
        lines.append("=" * 120)

        report_content = "\n".join(lines)

        # 输出到文件
        if output_file:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"报告已保存至: {output_file}")

        return report_content

    def _generate_strategy_section(
        self,
        strategy_type: str,
        strategy_name: str
    ) -> List[str]:
        """生成单个策略的报告部分"""
        lines = []

        # 获取统计数据
        stats_data = self.stats_calculator.calculate_strategy_stats(strategy_type)

        if not stats_data:
            lines.append(f"【{strategy_name} 策略表现】")
            lines.append("暂无数据")
            return lines

        lines.append(f"【{strategy_name} 策略表现】")
        lines.append("")

        # 表头
        header = f"{'持仓周期':<8}{'样本数':<10}{'盈利数':<10}{'胜率':<12}{'平均收益':<14}" \
                 f"{'中位数收益':<14}{'最大收益':<14}{'最小收益':<14}{'超额收益':<12}"
        lines.append(header)
        lines.append("-" * 130)

        # 数据行
        for holding_days in sorted(stats_data.keys()):
            stats = stats_data[holding_days]

            period_str = f"{holding_days}天"
            total = stats.get('total_positions', 0)
            winning = stats.get('winning_positions', 0)
            win_rate = stats.get('win_rate', 0)
            avg_return = stats.get('avg_return', 0)
            median_return = stats.get('median_return', 0)
            max_return = stats.get('max_return', 0)
            min_return = stats.get('min_return', 0)
            excess_return = stats.get('avg_excess_return', 0)

            line = (
                f"{period_str:<8}"
                f"{total:<10}"
                f"{winning:<10}"
                f"{self.format_percentage(win_rate):<12}"
                f"{self.format_percentage(avg_return):<14}"
                f"{self.format_percentage(median_return):<14}"
                f"{self.format_percentage(max_return):<14}"
                f"{self.format_percentage(min_return):<14}"
                f"{self.format_percentage(excess_return):<12}"
            )
            lines.append(line)

        return lines

    def export_to_csv(
        self,
        strategy_types: Optional[List[str]] = None,
        output_dir: Optional[Path] = None
    ) -> List[Path]:
        """
        导出CSV格式报告

        Args:
            strategy_types: 策略类型列表
            output_dir: 输出目录

        Returns:
            导出的文件路径列表
        """
        if strategy_types is None:
            strategy_types = list(STRATEGY_TYPES.keys())

        if output_dir is None:
            output_dir = OUTPUTS_DIR / "reports"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exported_files = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 导出汇总报告
        summary_file = output_dir / f"strategy_summary_{timestamp}.csv"
        self._export_summary_csv(strategy_types, summary_file)
        exported_files.append(summary_file)

        # 导出各策略详细报告
        for strategy_type in strategy_types:
            detail_file = output_dir / f"{strategy_type}_detail_{timestamp}.csv"
            self._export_detail_csv(strategy_type, detail_file)
            exported_files.append(detail_file)

        return exported_files

    def _export_summary_csv(
        self,
        strategy_types: List[str],
        output_file: Path
    ):
        """导出汇总CSV"""
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            # 表头
            header = [
                '策略类型', '持仓周期', '样本数', '盈利数', '胜率(%)',
                '平均收益(%)', '中位数收益(%)', '最大收益(%)', '最小收益(%)',
                '平均基准收益(%)', '平均超额收益(%)'
            ]
            writer.writerow(header)

            # 数据行
            for strategy_type in strategy_types:
                strategy_name = STRATEGY_TYPES.get(strategy_type, strategy_type)
                stats_data = self.stats_calculator.calculate_strategy_stats(strategy_type)

                for holding_days in sorted(stats_data.keys()):
                    stats = stats_data[holding_days]

                    row = [
                        strategy_name,
                        f"{holding_days}天",
                        stats.get('total_positions', 0),
                        stats.get('winning_positions', 0),
                        self.format_number(stats.get('win_rate', 0), 2),
                        self.format_number(stats.get('avg_return', 0), 2),
                        self.format_number(stats.get('median_return', 0), 2),
                        self.format_number(stats.get('max_return', 0), 2),
                        self.format_number(stats.get('min_return', 0), 2),
                        self.format_number(stats.get('avg_benchmark_return', 0), 2),
                        self.format_number(stats.get('avg_excess_return', 0), 2),
                    ]
                    writer.writerow(row)

        print(f"汇总CSV已导出: {output_file}")

    def _export_detail_csv(
        self,
        strategy_type: str,
        output_file: Path
    ):
        """导出策略详细CSV"""
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            # 获取所有持仓和收益记录
            from strategy_tracker.db.models import StockPosition, ReturnRecord, ScreeningRecord
            from sqlalchemy import and_

            with self.repository.get_session() as session:
                query = session.query(
                    StockPosition, ReturnRecord, ScreeningRecord
                ).join(
                    ScreeningRecord, StockPosition.screening_id == ScreeningRecord.id
                ).outerjoin(
                    ReturnRecord, StockPosition.id == ReturnRecord.position_id
                ).filter(
                    ScreeningRecord.strategy_type == strategy_type
                ).order_by(
                    ScreeningRecord.screen_date.desc(),
                    StockPosition.stock_code
                )

                # 表头
                header = [
                    '筛选日期', '股票代码', '股票名称', '筛选价格',
                    '5天收益(%)', '5天基准(%)', '5天超额(%)',
                    '10天收益(%)', '10天基准(%)', '10天超额(%)',
                    '20天收益(%)', '20天基准(%)', '20天超额(%)',
                    '筛选原因'
                ]
                writer.writerow(header)

                # 数据行
                current_position = None
                row_data = {}

                for position, return_rec, screening in query.all():
                    if current_position != position.id:
                        # 写入上一行数据
                        if row_data:
                            writer.writerow([
                                row_data.get('screen_date', ''),
                                row_data.get('stock_code', ''),
                                row_data.get('stock_name', ''),
                                row_data.get('screen_price', ''),
                                row_data.get('r5_return', ''),
                                row_data.get('r5_benchmark', ''),
                                row_data.get('r5_excess', ''),
                                row_data.get('r10_return', ''),
                                row_data.get('r10_benchmark', ''),
                                row_data.get('r10_excess', ''),
                                row_data.get('r20_return', ''),
                                row_data.get('r20_benchmark', ''),
                                row_data.get('r20_excess', ''),
                                row_data.get('reason', ''),
                            ])

                        current_position = position.id
                        row_data = {
                            'screen_date': position.screen_date.strftime('%Y-%m-%d') if position.screen_date else '',
                            'stock_code': position.stock_code,
                            'stock_name': position.stock_name or '',
                            'screen_price': self.format_number(position.screen_price, 2) if position.screen_price else '',
                            'reason': position.reason or '',
                        }

                    # 添加收益记录
                    if return_rec:
                        prefix = f"r{return_rec.holding_days}_"
                        row_data[f"{prefix}return"] = self.format_number(return_rec.return_rate, 2)
                        row_data[f"{prefix}benchmark"] = self.format_number(return_rec.benchmark_return, 2)
                        row_data[f"{prefix}excess"] = self.format_number(return_rec.excess_return, 2)

                # 写入最后一行
                if row_data:
                    writer.writerow([
                        row_data.get('screen_date', ''),
                        row_data.get('stock_code', ''),
                        row_data.get('stock_name', ''),
                        row_data.get('screen_price', ''),
                        row_data.get('r5_return', ''),
                        row_data.get('r5_benchmark', ''),
                        row_data.get('r5_excess', ''),
                        row_data.get('r10_return', ''),
                        row_data.get('r10_benchmark', ''),
                        row_data.get('r10_excess', ''),
                        row_data.get('r20_return', ''),
                        row_data.get('r20_benchmark', ''),
                        row_data.get('r20_excess', ''),
                        row_data.get('reason', ''),
                    ])

        print(f"详细CSV已导出: {output_file}")

    def print_report_to_console(
        self,
        strategy_types: Optional[List[str]] = None
    ):
        """
        打印报告到控制台

        Args:
            strategy_types: 策略类型列表
        """
        report = self.generate_text_report(strategy_types)
        print("\n" + report)

    def generate_comparison_report(
        self,
        output_file: Optional[Path] = None
    ) -> str:
        """
        生成策略对比报告

        Args:
            output_file: 输出文件路径

        Returns:
            报告内容字符串
        """
        lines = []
        lines.append("=" * 140)
        lines.append("策略对比报告 - 按持仓周期")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 140)
        lines.append("")

        # 按持仓周期组织对比
        for holding_days in HOLDING_PERIODS:
            lines.append(f"【{holding_days}天持仓周期对比】")
            lines.append("")

            # 表头
            header = f"{'策略类型':<20}{'样本数':<10}{'胜率':<12}{'平均收益':<14}" \
                     f"{'中位数收益':<14}{'最大收益':<14}{'最小收益':<14}{'超额收益':<12}"
            lines.append(header)
            lines.append("-" * 130)

            # 获取各策略数据
            strategy_comparison = []

            for strategy_type, strategy_name in STRATEGY_TYPES.items():
                stats_data = self.stats_calculator.calculate_strategy_stats(strategy_type)

                if holding_days in stats_data:
                    stats = stats_data[holding_days]
                    strategy_comparison.append({
                        'name': strategy_name,
                        'total': stats.get('total_positions', 0),
                        'win_rate': stats.get('win_rate', 0),
                        'avg_return': stats.get('avg_return', 0),
                        'median_return': stats.get('median_return', 0),
                        'max_return': stats.get('max_return', 0),
                        'min_return': stats.get('min_return', 0),
                        'excess_return': stats.get('avg_excess_return', 0),
                    })

            # 按超额收益排序
            strategy_comparison.sort(key=lambda x: x['excess_return'] or 0, reverse=True)

            # 输出数据行
            for item in strategy_comparison:
                line = (
                    f"{item['name']:<20}"
                    f"{item['total']:<10}"
                    f"{self.format_percentage(item['win_rate']):<12}"
                    f"{self.format_percentage(item['avg_return']):<14}"
                    f"{self.format_percentage(item['median_return']):<14}"
                    f"{self.format_percentage(item['max_return']):<14}"
                    f"{self.format_percentage(item['min_return']):<14}"
                    f"{self.format_percentage(item['excess_return']):<12}"
                )
                lines.append(line)

            lines.append("")

        report_content = "\n".join(lines)

        if output_file:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"对比报告已保存至: {output_file}")

        return report_content
