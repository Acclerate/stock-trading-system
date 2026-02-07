# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import datetime
import pandas as pd
import numpy as np

"""
示例策略仅供参考，不建议直接实盘使用。

小市值策略，等权买入全A市场中市值最小的前N只股票，月初调仓换股
"""

def init(context):
    # 定义股票池数量
    context.num = 10
    # 定时任务，日频
    schedule(schedule_func=algo, date_rule='1d', time_rule='15:00:00')


def algo(context):
    # 当前时间
    now_str = context.now.strftime('%Y-%m-%d')
    # 获取上一个交易日
    last_date = get_previous_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]

    # 判断是否为每个月第一个交易日
    if context.now.month!=pd.Timestamp(last_date).month:
        # 获取A股代码（剔除停牌股、ST股、次新股（365天））
        all_stock,all_stock_str = get_normal_stocks(now_str)
        # 获取所有股票市值,并按升序排序
        fundamental = stk_get_daily_mktvalue_pt(symbols=all_stock, fields='tot_mv', trade_date=last_date, df=True).sort_values(by='tot_mv')
        # 获取前N只股票
        to_buy = list(fundamental.iloc[:context.num,:]['symbol'])
        print('本次股票池有股票数目: ', len(to_buy))

        positions = get_position()
        # 平不在标的池的股票（注：本策略交易以收盘价为交易价格，当调整定时任务时间时，需调整对应价格）
        for position in positions:
            symbol = position['symbol']
            if symbol not in to_buy:
                new_price = history_n(symbol=symbol, frequency='1d', count=1, end_time=now_str, fields='close', adjust=ADJUST_PREV, adjust_end_time=context.backtest_end_time, df=False)[0]['close']
                # # 当前价（tick数据，免费版本有时间权限限制；实时模式，返回当前最新 tick 数据，回测模式，返回回测当前时间点的最近一分钟的收盘价）
                # new_price = current(symbols=symbol)[0]['price']
                order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,position_side=PositionSide_Long,price=new_price)

        # 获取股票的权重(预留出2%资金，防止剩余资金不够手续费抵扣)
        percent = 0.98 / len(to_buy)
        # 买在标的池中的股票（注：本策略交易以收盘价为交易价格，当调整定时任务时间时，需调整对应价格）
        for symbol in to_buy:
            # 收盘价（日频数据）
            new_price = history_n(symbol=symbol, frequency='1d', count=1, end_time=now_str, fields='close', adjust=ADJUST_PREV, adjust_end_time=context.backtest_end_time, df=False)[0]['close']
            # # 当前价（tick数据，免费版本有时间权限限制；实时模式，返回当前最新 tick 数据，回测模式，返回回测当前时间点的最近一分钟的收盘价）
            # new_price = current(symbols=symbol)[0]['price']
            order_target_percent(symbol=symbol, percent=percent, order_type=OrderType_Limit,position_side=PositionSide_Long,price=new_price)


def on_order_status(context, order):
    # 标的代码
    symbol = order['symbol']
    # 委托价格
    price = order['price']
    # 委托数量
    volume = order['volume']
    # 目标仓位
    target_percent = order['target_percent']
    # 查看下单后的委托状态，等于3代表委托全部成交
    status = order['status']
    # 买卖方向，1为买入，2为卖出
    side = order['side']
    # 开平仓类型，1为开仓，2为平仓
    effect = order['position_effect']
    # 委托类型，1为限价委托，2为市价委托
    order_type = order['order_type']
    if status == 3:
        if effect == 1:
            if side == 1:
                side_effect = '开多仓'
            else:
                side_effect = '开空仓'
        else:
            if side == 1:
                side_effect = '平空仓'
            else:
                side_effect = '平多仓'
        order_type_word = '限价' if order_type==1 else '市价'
        print('{}:标的：{}，操作：以{}{}，委托价格：{}，委托数量：{}'.format(context.now,symbol,order_type_word,side_effect,price,volume))
       

def get_normal_stocks(date,new_days=365,skip_suspended=True, skip_st=True):
    """
    获取目标日期date的A股代码（剔除停牌股、ST股、次新股（365天））
    :param date：目标日期
    :param new_days:新股上市天数，默认为365天
    """
    date = pd.Timestamp(date).replace(tzinfo=None)
    # A股，剔除停牌和ST股票
    stocks_info = get_symbols(sec_type1=1010, sec_type2=101001, skip_suspended=skip_suspended, skip_st=skip_st, trade_date=date.strftime('%Y-%m-%d'), df=True)
    stocks_info['listed_date'] = stocks_info['listed_date'].apply(lambda x:x.replace(tzinfo=None))
    stocks_info['delisted_date'] = stocks_info['delisted_date'].apply(lambda x:x.replace(tzinfo=None))
    # 剔除次新股和退市股
    stocks_info = stocks_info[(stocks_info['listed_date']<=date-datetime.timedelta(days=new_days))&(stocks_info['delisted_date']>date)]
    all_stocks = list(stocks_info['symbol'])
    all_stocks_str = ','.join(all_stocks)
    return all_stocks,all_stocks_str


def on_backtest_finished(context, indicator):
    print('*'*50)
    print('回测已完成，请通过右上角“回测历史”功能查询详情。')


if __name__ == '__main__':
    '''
    strategy_id策略ID,由系统生成
    filename文件名,请与本文件名保持一致
    mode实时模式:MODE_LIVE回测模式:MODE_BACKTEST
    token绑定计算机的ID,可在系统设置-密钥管理中生成
    backtest_start_time回测开始时间
    backtest_end_time回测结束时间
    backtest_adjust股票复权方式不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
    backtest_initial_cash回测初始资金
    backtest_commission_ratio回测佣金比例
    backtest_slippage_ratio回测滑点比例
    backtest_match_mode市价撮合模式，以下一tick/bar开盘价撮合:0，以当前tick/bar收盘价撮合：1
    '''
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='{{token}}',
        backtest_start_time='2021-01-01 08:00:00',
        backtest_end_time='2021-12-31 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)