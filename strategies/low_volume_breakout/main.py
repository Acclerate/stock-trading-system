# -*- coding: utf-8 -*-
"""
低位放量突破策略 - 主程序

策略入口，负责：
1. 解析命令行参数
2. 获取股票池
3. 并发处理股票分析
4. 生成输出报告
"""
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from data.data_resilient import DataResilient
from data.cache_manager import CacheManager
from data.diggold_data import DiggoldDataSource

# 处理相对导入和绝对导入
try:
    # 尝试相对导入（作为模块运行时）
    from .config import StrategyConfig
    from .stock_pool import StockPoolManager
    from .indicators import IndicatorCalculator
    from .signals import SignalGenerator, SignalResult, SignalType
except ImportError:
    # 回退到绝对导入（直接运行时）
    from strategies.low_volume_breakout.config import StrategyConfig
    from strategies.low_volume_breakout.stock_pool import StockPoolManager
    from strategies.low_volume_breakout.indicators import IndicatorCalculator
    from strategies.low_volume_breakout.signals import SignalGenerator, SignalResult, SignalType


class LowVolumeBreakoutStrategy:
    """低位放量突破策略主类"""

    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        初始化策略

        Args:
            config: 策略配置
        """
        self.config = config or StrategyConfig()
        self.stock_pool_manager = StockPoolManager(self.config)
        self.signal_generator = SignalGenerator(self.config)
        self.results: List[SignalResult] = []

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        获取单个股票的历史数据

        Args:
            symbol: 股票代码（掘金格式 SHSE.600XXX）
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            OHLCV数据DataFrame
        """
        try:
            # 直接使用掘金SDK的history_n函数获取最近N条数据
            try:
                from gm.api import history_n

                # 转换日期格式 YYYYMMDD -> YYYY-MM-DD
                end_date_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

                # 掘金格式的股票代码
                diggold_symbol = symbol  # 已经是掘金格式

                # 获取最近350条数据（确保有足够的数据）
                df = history_n(
                    symbol=diggold_symbol,
                    frequency='1d',
                    count=self.config.data_period + 50,  # 多取一些确保有足够数据
                    end_time=end_date_fmt,
                    adjust=1,  # 前复权
                    df=True
                )

                if df is None or df.empty:
                    return None

                # 处理日期列
                if 'eob' in df.columns:
                    df['date'] = pd.to_datetime(df['eob'])
                    df = df.drop(columns=['eob'])
                elif 'bob' in df.columns:
                    df['date'] = pd.to_datetime(df['bob'])
                    df = df.drop(columns=['bob'])

                if 'date' in df.columns:
                    df.set_index('date', inplace=True)

                # 确保数据长度足够
                if len(df) < self.config.min_data_points:
                    return None

                return df

            except ImportError:
                # 如果掘金SDK不可用，回退到DataResilient
                code = symbol.replace('SHSE.', '').replace('SZSE.', '')

                df = DataResilient.fetch_stock_data(
                    symbol=code,
                    start_date=start_date,
                    end_date=end_date,
                    use_cache=True
                )

                if df is None or df.empty:
                    return None

                # 确保数据长度足够
                if len(df) < self.config.min_data_points:
                    return None

                return df

        except Exception as e:
            # 只打印前几个错误，避免刷屏
            if not hasattr(self, '_error_count'):
                self._error_count = 0
            self._error_count += 1
            if self._error_count <= 3:
                print(f"获取 {symbol} 数据失败: {e}")

            return None

    def analyze_single_stock(self, symbol: str, end_date: str) -> Optional[SignalResult]:
        """
        分析单个股票

        Args:
            symbol: 股票代码
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            信号结果
        """
        # 计算开始日期
        start_date = (pd.Timestamp(end_date) - pd.Timedelta(days=self.config.data_period)).strftime('%Y%m%d')
        end_date_num = end_date.replace('-', '')

        # 获取历史数据
        df = self.fetch_stock_data(symbol, start_date, end_date_num)

        if df is None:
            return None

        if df.empty:
            return None

        if len(df) < self.config.min_data_points:
            return None

        # 获取市值
        market_cap = self.stock_pool_manager.get_market_cap(symbol)

        # 生成信号
        result = self.signal_generator.generate_signal(symbol, df, market_cap)

        return result

    def analyze_stocks(self, stock_pool: List[str], end_date: str,
                      show_progress: bool = True) -> List[SignalResult]:
        """
        并发分析股票池

        Args:
            stock_pool: 股票代码列表
            end_date: 结束日期
            show_progress: 是否显示进度

        Returns:
            信号结果列表
        """
        results = []
        total = len(stock_pool)
        failed = 0
        no_data_count = 0  # 数据不足的计数

        print(f"\n开始分析 {total} 只股票（并发数: {self.config.max_workers}）...")

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # 提交任务
            futures = {
                executor.submit(self.analyze_single_stock, symbol, end_date): symbol
                for symbol in stock_pool
            }

            # 处理结果
            completed = 0
            for future in as_completed(futures):
                symbol = futures[future]
                completed += 1

                try:
                    result = future.result(timeout=30)
                    if result is not None:
                        results.append(result)
                    else:
                        no_data_count += 1

                    # 进度显示
                    if show_progress and completed % 50 == 0:
                        buy_count = sum(1 for r in results if r.signal_type == SignalType.BUY)
                        wait_count = sum(1 for r in results if r.signal_type == SignalType.WAIT)
                        print(f"进度: {completed}/{total} ({completed/total*100:.1f}%) - "
                              f"买入: {buy_count}, 观望: {wait_count}, 无数据: {no_data_count}")

                except Exception as e:
                    failed += 1
                    if failed <= 5:  # 只打印前5个错误
                        print(f"分析 {symbol} 失败: {e}")

        print(f"\n分析完成: 成功 {len(results)}, 失败 {failed}, 无数据: {no_data_count}")

        # 如果所有股票都没有数据，打印调试信息
        if len(results) == 0 and no_data_count > 0:
            print(f"\n警告: 所有 {no_data_count} 只股票都没有足够的数据进行分析")
            print(f"可能原因:")
            print(f"  1. 请求的日期范围 ({end_date}) 没有交易数据")
            print(f"  2. 数据长度不足 {self.config.min_data_points} 天")
            print(f"  3. 网络或数据源问题")

        # 按得分排序
        results.sort(key=lambda x: x.score, reverse=True)

        self.results = results
        return results

    def format_output(self, results: List[SignalResult]) -> str:
        """
        格式化输出结果

        Args:
            results: 信号结果列表

        Returns:
            格式化的输出字符串
        """
        lines = []
        lines.append("=" * 100)
        lines.append("低位放量突破策略 - 筛选结果")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 100)
        lines.append("")

        # 策略参数
        lines.append("【策略参数】")
        for key, value in self.config.get_display_params().items():
            lines.append(f"  {key}: {value}")
        lines.append("")

        # 统计结果
        buy_signals = [r for r in results if r.signal_type == SignalType.BUY]
        wait_signals = [r for r in results if r.signal_type == SignalType.WAIT]

        lines.append("【筛选统计】")
        lines.append(f"  分析总数: {len(results)}")
        lines.append(f"  买入信号: {len(buy_signals)}")
        lines.append(f"  观望: {len(wait_signals)}")
        lines.append("")

        # Top N 结果
        top_results = buy_signals[:self.config.top_n] if buy_signals else results[:self.config.top_n]

        lines.append(f"【Top {len(top_results)} 结果】")
        lines.append("")

        # 表头
        header = f"{'排名':<6}{'代码':<15}{'名称':<12}{'市值':<10}{'价格':<10}{'价位%':<10}{'放量':<10}{'趋势':<10}{'得分':<8}{'判定依据'}"
        lines.append(header)
        lines.append("-" * 110)

        # 数据行
        for idx, result in enumerate(top_results, 1):
            symbol_short = result.symbol.replace('SHSE.', '').replace('SZSE.', '')

            # 获取股票名称（如果有的话）
            stock_name = self._get_stock_name(result.symbol)

            line = f"{idx:<6}{result.symbol:<15}{stock_name:<12}"

            if result.market_cap:
                line += f"{result.market_cap:<10.1f}"
            else:
                line += f"{'N/A':<10}"

            line += f"{result.indicators.get('close', 0):<10.2f}"
            line += f"{result.indicators.get('price_position', 0):<10.1%}"
            line += f"{result.indicators.get('volume_expansion', 0):<10.2f}"
            line += f"{result.indicators.get('trend_strength', 0):<10.1%}"
            line += f"{result.score:<8.1f}"
            line += f"{' + '.join(result.reasons)}"

            lines.append(line)

        lines.append("")
        lines.append("=" * 100)

        return "\n".join(lines)

    def _get_stock_name(self, symbol: str) -> str:
        """
        获取股票名称

        Args:
            symbol: 股票代码

        Returns:
            股票名称
        """
        try:
            # 简单的代码到名称映射（可根据需要扩展）
            # 这里可以使用掘金SDK的get_symbol_infos获取
            return ""
        except:
            return ""

    def save_results(self, output: str, filename: Optional[str] = None) -> str:
        """
        保存结果到文件

        Args:
            output: 输出内容
            filename: 文件名，默认使用时间戳

        Returns:
            保存的文件路径
        """
        # 创建输出目录
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        if filename is None:
            filename = f"stock_pool_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        filepath = output_dir / filename

        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)

        return str(filepath)

    def run(self, end_date: Optional[str] = None) -> List[SignalResult]:
        """
        运行策略

        Args:
            end_date: 结束日期 (YYYY-MM-DD)，默认为当前日期

        Returns:
            信号结果列表
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        print("=" * 70)
        print("低位放量突破策略 v1.0")
        print("=" * 70)

        # 初始化缓存
        CacheManager.initialize()

        # 初始化掘金SDK
        try:
            DiggoldDataSource.init()
        except:
            print("警告: 掘金SDK初始化失败，部分功能可能受限")

        # 步骤1: 获取股票池
        print(f"\n【步骤1】获取股票池")
        stock_pool = self.stock_pool_manager.get_stock_pool(end_date)

        if not stock_pool:
            print("未获取到股票池，退出")
            return []

        # 步骤2: 分析股票
        print(f"\n【步骤2】分析股票")
        results = self.analyze_stocks(stock_pool, end_date)

        if not results:
            print("未获得任何分析结果")
            return []

        # 步骤3: 格式化输出
        print(f"\n【步骤3】生成报告")
        output = self.format_output(results)

        # 打印到控制台
        print("\n" + output)

        # 步骤4: 保存到文件
        filepath = self.save_results(output)
        print(f"\n报告已保存至: {filepath}")

        print("\n策略执行完成！")

        return results


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='低位放量突破策略 - 寻找长期低位震荡后逐步放量的中小盘股票'
    )

    # 策略参数
    parser.add_argument('--min-cap', type=float, default=20.0,
                       help='最小市值（亿元），默认20亿')
    parser.add_argument('--max-cap', type=float, default=200.0,
                       help='最大市值（亿元），默认200亿')
    parser.add_argument('--low-threshold', type=float, default=0.6,
                       help='低位阈值（当前价格/250日最高价），默认0.6')
    parser.add_argument('--volume-ratio', type=float, default=1.5,
                       help='放量倍数（5日均量/20日均量），默认1.5')

    # 数据参数
    parser.add_argument('--data-period', type=int, default=300,
                       help='获取历史数据天数，默认300天')
    parser.add_argument('--end-date', type=str, default=None,
                       help='结束日期（YYYY-MM-DD），默认为今天')

    # 并发参数
    parser.add_argument('--max-workers', type=int, default=8,
                       help='并发处理线程数，默认8')

    # 输出参数
    parser.add_argument('--top-n', type=int, default=50,
                       help='输出Top N股票，默认50')
    parser.add_argument('--output-dir', type=str, default='outputs/low_volume_breakout',
                       help='输出目录，默认outputs/low_volume_breakout')

    return parser.parse_args()


def main():
    """主程序入口"""
    # 解析命令行参数
    args = parse_arguments()

    # 创建配置
    config = StrategyConfig.from_args(
        min_cap=args.min_cap,
        max_cap=args.max_cap,
        low_threshold=args.low_threshold,
        volume_ratio=args.volume_ratio,
        data_period=args.data_period,
        max_workers=args.max_workers,
        top_n=args.top_n,
    )

    # 设置输出目录
    config.output_dir = args.output_dir

    # 运行策略
    strategy = LowVolumeBreakoutStrategy(config)
    strategy.run(end_date=args.end_date)


if __name__ == '__main__':
    main()
