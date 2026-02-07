# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *


"""
示例策略仅供参考，不建议直接实盘使用。

本策略采用布林线进行均值回归交易。当价格触及布林线上轨的时候进行卖出，当触及下轨的时候，进行买入。
"""


# 策略中必须有init方法
def init(context):
    # 设置布林线的三个参数
    context.maPeriod = 26  # 计算BOLL布林线中轨的参数
    context.stdPeriod = 26  # 计算BOLL 标准差的参数
    context.stdRange = 1  # 计算BOLL 上下轨和中轨距离的参数
    # 设置要进行回测的合约
    context.symbol = 'SHSE.600004'  # 订阅&交易标的, 此处订阅的是600004
    context.period = max(context.maPeriod, context.stdPeriod, context.stdRange) + 1  # 订阅数据滑窗长度
    # 订阅行情
    subscribe(symbols= context.symbol, frequency='1d', count=context.period)


def on_bar(context, bars):
    # 获取数据滑窗，只要在init里面有订阅，在这里就可以取的到，返回值是pandas.DataFrame
    data = context.data(symbol=context.symbol, frequency='1d', count=context.period, fields='close')

    ## 计算布林带
    # 标准差
    std = data['close'].rolling(context.stdPeriod).std()
    # 均值
    mean = data['close'].rolling(context.maPeriod).mean()
    # 布林带上轨
    bollUpper =  mean + context.stdRange*std 
    # 布林带下轨
    bollBottom = mean - context.stdRange*std

    # 获取现有持仓
    pos = list(filter(lambda x:x['symbol']==context.symbol,get_position()))
    
    # 交易逻辑与下单
    # 当有持仓，且股价穿过BOLL上界的时候卖出股票。
    if pos and data.close.values[-1] > bollUpper.values[-1] and data.close.values[-2] <= bollUpper.values[-2]:
        order_volume(symbol=context.symbol, volume=100, side=OrderSide_Sell,
                        order_type=OrderType_Limit, position_effect=PositionEffect_Close, price=data.close.values[-1])
    # 当没有持仓，且股价穿过BOLL下界的时候买出股票。
    elif not pos and data.close.values[-1] < bollBottom.values[-1] and data.close.values[-2] >= bollBottom.values[-2]:
        order_volume(symbol=context.symbol, volume=100, side=OrderSide_Buy,
                        order_type=OrderType_Limit, position_effect=PositionEffect_Open, price=data.close.values[-1])


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
        backtest_start_time='2010-01-01 08:00:00',
        backtest_end_time='2020-12-31 15:30:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)