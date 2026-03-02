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
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.trades = []
        self.portfolio_value = pd.DataFrame()

    def parse_log(self, log_text: str) -> List[Dict]:
        """
        解析交易日志
        兼容 限价/市价，兼容不同格式的时间戳
        """
        # 修复点：使用 (?:限价|市价) 来兼容两种订单类型，提取真正的操作(开多仓/平多仓)
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?标的：([a-zA-Z0-9.]+)，操作：以(?:限价|市价)(开多仓|平多仓|开空仓|平空仓)，委托价格：([\d.]+)，目标仓位：([\d.]+)%'

        for match in re.finditer(pattern, log_text):
            date_str = match.group(1)
            symbol = match.group(2)
            action = match.group(3)  # 开多仓 or 平多仓
            price = float(match.group(4))
            target_percent = float(match.group(5))

            # 将百分比值转换为小数形式（如100 -> 1.0, 4.27 -> 0.0427）
            target_percent_decimal = target_percent / 100.0

            trade = {
                'datetime': pd.to_datetime(date_str),
                'date': pd.to_datetime(date_str).date(),
                'symbol': symbol,
                'action': action,
                'price': price,
                'target_percent': target_percent_decimal  # 使用小数形式
            }
            self.trades.append(trade)

        self.trades = pd.DataFrame(self.trades)
        if not self.trades.empty:
            # 去重：日志可能重复输出
            self.trades = self.trades.drop_duplicates().sort_values('datetime').reset_index(drop=True)

        return self.trades

    def calculate_position_value(self, price: float, percent: float, cash: float) -> Tuple[float, float]:
        """
        计算持仓价值和使用的现金
        percent: 目标仓位占比（小数形式，如1.0表示100%，0.05表示5%）
        """
        if percent >= 0.99:  # 100%全仓，直接使用所有可用资金
            position_value = cash / (1 + self.commission_rate)
        else:  # 部分仓位，假设现金占总资产的(1-percent)，计算总资产
            total_assets = cash / (1 - percent) if percent < 1 else cash
            position_value = total_assets * percent
        return position_value, position_value * (1 + self.commission_rate)

    def calculate_returns(self) -> pd.DataFrame:
        """计算每日的持仓和收益率"""
        if self.trades.empty:
            return pd.DataFrame()

        dates = pd.date_range(start=self.trades['datetime'].min(),
                              end=self.trades['datetime'].max(),
                              freq='D')

        positions = {}  # {symbol: {'shares': float, 'buy_price': float}}
        cash = self.initial_cash
        daily_values = []

        def get_total_asset():
            """计算总资产（现金 + 持仓市值）"""
            total = cash
            for symbol, pos in positions.items():
                total += pos['shares'] * pos['buy_price']  # 使用买入价作为持仓价值
            return total

        for date in dates:
            day_trades = self.trades[self.trades['datetime'].dt.date == date.date()]

            for _, trade in day_trades.iterrows():
                symbol = trade['symbol']
                action = trade['action']
                price = trade['price']
                percent = trade['target_percent']  # 小数形式，如1.0表示100%

                if action == '开多仓':
                    # 计算总资产，然后按目标仓位比例买入
                    total_asset = get_total_asset()

                    if percent >= 0.99:  # 100%全仓，使用所有可用资金
                        buy_amount = cash / (1 + self.commission_rate)
                    else:  # 部分仓位
                        buy_amount = total_asset * percent
                        # 确保不超过可用资金
                        if buy_amount * (1 + self.commission_rate) > cash:
                            buy_amount = cash / (1 + self.commission_rate)

                    calc_price = price if price > 0 else 1.0
                    cost = buy_amount * (1 + self.commission_rate)
                    shares = buy_amount / calc_price

                    cash -= cost
                    positions[symbol] = {
                        'shares': shares,
                        'buy_price': calc_price
                    }

                elif action == '平多仓':
                    if symbol in positions:
                        calc_price = price if price > 0 else positions[symbol]['buy_price']
                        sell_value = positions[symbol]['shares'] * calc_price
                        cash += sell_value * (1 - self.commission_rate)
                        del positions[symbol]

            total_value = get_total_asset()
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
        """计算各项绩效指标"""
        if self.portfolio_value.empty:
            self.calculate_returns()

        df = self.portfolio_value

        if df.empty:
            return {
                'initial_cash': self.initial_cash, 'final_value': self.initial_cash, 'total_profit': 0,
                'total_return': 0, 'annual_return': 0, 'annual_volatility': 0, 'sharpe_ratio': 0,
                'max_drawdown': 0, 'win_rate': 0, 'profit_loss_ratio': 0, 'win_trades': 0,
                'loss_trades': 0, 'total_trades': 0, 'trade_count': 0, 'backtest_days': 0
            }

        total_return = df['return'].iloc[-1]
        days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

        df['daily_return'] = df['total_value'].pct_change().fillna(0)
        annual_volatility = df['daily_return'].std() * np.sqrt(252) if len(df) > 1 else 0

        risk_free_rate = 0.03
        sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility if annual_volatility > 0 else 0

        df['cummax'] = df['total_value'].cummax()
        df['drawdown'] = (df['total_value'] - df['cummax']) / df['cummax']
        max_drawdown = df['drawdown'].min()

        win_trades = 0
        loss_trades = 0
        total_profit = 0
        total_loss = 0

        symbols = self.trades['symbol'].unique()
        for symbol in symbols:
            symbol_trades = self.trades[self.trades['symbol'] == symbol].sort_values('datetime')
            
            # 使用更健壮的匹配逻辑：维护一个开仓队列
            buys = []
            for _, trade in symbol_trades.iterrows():
                if trade['action'] == '开多仓':
                    buys.append(trade['price'])
                elif trade['action'] == '平多仓' and buys:
                    buy_price = buys.pop(0)
                    sell_price = trade['price']
                    
                    # 避免市价单委托价格为0导致的计算错误
                    if buy_price <= 0 or sell_price <= 0:
                        continue
                        
                    profit_pct = (sell_price - buy_price) / buy_price
                    if profit_pct > 0:
                        win_trades += 1
                        total_profit += profit_pct
                    else:
                        loss_trades += 1
                        total_loss += abs(profit_pct)

        total_trades = win_trades + loss_trades
        win_rate = win_trades / total_trades if total_trades > 0 else 0
        profit_loss_ratio = total_profit / total_loss if total_loss > 0 else 0
        trade_count = len(self.trades) // 2

        final_value = df['total_value'].iloc[-1]

        return {
            'initial_cash': self.initial_cash, 'final_value': final_value,
            'total_profit': final_value - self.initial_cash, 'total_return': total_return,
            'annual_return': annual_return, 'annual_volatility': annual_volatility,
            'sharpe_ratio': sharpe_ratio, 'max_drawdown': max_drawdown, 'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio, 'win_trades': win_trades,
            'loss_trades': loss_trades, 'total_trades': total_trades, 'trade_count': trade_count,
            'backtest_days': days
        }

    def print_report(self, metrics: Dict = None):
        if metrics is None: metrics = self.calculate_metrics()
        print("\n" + "="*60 + "\n                    回测结果分析报告\n" + "="*60)
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

        if not self.trades.empty:
            current_positions = self.get_current_positions()
            if current_positions:
                print("\n【当前持仓】")
                print(f"  {'股票代码':<15} {'买入日期':<12} {'价格':<10}")
                print("  " + "-"*50)
                for pos in current_positions:
                    print(f"  {pos['symbol']:<15} {pos['date'].strftime('%Y-%m-%d'):<12} CNY {pos['price']:<10.2f}")
        print("\n" + "="*60 + "\n")

    def get_current_positions(self) -> List[Dict]:
        if self.trades.empty: return []
        current = []
        for symbol in self.trades['symbol'].unique():
            symbol_trades = self.trades[self.trades['symbol'] == symbol]
            buys = len(symbol_trades[symbol_trades['action'] == '开多仓'])
            sells = len(symbol_trades[symbol_trades['action'] == '平多仓'])
            if buys > sells:
                last_buy = symbol_trades[symbol_trades['action'] == '开多仓'].iloc[-1]
                current.append({'symbol': symbol, 'date': last_buy['datetime'], 'price': last_buy['price']})
        return current

    def export_to_csv(self, filename: str = 'backtest_results.csv'):
        if self.portfolio_value.empty: self.calculate_returns()
        self.portfolio_value.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"结果已导出到: {filename}")

def main():
    import sys, os
    log_text = ""
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
        try:
            with open(log_file, 'r', encoding='utf-8') as f: log_text = f.read()
        except UnicodeDecodeError:
            with open(log_file, 'r', encoding='gbk') as f: log_text = f.read()
    else:
        log_file = 'backtest_log_style_rotation_v3.txt'
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f: log_text = f.read()
            except UnicodeDecodeError:
                with open(log_file, 'r', encoding='gbk') as f: log_text = f.read()
        else:
            print("用法: python backtest_analyzer.py <日志文件路径>")
            return

    analyzer = BacktestAnalyzer(initial_cash=10000000, commission_rate=0.0001) # 修正为1000万匹配主策略
    print("正在解析交易日志...")
    analyzer.parse_log(log_text)
    print(f"解析完成，共 {len(analyzer.trades)} 条交易记录")
    print("正在计算绩效指标...")
    analyzer.print_report()
    analyzer.export_to_csv('backtest_daily_values.csv')

if __name__ == '__main__':
    main()