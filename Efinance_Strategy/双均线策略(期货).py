# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

import re
import datetime
import numpy as np
import pandas as pd

'''
示例策略仅供参考，不建议直接实盘使用。

本策略以分钟级别数据建立双均线模型，短周期为20，长周期为60
当短期均线由上向下穿越长期均线时做空
当短期均线由下向上穿越长期均线时做多
'''

def init(context):
    context.frequency = '300s'# 使用的频率，300s为5分钟bar
    context.short = 20  # 短周期均线
    context.long = 60  # 长周期均线
    context.symbol = ['CZCE.SA','CZCE.MA'] # 订阅交易标的 
    context.volume = 1 # 每次交易数量，手（注意资金是否充足）
    context.period = context.long + 1  # 订阅数据滑窗长度

    # 数据一次性获取
    if context.mode==MODE_BACKTEST:
        context.contract_list = {}
        for symbol in context.symbol:
            contract_list = fut_get_continuous_contracts(csymbol=symbol, start_date=context.backtest_start_time[:10], end_date=context.backtest_end_time[:10])
            if len(contract_list)>0:
                context.contract_list[symbol] = {dic['trade_date']:dic['symbol'] for dic in contract_list}
    # 定时任务：夜盘21点开始，日盘9点开始
    schedule(schedule_func=algo, date_rule='1d', time_rule='21:00:00')
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:00:00')


def algo(context):
    now_str = context.now.strftime('%Y-%m-%d')
    # 主力合约
    if context.now.hour>15:
        date = get_next_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0] 
    else:
        date = context.now.strftime('%Y-%m-%d')
    if context.mode==MODE_BACKTEST:
        try:
            context.main_contract = {symbol:context.contract_list[symbol][date] for symbol in context.symbol}
        except:
            context.main_contract = {symbol:fut_get_continuous_contracts(csymbol=symbol, start_date=date, end_date=date)[0]['symbol'] for symbol in context.symbol}
        context.main_contract_list = list(context.main_contract.values())
    else:
        context.main_contract = {symbol:fut_get_continuous_contracts(csymbol=symbol, start_date=date, end_date=date)[0]['symbol'] for symbol in context.symbol}
        context.main_contract_list = list(context.main_contract.values())
    # 订阅行情
    subscribe(context.main_contract_list, context.frequency, count=context.period, unsubscribe_previous=True)  
    # 有持仓时，检查持仓的合约是否为主力合约,非主力合约则卖出
    Account_positions = get_position()
    if Account_positions:
        # 获取当前价格
        symbols_list = list(set([posi['symbol'] for posi in Account_positions]))
        if len(symbols_list)>0:
            new_price = {data['symbol']:data['price'] for data in current_price(symbols_list)}
        for posi in Account_positions:
            holding_symbol_prefix = re.findall(r'\D+',posi['symbol'])[0].upper()
            if holding_symbol_prefix in context.symbol and posi['symbol'] not in context.main_contract_list:
                print('{}：持仓合约由{}替换为主力合约{}'.format(context.now,posi['symbol'],context.main_contract[holding_symbol_prefix]))       
                order_target_volume(symbol=posi['symbol'], volume=0, position_side=posi['side'], order_type=OrderType_Limit, price=new_price[posi['symbol']])


def on_bar(context, bars):
    # 获取通过subscribe订阅的数据
    symbol = bars[0]['symbol']
    if symbol in context.main_contract_list:
        prices = context.data(symbol, context.frequency, context.period, fields='close')

        # 计算长短周期均线
        short_avg = prices.rolling(context.short).mean().values
        long_avg = prices.rolling(context.long).mean().values

        # 查询持仓
        positions = get_position()
        position_long = list(filter(lambda x:x['symbol']==symbol and x['side']==PositionSide_Long,positions))        # 多头仓位
        position_short = list(filter(lambda x:x['symbol']==symbol and x['side']==PositionSide_Short,positions))      # 空头仓位

        # 短均线下穿长均线，做空(即当前时间点短均线处于长均线下方，前一时间点短均线处于长均线上方)
        if long_avg[-2] <= short_avg[-2] and long_avg[-1] > short_avg[
                -1] and not position_short:
            # 无多仓情况下，直接开空
            if not position_long:
                order_volume(symbol=symbol, volume=context.volume, side=OrderSide_Sell, position_effect=PositionEffect_Open, order_type=OrderType_Market)
            # 有多仓情况下，先平多，再开空(开空命令放在on_order_status里面)
            else:
                # 以市价平多仓
                order_volume(symbol=symbol, volume=context.volume, side=OrderSide_Sell, position_effect=PositionEffect_Close, order_type=OrderType_Market)

        # 短均线上穿长均线，做多（即当前时间点短均线处于长均线上方，前一时间点短均线处于长均线下方）
        if short_avg[-2] <= long_avg[-2] and short_avg[-1] > long_avg[
                -1] and not position_long:
            # 无空仓情况下，直接开多
            if not position_short:
                order_volume(symbol=symbol, volume=context.volume, side=OrderSide_Buy, position_effect=PositionEffect_Open, order_type=OrderType_Market)
            # 有空仓的情况下，先平空，再开多(开多命令放在on_order_status里面)
            else:
                # 以市价平空仓
                order_volume(symbol=symbol, volume=context.volume, side=OrderSide_Buy, position_effect=PositionEffect_Close, order_type=OrderType_Market)


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
        order_type_word = '限价' if order_type == 1 else '市价'
        print('{}:标的：{}，操作：以{}{}，委托价格：{}，委托数量：{}'.format(
            context.now, symbol, order_type_word, side_effect, price, volume))
        # 平仓后，接着开相反方向的仓位
        if effect == 2 and symbol in context.main_contract_list:
            order_volume(symbol=symbol,
                         volume=volume,
                         side=side,
                         order_type=OrderType_Market,
                         position_effect=PositionEffect_Open)


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
    backtest_start_time = str(datetime.datetime.now() - datetime.timedelta(days=100))[:19]
    backtest_end_time = str(datetime.datetime.now())[:19]
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='{{token}}',
        backtest_start_time=backtest_start_time,
        backtest_end_time=backtest_end_time,
        backtest_adjust=ADJUST_NONE,
        backtest_initial_cash=100000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
