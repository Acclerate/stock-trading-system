"""
策略跟踪系统主程序
命令行工具入口
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from strategy_tracker.config import (
    STRATEGY_TYPES, OUTPUTS_DIR, HOLDING_PERIODS
)
from strategy_tracker.db.repository import get_repository
from strategy_tracker.db import init_db
from strategy_tracker.data import parse_directory, BenchmarkCollector
from strategy_tracker.core import ReturnCalculator, StatisticsCalculator
from strategy_tracker.report import ReportGenerator


class StrategyTrackerCLI:
    """策略跟踪系统命令行工具"""

    def __init__(self):
        self.repository = get_repository()
        self.benchmark_collector = BenchmarkCollector(self.repository)
        self.return_calculator = ReturnCalculator(self.repository)
        self.stats_calculator = StatisticsCalculator(self.repository)
        self.report_generator = ReportGenerator(self.repository)

    def init_database(self):
        """初始化数据库"""
        print("=" * 60)
        print("初始化数据库...")
        print("=" * 60)
        init_db.init_database()

    def parse_outputs(self, strategy_type: str = None):
        """
        解析输出目录中的文件

        Args:
            strategy_type: 策略类型，如果为None则解析所有类型
        """
        print("=" * 60)
        print("解析输出文件...")
        print("=" * 60)

        results = parse_directory(OUTPUTS_DIR)

        if not results:
            print("未找到可解析的输出文件")
            return

        # 过滤策略类型
        if strategy_type:
            results = [r for r in results if r['strategy_type'] == strategy_type]

        print(f"找到 {len(results)} 个输出文件")
        print()

        imported_count = 0
        skipped_count = 0

        for result in results:
            strategy_type = result['strategy_type']
            screen_date = result.get('screen_date')
            generated_at = result.get('generated_at')
            stocks = result.get('stocks', [])

            if not stocks:
                print(f"跳过: {result.get('file_path')} (无股票数据)")
                skipped_count += 1
                continue

            print(f"处理: {strategy_type} - {screen_date.strftime('%Y-%m-%d')} - {len(stocks)} 只股票")

            # 检查是否已存在
            existing = self.repository.get_screening_by_date_and_strategy(
                strategy_type, screen_date
            )

            if existing:
                print(f"  已存在，跳过")
                skipped_count += 1
                continue

            # 创建筛选记录
            screening_id = self.repository.create_screening_record(
                strategy_type=strategy_type,
                screen_date=screen_date,
                generated_at=generated_at or screen_date,
                total_stocks=len(stocks),
                strategy_params=result.get('strategy_params')
            )

            # 创建持仓记录
            positions_data = []
            for stock in stocks:
                positions_data.append({
                    'screening_id': screening_id,
                    'stock_code': stock['stock_code'],
                    'stock_name': stock.get('stock_name'),
                    'screen_date': stock.get('screen_date'),
                    'screen_price': stock.get('screen_price'),
                    'score': stock.get('score'),
                    'reason': stock.get('reason')
                })

            self.repository.bulk_create_positions(positions_data)
            print(f"  导入成功: {len(stocks)} 只股票")
            imported_count += 1

        print()
        print("=" * 60)
        print(f"导入完成: {imported_count} 个文件, 跳过 {skipped_count} 个文件")
        print("=" * 60)

    def calculate_returns(self, force_update: bool = False):
        """
        计算收益

        Args:
            force_update: 是否强制更新已有记录
        """
        print("=" * 60)
        print("计算持仓收益...")
        print("=" * 60)

        stats = self.return_calculator.calculate_all_holding_periods(
            check_date=datetime.now(),
            force_update=force_update
        )

        # 汇总统计
        total_success = sum(s['success'] for s in stats.values())
        total_failed = sum(s['failed'] for s in stats.values())

        print()
        print("=" * 60)
        print("计算完成")
        print(f"总计: 成功 {total_success}, 失败 {total_failed}")
        print("=" * 60)

    def update_benchmark(self, days: int = 30):
        """
        更新基准数据

        Args:
            days: 更新最近多少天的数据
        """
        print("=" * 60)
        print(f"更新基准数据 (最近 {days} 天)...")
        print("=" * 60)

        count = self.benchmark_collector.update_recent_benchmark(days)

        print()
        print("=" * 60)
        print(f"基准数据更新完成: {count} 条记录")
        print("=" * 60)

    def calculate_stats(self):
        """计算策略统计"""
        print("=" * 60)
        print("计算策略统计...")
        print("=" * 60)

        all_stats = self.stats_calculator.calculate_all_strategies()

        print()
        print("统计结果:")
        for strategy_type, stats in all_stats.items():
            strategy_name = STRATEGY_TYPES.get(strategy_type, strategy_type)
            print(f"  {strategy_name}:")
            for holding_days, data in stats.items():
                print(f"    {holding_days}天: {data['total_positions']} 个样本, "
                      f"胜率 {data.get('win_rate', 0):.2f}%, "
                      f"平均收益 {data.get('avg_return', 0):.2f}%")

        print()
        print("=" * 60)
        print("统计计算完成")
        print("=" * 60)

    def generate_report(
        self,
        strategy_types: list = None,
        output_file: str = None,
        export_csv: bool = False
    ):
        """
        生成报告

        Args:
            strategy_types: 策略类型列表
            output_file: 输出文件路径
            export_csv: 是否导出CSV
        """
        print("=" * 60)
        print("生成报告...")
        print("=" * 60)

        # 先计算最新统计
        self.calculate_stats()

        if export_csv:
            print()
            files = self.report_generator.export_to_csv(strategy_types)
            print()
            print(f"已导出 {len(files)} 个CSV文件")

        # 生成文本报告
        output_path = Path(output_file) if output_file else None
        report = self.report_generator.generate_text_report(strategy_types, output_path)

        print()
        print("=" * 60)
        print("报告生成完成")
        print("=" * 60)

        # 打印到控制台
        print()
        print(report)

    def update_all(self, force_update: bool = False):
        """
        执行完整更新流程

        Args:
            force_update: 是否强制更新已有记录
        """
        print()
        print("=" * 60)
        print("策略跟踪系统 - 完整更新")
        print("=" * 60)
        print()

        # 1. 更新基准数据
        self.update_benchmark(days=30)

        # 2. 解析输出文件
        self.parse_outputs()

        # 3. 计算收益
        self.calculate_returns(force_update=force_update)

        # 4. 计算统计
        self.calculate_stats()

        print()
        print("=" * 60)
        print("完整更新完成!")
        print("=" * 60)

    def show_status(self):
        """显示系统状态"""
        print("=" * 60)
        print("系统状态")
        print("=" * 60)
        print()

        # 统计各表记录数
        from sqlalchemy import text

        with self.repository.get_session() as session:
            tables = [
                'screening_records',
                'stock_positions',
                'return_records',
                'benchmark_data',
                'strategy_stats'
            ]

            print("数据库记录:")
            for table in tables:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"  {table}: {count} 条")

        print()

        # 显示最新的筛选记录
        print("最近的筛选记录:")
        records = self.repository.list_screening_records(limit=5)

        if not records:
            print("  暂无记录")
        else:
            for record in records:
                strategy_name = STRATEGY_TYPES.get(record.strategy_type, record.strategy_type)
                date_str = record.screen_date.strftime('%Y-%m-%d') if record.screen_date else 'N/A'
                print(f"  {strategy_name}: {date_str} - {record.total_stocks} 只股票")

    def comparison_report(self, output_file: str = None):
        """生成策略对比报告"""
        print("=" * 60)
        print("生成策略对比报告...")
        print("=" * 60)

        # 先计算最新统计
        self.calculate_stats()

        output_path = Path(output_file) if output_file else None
        report = self.report_generator.generate_comparison_report(output_path)

        print()
        print("=" * 60)
        print("对比报告生成完成")
        print("=" * 60)

        print()
        print(report)


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description='股票策略表现跟踪系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python -m strategy_tracker.main --init-db           # 初始化数据库
  python -m strategy_tracker.main --parse-all         # 解析所有输出文件
  python -m strategy_tracker.main --calculate         # 计算收益
  python -m strategy_tracker.main --report            # 生成报告
  python -m strategy_tracker.main --update-all        # 完整更新
  python -m strategy_tracker.main --status            # 查看状态
        '''
    )

    parser.add_argument('--init-db', action='store_true',
                        help='初始化数据库')
    parser.add_argument('--parse-all', action='store_true',
                        help='解析所有输出文件')
    parser.add_argument('--parse', type=str, metavar='STRATEGY',
                        help='解析指定策略的输出文件')
    parser.add_argument('--calculate', action='store_true',
                        help='计算持仓收益')
    parser.add_argument('--force', action='store_true',
                        help='强制更新已有记录')
    parser.add_argument('--update-benchmark', action='store_true',
                        help='更新基准数据')
    parser.add_argument('--stats', action='store_true',
                        help='计算策略统计')
    parser.add_argument('--report', action='store_true',
                        help='生成报告')
    parser.add_argument('--export-csv', action='store_true',
                        help='导出CSV格式报告')
    parser.add_argument('--output', type=str, metavar='FILE',
                        help='报告输出文件路径')
    parser.add_argument('--update-all', action='store_true',
                        help='执行完整更新流程')
    parser.add_argument('--status', action='store_true',
                        help='显示系统状态')
    parser.add_argument('--compare', action='store_true',
                        help='生成策略对比报告')

    args = parser.parse_args()

    # 创建CLI实例
    cli = StrategyTrackerCLI()

    try:
        if args.init_db:
            cli.init_database()

        elif args.parse_all or args.parse:
            cli.parse_outputs(args.parse)

        elif args.calculate:
            cli.calculate_returns(force_update=args.force)

        elif args.update_benchmark:
            cli.update_benchmark()

        elif args.stats:
            cli.calculate_stats()

        elif args.report or args.export_csv:
            cli.generate_report(
                strategy_types=None,
                output_file=args.output,
                export_csv=args.export_csv
            )

        elif args.update_all:
            cli.update_all(force_update=args.force)

        elif args.status:
            cli.show_status()

        elif args.compare:
            cli.comparison_report(args.output)

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
