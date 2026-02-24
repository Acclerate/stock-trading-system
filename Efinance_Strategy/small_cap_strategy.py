# -*- coding: utf-8 -*-
"""
小市值策略 v2.0

策略思路：等权买入全A市场中市值最小的前N只股票，月初调仓换股

核心逻辑：
1. 选股池：全A股剔除停牌、ST、次新股（默认365天）
2. 选股因子：总市值（tot_mv），选择市值最小的N只
3. 调仓频率：每月第一个交易日调仓
4. 仓位管理：等权配置，预留2%资金防止手续费不足
5. 风险控制：剔除退市风险股票

适用场景：
- 小盘股风格占优市场
- 流动性充裕环境
- 适合中长期持有

注意事项：
- 小市值股票流动性风险较高
- 需要关注退市风险
- 建议配合市场环境判断使用
"""

from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import os
import datetime
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 读取token
token = os.getenv('DIGGOLD_TOKEN')


def init(context):
    """
    初始化函数，设置策略参数
    """
    # 选股参数
    context.stock_num = 30  # 选择市值最小的30只股票（可调整：10-50）
    context.new_days = 365  # 剔除上市不足N天的次新股

    # 仓位管理
    context.cash_reserve = 0.02  # 预留2%资金用于手续费

    # 调仓参数
    context.rebalance_day = 1  # 每月第1个交易日调仓
    context.last_rebalance_month = 0  # 上次调仓月份

    # 选股池过滤参数
    context.skip_suspended = True  # 剔除停牌股
    context.skip_st = True  # 剔除ST股

    # 记录调仓信息
    context.rebalance_count = 0  # 调仓次数统计

    # 每个交易日执行
    schedule(schedule_func=algo, date_rule='1d', time_rule='15:00:00')


def algo(context):
    """
    主策略逻辑，每日执行
    """
    now = context.now
    now_str = now.strftime('%Y-%m-%d')

    # 获取上一个交易日
    last_day = get_previous_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]
    last_day_ts = pd.Timestamp(last_day)

    # 判断是否为每月第一个交易日
    current_month = now.month
    is_rebalance_day = (current_month != context.last_rebalance_month)

    if is_rebalance_day:
        context.last_rebalance_month = current_month
        context.rebalance_count += 1

        print('=' * 60)
        print('{}: 第{}次调仓，开始执行小市值策略'.format(now, context.rebalance_count))
        print('=' * 60)

        # 执行调仓
        rebalance(context, now, now_str, last_day)


def get_normal_stocks(context, date):
    """
    获取目标日期的A股代码（剔除停牌股、ST股、次新股）

    Args:
        context: 上下文对象
        date: 目标日期字符串

    Returns:
        list: 符合条件的股票代码列表
    """
    date = pd.Timestamp(date).replace(tzinfo=None)

    # 获取A股股票信息
    stocks_info = get_symbols(
        sec_type1=1010,
        sec_type2=101001,
        skip_suspended=context.skip_suspended,
        skip_st=context.skip_st,
        trade_date=date.strftime('%Y-%m-%d'),
        df=True
    )

    # 处理日期字段
    stocks_info['listed_date'] = stocks_info['listed_date'].apply(lambda x: x.replace(tzinfo=None))
    stocks_info['delisted_date'] = stocks_info['delisted_date'].apply(lambda x: x.replace(tzinfo=None))

    # 剔除次新股和退市股
    cutoff_date = date - datetime.timedelta(days=context.new_days)
    stocks_info = stocks_info[
        (stocks_info['listed_date'] <= cutoff_date) &
        (stocks_info['delisted_date'] > date)
    ]

    all_stocks = list(stocks_info['symbol'])

    print('可选股票池数量: {} (剔除次新股<{}天, 停牌, ST)'.format(
        len(all_stocks), context.new_days))

    return all_stocks


def select_small_caps(context, stock_pool, trade_date):
    """
    选择市值最小的N只股票

    Args:
        context: 上下文对象
        stock_pool: 股票池列表
        trade_date: 交易日期

    Returns:
        list: 选中的股票代码列表
    """
    # 获取市值数据
    fundamental = stk_get_daily_mktvalue_pt(
        symbols=stock_pool,
        fields='tot_mv',
        trade_date=trade_date,
        df=True
    ).sort_values(by='tot_mv')

    # 选择市值最小的N只
    selected = fundamental.head(context.stock_num)
    selected_list = selected['symbol'].tolist()

    # 打印选中股票信息
    print('\n选中的{}只小市值股票:'.format(len(selected_list)))
    print('-' * 60)
    for idx, row in selected.head(10).iterrows():
        print('  {}: 总市值 = {:.2f}亿元'.format(row['symbol'], row['tot_mv']))
    if len(selected_list) > 10:
        print('  ... (共{}只)'.format(len(selected_list)))

    # 统计信息
    print('\n市值统计:')
    print('  最小市值: {:.2f}亿元'.format(selected['tot_mv'].min()))
    print('  最大市值: {:.2f}亿元'.format(selected['tot_mv'].max()))
    print('  平均市值: {:.2f}亿元'.format(selected['tot_mv'].mean()))

    return selected_list


def rebalance(context, now, now_str, last_day):
    """
    调仓逻辑

    Args:
        context: 上下文对象
        now: 当前时间
        now_str: 当前时间字符串
        last_day: 上一个交易日字符串
    """
    # 1. 获取股票池
    stock_pool = get_normal_stocks(context, last_day)

    if not stock_pool:
        print('{}: 没有可用股票，保持空仓'.format(now))
        return

    # 2. 选股
    to_buy = select_small_caps(context, stock_pool, last_day)

    if not to_buy:
        print('{}: 没有选中任何股票，保持空仓'.format(now))
        return

    # 3. 获取当前持仓
    positions = get_position()
    current_positions = {p['symbol']: p for p in positions}

    # 4. 卖出不在新池中的股票
    sell_count = 0
    for symbol in list(current_positions.keys()):
        if symbol not in to_buy:
            new_price = history_n(
                symbol=symbol,
                frequency='1d',
                count=1,
                end_time=now_str,
                fields='close',
                adjust=ADJUST_PREV,
                adjust_end_time=context.backtest_end_time,
                df=False
            )[0]['close']

            order_target_percent(
                symbol=symbol,
                percent=0,
                order_type=OrderType_Limit,
                position_side=PositionSide_Long,
                price=new_price
            )
            sell_count += 1

    if sell_count > 0:
        print('\n卖出 {} 只不在新池中的股票'.format(sell_count))

    # 5. 买入新池中的股票（等权配置）
    buy_count = 0
    percent = (1 - context.cash_reserve) / len(to_buy)

    print('\n买入配置: 单股权重 = {:.2%}'.format(percent))

    for symbol in to_buy:
        # 跳过已持有的股票
        if symbol in current_positions:
            continue

        new_price = history_n(
            symbol=symbol,
            frequency='1d',
            count=1,
            end_time=now_str,
            fields='close',
            adjust=ADJUST_PREV,
            adjust_end_time=context.backtest_end_time,
            df=False
        )[0]['close']

        order_target_percent(
            symbol=symbol,
            percent=percent,
            order_type=OrderType_Limit,
            position_side=PositionSide_Long,
            price=new_price
        )
        buy_count += 1

    if buy_count > 0:
        print('买入 {} 只新选中的股票'.format(buy_count))

    print('\n调仓完成: 持仓股票数量 = {}'.format(len(to_buy)))
    print('=' * 60)


def on_order_status(context, order):
    """
    订单状态回调

    Args:
        context: 上下文对象
        order: 订单信息字典
    """
    symbol = order['symbol']
    price = order['price']
    volume = order['volume']
    target_percent = order['target_percent']
    status = order['status']
    side = order['side']
    effect = order['position_effect']
    order_type = order['order_type']

    if status == 3:  # 全部成交
        if effect == 1:  # 开仓
            side_effect = '开多仓' if side == 1 else '开空仓'
        else:  # 平仓
            side_effect = '平多仓' if side == 2 else '平空仓'

        order_type_word = '限价' if order_type == 1 else '市价'
        print('{}: {} | {}{} | 价格: {:.2f} | 数量: {} | 目标仓位: {:.2%}'.format(
            context.now, symbol, order_type_word, side_effect, price, volume, target_percent
        ))


def on_backtest_finished(context, indicator):
    """
    Backtest completion callback

    Args:
        context: Context object
        indicator: Backtest indicator dictionary
    """
    print('\n')
    print('*' * 60)
    print('Small Cap Strategy Backtest Completed')
    print('*' * 60)
    print('Final Capital: {:.2f}'.format(indicator['pnl_ratio']))
    print('Total Return: {:.2%}'.format(indicator['pnl_ratio'] / 100 - 1))
    print('Annual Return: {:.2%}'.format(indicator['pnl_ratio_annual']))
    print('Max Drawdown: {:.2%}'.format(indicator['max_drawdown'] / 100))
    print('Sharpe Ratio: {:.2f}'.format(indicator['sharp_ratio']))
    print('Rebalance Count: {}'.format(context.rebalance_count))
    print('*' * 60)
    print('Please check backtest history for detailed report')
    print('*' * 60)


if __name__ == '__main__':
    """
    主函数 - 执行回测

    参数说明：
    - strategy_id: 策略ID（系统生成）
    - filename: 文件名（与本文件名保持一致）
    - mode: 运行模式（MODE_LIVE实时 / MODE_BACKTEST回测）
    - token: 掘金账户token（从.env文件读取）
    - backtest_start_time: 回测开始时间
    - backtest_end_time: 回测结束时间
    - backtest_adjust: 复权方式（ADJUST_NONE不复权 / ADJUST_PREV前复权 / ADJUST_POST后复权）
    - backtest_initial_cash: 初始资金
    - backtest_commission_ratio: 佣金比例
    - backtest_slippage_ratio: 滑点比例
    - backtest_match_mode: 撮合模式（0下一tick开盘价 / 1当前bar收盘价）
    """
    run(
        strategy_id='small_cap_strategy_id',
        filename='small_cap_strategy.py',
        mode=MODE_BACKTEST,
        token=token,
        backtest_start_time='2024-01-01 08:00:00',
        backtest_end_time='2026-02-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1
    )
