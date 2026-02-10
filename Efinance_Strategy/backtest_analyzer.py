# -*- coding: utf-8 -*-
"""
回测结果分析工具
解析掘金策略的交易日志，计算各项绩效指标
"""

import re
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple

# 修复Windows控制台中文乱码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


class BacktestAnalyzer:
    """回测结果分析器"""

    def __init__(self, initial_cash: float = 1000000, commission_rate: float = 0.0001):
        """
        初始化分析器

        Args:
            initial_cash: 初始资金
            commission_rate: 佣金比例
        """
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.trades = []
        self.portfolio_value = pd.DataFrame()

    def parse_log(self, log_text: str) -> List[Dict]:
        """
        解析交易日志

        日志格式:
        2024-08-01 09:30:00+08:00:标的：SHSE.600011，操作：以限价开多仓，委托价格：7.5651，目标仓位：8.00%
        """
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?标的：(\S+)，操作：以限价(\S+)，委托价格：([\d.]+)，目标仓位：([\d.]+)%'

        for match in re.finditer(pattern, log_text):
            date_str = match.group(1)
            symbol = match.group(2)
            action = match.group(3)  # 开多仓 or 平多仓
            price = float(match.group(4))
            target_percent = float(match.group(5))

            trade = {
                'datetime': pd.to_datetime(date_str),
                'date': pd.to_datetime(date_str).date(),
                'symbol': symbol,
                'action': action,
                'price': price,
                'target_percent': target_percent
            }
            self.trades.append(trade)

        self.trades = pd.DataFrame(self.trades)
        if not self.trades.empty:
            self.trades = self.trades.sort_values('datetime').reset_index(drop=True)

        return self.trades

    def calculate_position_value(self, price: float, percent: float, cash: float) -> Tuple[float, float]:
        """
        计算持仓价值和使用的现金

        Args:
            price: 股票价格
            percent: 目标仓位百分比
            cash: 当前可用现金

        Returns:
            (持仓价值, 使用的现金)
        """
        # 目标总资产 = cash / (1 - total_position_ratio)
        # 对于单个股票: value = target_percent / 100 * total_assets
        # 这里简化计算: 直接按目标百分比分配资金

        total_assets = cash / 0.8  # 因为总仓位是80%
        position_value = total_assets * (percent / 100)
        return position_value, position_value * (1 + self.commission_rate)

    def calculate_returns(self) -> pd.DataFrame:
        """
        计算每日的持仓和收益率

        Returns:
            包含每日净值、收益率等的DataFrame
        """
        if self.trades.empty:
            return pd.DataFrame()

        # 获取所有交易日期
        dates = pd.date_range(start=self.trades['datetime'].min(),
                             end=self.trades['datetime'].max(),
                             freq='D')

        # 当前持仓: {symbol: {'price': buy_price, 'shares': shares, 'value': value}}
        positions = {}
        cash = self.initial_cash
        daily_values = []

        for date in dates:
            # 当日的交易
            day_trades = self.trades[self.trades['datetime'].dt.date == date.date()]

            for _, trade in day_trades.iterrows():
                symbol = trade['symbol']
                action = trade['action']
                price = trade['price']
                percent = trade['target_percent']

                if action == '开多仓':  # 买入
                    position_value, cost = self.calculate_position_value(price, percent, cash)
                    shares = position_value / price
                    cash -= cost

                    positions[symbol] = {
                        'buy_price': price,
                        'shares': shares,
                        'value': position_value
                    }

                elif action == '平多仓':  # 卖出
                    if symbol in positions:
                        sell_value = positions[symbol]['shares'] * price
                        cash += sell_value * (1 - self.commission_rate)
                        del positions[symbol]

            # 计算当日总资产
            total_value = cash
            for pos in positions.values():
                # 这里使用买入价作为基准（实际应该用当日收盘价）
                # 由于日志中没有每日收盘价，我们用买入价代替
                total_value += pos['value']

            daily_values.append({
                'date': date,
                'cash': cash,
                'position_value': total_value - cash,
                'total_value': total_value,
                'return': (total_value - self.initial_cash) / self.initial_cash
            })

        self.portfolio_value = pd.DataFrame(daily_values)
        return self.portfolio_value

    def calculate_metrics(self) -> Dict:
        """
        计算各项绩效指标

        Returns:
            包含各项指标的字典
        """
        if self.portfolio_value.empty:
            self.calculate_returns()

        df = self.portfolio_value

        # 总收益率
        total_return = df['return'].iloc[-1]

        # 年化收益率
        days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

        # 每日收益率
        df['daily_return'] = df['total_value'].pct_change().fillna(0)

        # 年化波动率
        annual_volatility = df['daily_return'].std() * np.sqrt(252) if len(df) > 1 else 0

        # 夏普比率 (假设无风险利率为3%)
        risk_free_rate = 0.03
        sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility if annual_volatility > 0 else 0

        # 最大回撤
        df['cummax'] = df['total_value'].cummax()
        df['drawdown'] = (df['total_value'] - df['cummax']) / df['cummax']
        max_drawdown = df['drawdown'].min()

        # 胜率计算
        win_trades = 0
        loss_trades = 0
        total_profit = 0
        total_loss = 0

        symbols = self.trades['symbol'].unique()
        for symbol in symbols:
            symbol_trades = self.trades[self.trades['symbol'] == symbol].sort_values('datetime')

            i = 0
            while i < len(symbol_trades) - 1:
                if symbol_trades.iloc[i]['action'] == '开多仓' and symbol_trades.iloc[i+1]['action'] == '平多仓':
                    buy_price = symbol_trades.iloc[i]['price']
                    sell_price = symbol_trades.iloc[i+1]['price']
                    profit_pct = (sell_price - buy_price) / buy_price

                    if profit_pct > 0:
                        win_trades += 1
                        total_profit += profit_pct
                    else:
                        loss_trades += 1
                        total_loss += abs(profit_pct)
                    i += 2
                else:
                    i += 1

        total_trades = win_trades + loss_trades
        win_rate = win_trades / total_trades if total_trades > 0 else 0

        # 盈亏比
        profit_loss_ratio = total_profit / total_loss if total_loss > 0 else 0

        # 交易次数
        trade_count = len(self.trades) // 2  # 每次开仓+平仓算一笔

        # 最终资产
        final_value = df['total_value'].iloc[-1]

        return {
            'initial_cash': self.initial_cash,
            'final_value': final_value,
            'total_profit': final_value - self.initial_cash,
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'win_trades': win_trades,
            'loss_trades': loss_trades,
            'total_trades': total_trades,
            'trade_count': trade_count,
            'backtest_days': days
        }

    def print_report(self, metrics: Dict = None):
        """打印分析报告"""
        if metrics is None:
            metrics = self.calculate_metrics()

        print("\n" + "="*60)
        print("                    回测结果分析报告")
        print("="*60)

        print("\n【基本信息】")
        print(f"  初始资金: CNY {metrics['initial_cash']:,.2f}")
        print(f"  最终资产: CNY {metrics['final_value']:,.2f}")
        print(f"  总盈利:   CNY {metrics['total_profit']:,.2f}")
        print(f"  回测天数: {metrics['backtest_days']} 天")

        print("\n【收益指标】")
        print(f"  总收益率:     {metrics['total_return']*100:.2f}%")
        print(f"  年化收益率:   {metrics['annual_return']*100:.2f}%")
        print(f"  年化波动率:   {metrics['annual_volatility']*100:.2f}%")

        print("\n【风险指标】")
        print(f"  最大回撤:     {metrics['max_drawdown']*100:.2f}%")
        print(f"  夏普比率:     {metrics['sharpe_ratio']:.2f}")

        print("\n【交易统计】")
        print(f"  总交易次数:   {metrics['trade_count']} 笔")
        print(f"  盈利次数:     {metrics['win_trades']} 笔")
        print(f"  亏损次数:     {metrics['loss_trades']} 笔")
        print(f"  胜率:         {metrics['win_rate']*100:.2f}%")
        print(f"  盈亏比:       {metrics['profit_loss_ratio']:.2f}")

        # 当前持仓
        if not self.trades.empty:
            current_positions = self.get_current_positions()
            if current_positions:
                print("\n【当前持仓】")
                print(f"  {'股票代码':<15} {'买入日期':<12} {'买入价格':<10}")
                print("  " + "-"*50)
                for pos in current_positions:
                    print(f"  {pos['symbol']:<15} {pos['date'].strftime('%Y-%m-%d'):<12} CNY {pos['price']:<10.2f}")

        print("\n" + "="*60 + "\n")

    def get_current_positions(self) -> List[Dict]:
        """获取当前持仓"""
        if self.trades.empty:
            return []

        # 最后的买入操作就是当前持仓
        buy_trades = self.trades[self.trades['action'] == '开多仓']
        sell_trades = self.trades[self.trades['action'] == '平多仓']

        current = []
        for symbol in buy_trades['symbol'].unique():
            symbol_buys = buy_trades[buy_trades['symbol'] == symbol]
            symbol_sells = sell_trades[sell_trades['symbol'] == symbol]

            if len(symbol_buys) > len(symbol_sells):
                last_buy = symbol_buys.iloc[-1]
                current.append({
                    'symbol': symbol,
                    'date': last_buy['datetime'],
                    'price': last_buy['price']
                })

        return current

    def export_to_csv(self, filename: str = 'backtest_results.csv'):
        """导出结果到CSV"""
        if self.portfolio_value.empty:
            self.calculate_returns()

        self.portfolio_value.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"结果已导出到: {filename}")


def main():
    """主函数"""
    # 示例日志文本（实际使用时可以从文件读取）
    log_text = """
    2024-08-01 09:30:00+08:00:标的：SHSE.600011，操作：以限价开多仓，委托价格：7.5651，目标仓位：8.00%
    2024-08-01 09:30:00+08:00:标的：SHSE.600938，操作：以限价开多仓，委托价格：27.2578，目标仓位：8.00%
    2024-09-02 09:30:00+08:00:标的：SHSE.600011，操作：以限价平多仓，委托价格：6.6785，目标仓位：0.00%
    """

    # 从文件读取日志
    import sys
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
        # 尝试多种编码
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_text = f.read()
        except UnicodeDecodeError:
            with open(log_file, 'r', encoding='gbk') as f:
                log_text = f.read()
    else:
        # 如果没有提供文件，尝试读取默认日志文件
        import os
        log_file = 'backtest_log.txt'
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_text = f.read()
            except UnicodeDecodeError:
                with open(log_file, 'r', encoding='gbk') as f:
                    log_text = f.read()
        else:
            print("用法: python backtest_analyzer.py <日志文件路径>")
            print("或者将日志保存到 backtest_log.txt")
            return

    # 创建分析器
    analyzer = BacktestAnalyzer(initial_cash=1000000, commission_rate=0.0001)

    # 解析日志
    print("正在解析交易日志...")
    analyzer.parse_log(log_text)
    print(f"解析完成，共 {len(analyzer.trades)} 条交易记录")

    # 计算指标
    print("正在计算绩效指标...")
    metrics = analyzer.calculate_metrics()

    # 打印报告
    analyzer.print_report(metrics)

    # 导出结果
    analyzer.export_to_csv('backtest_daily_values.csv')


if __name__ == '__main__':
    main()
