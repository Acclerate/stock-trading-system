# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import datetime
import pandas as pd
import numpy as np

'''
示例策略仅供参考，不建议直接实盘使用。

日内回转交易是指投资者就同一个标的（如股票）在同一个交易日内各完成多次买进和卖出的行为
其目的为维持股票数量不变，降低股票成本
本策略以1分钟MACD为基础，金叉时买入，死叉时卖出，尾盘回转至初始仓位
'''


def init(context):
    # 设置标的股票
    context.all_symbols = ['SHSE.600000','SHSE.601963']
    # 用于判定第一个仓位是否成功开仓
    context.first = {symbol:0 for symbol in context.all_symbols}
    # 需要保持的总仓位
    context.total = 10000
    # 日内回转每次交易数量
    context.trade_n = 500
    # 使用的频率，60s为1分钟bar，300s为5分钟bar
    context.frequency = '60s'
    # 回溯数据长度（计算MACD)
    context.periods_time = 100
    # 订阅数据
    subscribe(symbols=context.all_symbols,
              frequency=context.frequency,
              count=context.periods_time,
              fields='symbol,eob,close')


def on_bar(context, bars):
    bar = bars[0]
    symbol = bar['symbol']
    # 配置底仓
    if context.first[symbol] == 0:
        context.first[symbol] = 1
        # 购买10000股浦发银行股票
        order_volume(symbol=symbol,
                     volume=context.total,
                     side=OrderSide_Buy,
                     order_type=OrderType_Market,
                     position_effect=PositionEffect_Open)
        print('{}：{}建底仓，以市价单开多仓{}股'.format(context.now, symbol, context.total))
        return

    # 获取持仓
    position = list(filter(lambda x:x['symbol']==symbol,get_position()))
    if len(position)==0:return

    # 可用仓位
    available_volume = position[0]['volume'] - position[0]['available_today']

    # 尾盘回转仓位
    if context.now.hour == 14 and context.now.minute >= 57 or context.now.hour == 15:
        if position[0]['volume'] != context.total:
            order_target_volume(symbol=symbol,
                                volume=context.total,
                                order_type=OrderType_Market,
                                position_side=PositionSide_Long)
    # 非尾盘时间，正常交易(首日不交易，可用仓位为0)
    elif available_volume > 0:
        # 调用收盘价
        close = context.data(symbol=symbol,
                             frequency=context.frequency,
                             count=context.periods_time,
                             fields='close')['close'].values
        # 计算MACD线
        macd = MACD(close)[-1]
        # MACD由负转正时,买入
        if macd[-2] <= 0 and macd[-1] > 0:
            order_volume(symbol=symbol,
                         volume=context.trade_n,
                         side=OrderSide_Buy,
                         order_type=OrderType_Market,
                         position_effect=PositionEffect_Open)

        # MACD由正转负时,卖出
        elif macd[-2] >= 0 and macd[
                -1] < 0 and available_volume >= context.trade_n:
            order_volume(symbol=symbol,
                         volume=context.trade_n,
                         side=OrderSide_Sell,
                         order_type=OrderType_Market,
                         position_effect=PositionEffect_Close)


def EMA(S: np.ndarray, N: int) -> np.ndarray:
    '''指数移动平均,为了精度 S>4*N  EMA至少需要120周期     
    alpha=2/(span+1)

    Args:
        S (np.ndarray): 时间序列
        N (int): 指标周期

    Returns:
        np.ndarray: EMA
    '''
    return pd.Series(S).ewm(span=N, adjust=False).mean().values


def MACD(CLOSE: np.ndarray,
         SHORT: int = 12,
         LONG: int = 26,
         M: int = 9) -> tuple:
    '''计算MACD
    EMA的关系，S取120日

    Args:
        CLOSE (np.ndarray): 收盘价时间序列
        SHORT (int, optional): ema 短周期. Defaults to 12.
        LONG (int, optional): ema 长周期. Defaults to 26.
        M (int, optional): macd 平滑周期. Defaults to 9.

    Returns:
        tuple: _description_
    '''
    DIF = EMA(CLOSE, SHORT) - EMA(CLOSE, LONG)
    DEA = EMA(DIF, M)
    MACD = (DIF - DEA) * 2
    return DIF, DEA, MACD


def on_order_status(context, order):
    # 标的代码
    symbol = order['symbol']
    # 委托价格
    price = order['price']
    # 委托数量
    volume = order['volume']
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
        order_type_word = '限价' if order_type == 1 else '市价'
        print('{}:标的：{}，操作：以{}{}，委托价格：{}，委托数量：{}'.format(
            context.now, symbol, order_type_word, side_effect, price, volume))


def on_backtest_finished(context, indicator):
    print('*' * 50)
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
    backtest_start_time = str(datetime.datetime.now() - datetime.timedelta(days=180))[:19]
    backtest_end_time = str(datetime.datetime.now())[:19]
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='{{token}}',
        backtest_start_time=backtest_start_time,
        backtest_end_time=backtest_end_time,
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=200000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
