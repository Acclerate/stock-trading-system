# coding=utf-8
"""
掘金SDK事件驱动实时监控策略

使用掘金SDK的事件驱动模式实现多股票实时监控。
通过 subscribe() 订阅数据，on_bar() 处理K线推送事件。

运行方式：
1. 在掘金终端中创建策略
2. 设置 mode=MODE_LIVE（实时模式）或 MODE_BACKTEST（回测模式）
3. 运行策略

功能：
- 多股票同时监控
- 实时技术指标计算
- 买卖信号提醒
- 信号日志记录
"""

from __future__ import print_function, absolute_import, unicode_literals

from gm.api import *
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realtime_monitor.indicator_engine import IndicatorEngine
from realtime_monitor.signal_alert import SignalAlert
from realtime_monitor.monitor_config import load_watchlist
from data.diggold_data import DiggoldDataSource

# 全局变量（在 init 中初始化）
indicator_engine = None
signal_alert = None
symbol_names = {}
signal_cache = {}


def init(context):
    """
    策略初始化

    - 加载自选股列表
    - 订阅多只股票
    - 初始化指标引擎和信号提醒
    """
    global indicator_engine, signal_alert, symbol_names, signal_cache

    print("=" * 60)
    print("🔄 掘金事件驱动实时监控策略初始化")
    print("=" * 60)

    # 加载自选股配置
    config_path = os.path.join(os.path.dirname(__file__), 'watchlist.yaml')

    try:
        watchlist = load_watchlist(config_path)
    except FileNotFoundError:
        print(f"⚠️ 配置文件不存在: {config_path}")
        print("使用默认股票列表...")
        watchlist = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '000858', 'name': '五粮液'},
        ]

    print(f"📋 加载了 {len(watchlist)} 只股票")

    # 转换为掘金格式代码
    symbols = []
    names = {}
    for stock in watchlist:
        diggold_symbol = DiggoldDataSource.convert_symbol_to_diggold(stock['symbol'])
        symbols.append(diggold_symbol)
        names[diggold_symbol] = stock['name']
        print(f"  - {stock['name']} ({diggold_symbol})")

    # 保存到全局变量
    context.symbols = symbols
    symbol_names = names

    # 初始化指标引擎（共享实例）
    indicator_engine = IndicatorEngine()

    # 初始化信号提醒
    signal_alert = SignalAlert(enable_console=True, enable_log=True)

    # 信号状态缓存
    signal_cache = {symbol: None for symbol in symbols}

    # 订阅数据（1分钟K线）
    subscribe(
        symbols=context.symbols,
        frequency='60s',
        count=120,  # 获取最近120根K线用于计算指标
        fields='symbol,eob,open,high,low,close,volume,amount'
    )

    print(f"\n✅ 已订阅 {len(context.symbols)} 只股票")
    print(f"📊 数据频率: 60s (1分钟)")
    print(f"📈 历史K线: 120根")
    print("=" * 60)


def on_bar(context, bars):
    """
    K线数据推送处理

    - 更新技术指标
    - 检测买卖信号
    - 触发信号提醒
    """
    global indicator_engine, signal_alert, symbol_names, signal_cache

    for bar in bars:
        symbol = bar['symbol']
        name = symbol_names.get(symbol, symbol)

        try:
            # 获取历史数据用于计算指标
            df = context.data(
                symbol=symbol,
                frequency='60s',
                count=120,
                fields='open,high,low,close,volume'
            )

            if df is None or df.empty:
                continue

            # 计算技术指标
            df = indicator_engine.calculate_all(df)

            if df is None or df.empty:
                continue

            # 生成信号
            signal = indicator_engine.generate_signal(df)

            # 检查信号变化
            prev_signal = signal_cache.get(symbol)
            current_signal_value = signal.get('signal')
            prev_signal_value = prev_signal.get('signal') if prev_signal else None

            if current_signal_value != prev_signal_value:
                # 发送提醒
                signal_alert.send_alert(
                    symbol=symbol,
                    name=name,
                    current_signal=signal,
                    prev_signal=prev_signal,
                    price=bar['close'],
                    timestamp=context.now
                )

                # 更新缓存
                signal_cache[symbol] = signal

        except Exception as e:
            print(f"⚠️ 处理 {symbol} 数据失败: {e}")


def on_tick(context, tick):
    """
    tick数据推送处理（可选）

    - 用于更精细的价格监控
    - 检测异常价格波动
    """
    # 暂不处理tick数据，如需启用可在此添加逻辑
    pass


def on_backtest_finished(context, indicator):
    """回测完成回调"""
    print("\n" + "=" * 60)
    print("📊 回测完成")
    print("=" * 60)
    print(indicator)
    print("=" * 60)


def on_order_status(context, order):
    """委托状态更新"""
    print(f"📝 委托状态更新: {order}")


def on_execution_report(context, exec_rpt):
    """成交回报"""
    print(f"💰 成交回报: {exec_rpt}")


def on_error(context, error):
    """错误处理"""
    print(f"❌ 策略错误: {error}")


if __name__ == '__main__':
    """
    启动事件驱动监控策略

    注意：此脚本需要在掘金终端环境中运行
    """
    from datetime import datetime
    from gm.api import run, MODE_LIVE, MODE_BACKTEST, ADJUST_PREV

    print("=" * 60)
    print("掘金事件驱动实时监控策略")
    print("=" * 60)
    print()
    print("运行方式：")
    print("1. 实时模式：mode=MODE_LIVE")
    print("2. 回测模式：mode=MODE_BACKTEST")
    print()
    print("请在掘金终端中运行此策略，或在终端中设置参数后启动。")
    print()
    print("示例回测参数：")
    print("  - 回测时间: 2024-01-01 至今")
    print("  - 复权方式: 前复权")
    print("  - 初始资金: 1000000")
    print("  - 佣金比例: 0.0001")
    print("  - 滑点比例: 0.0001")
    print("=" * 60)

    # 以下是运行策略的示例代码
    # 在实际使用时，需要在掘金终端中设置相应的参数
    run(
        strategy_id='realtime_monitor_v1',
        filename='jinfeng_event_driven.py',
        mode=MODE_BACKTEST,  # 改为 MODE_LIVE 实时运行
        token=None,  # 在终端中会自动获取
        backtest_start_time='2024-01-01 09:30:00',
        backtest_end_time=datetime.now().strftime('%Y-%m-%d 15:00:00'),
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001
    )
