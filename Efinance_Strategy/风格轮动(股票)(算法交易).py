# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import datetime
import numpy as np
import pandas as pd

'''
示例策略仅供参考，不建议直接实盘使用。

回测模式不支持算法交易，仅部分券商版本的实盘模式支持；此策略仅供参考，不具有投资建议，各项数值需客户自行填写后方可运行。

风格轮动策略
逻辑：以上证50、沪深300、中证500作为市场三个风格的代表，每次选取表现做好的一种风格，买入其成分股中最大市值的N只股票，每月月初进行调仓换股
'''

def init(context):
    # 待轮动的风格指数(分别为：上证50、沪深300、中证500)
    context.index = ['SHSE.000016', 'SHSE.000300', 'SZSE.399625']
    # 用于统计数据的天数
    context.days = 20
    # 持股数量
    context.holding_num = 10
    # 每日定时任务
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:30:00')


def algo(context):
    # 当天日期
    now_str = context.now.strftime('%Y-%m-%d')
    # 获取上一个交易日
    last_day = get_previous_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]
    # 判断是否为每个月第一个交易日
    if context.now.month!=pd.Timestamp(last_day).month:
        return_index = pd.DataFrame(columns=['return'])
        # 获取并计算指数收益率
        for i in context.index:
            return_index_his = history_n(symbol=i, frequency='1d', count=context.days+1, fields='close,bob',
                                        fill_missing='Last', adjust=ADJUST_PREV, end_time=last_day, df=True)
            return_index_his = return_index_his['close'].values
            return_index.loc[i,'return'] = return_index_his[-1] / return_index_his[0] - 1
        
        # 获取指定数内收益率表现最好的风格
        sector = return_index.index[np.argmax(return_index)]
        print('{}:最佳指数是:{}'.format(now_str,sector))

        # 获取最佳指数成份股
        symbols = list(stk_get_index_constituents(index=sector, trade_date=last_day)['symbol'])
        
        # 过滤停牌的股票
        stocks_info =  get_symbols(sec_type1=1010, symbols=symbols, trade_date=now_str, skip_suspended=True, skip_st=True)
        symbols = [item['symbol'] for item in stocks_info if item['listed_date']<context.now and item['delisted_date']>context.now]
        # 获取最佳指数成份股的市值，选取市值最大的N只股票
        fin = stk_get_daily_mktvalue_pt(symbols=symbols, fields='tot_mv', trade_date=last_day, df=True).sort_values(by='tot_mv',ascending=False)
        to_buy = list(fin.iloc[:context.holding_num]['symbol'])
        
        # 计算权重(预留出2%资金，防止剩余资金不够手续费抵扣)
        percent = 0.98 / len(to_buy)
        # 获取当前所有仓位
        positions = get_position()

        # 平不在标的池的股票（注：本策略交易以开盘价为交易价格，当调整定时任务时间时，需调整对应价格）
        for position in positions:
            symbol = position['symbol']
            if symbol not in to_buy:
                # 当前价（tick数据，免费版本有时间权限限制；实时模式，返回当前最新 tick 数据，回测模式，返回回测当前时间点的最近一分钟的收盘价）
                new_price = current(symbols=symbol)[0]['price']
                # # 普通下单
                # order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,position_side=PositionSide_Long,price=new_price)

                # 交易算法下单
                trade_volume = position['available_now']                                            # 获取股票的可用数量
                # 下单
                if trade_volume>0:
                    algo_param = {'start_time': '09:00:00', 'end_time_referred':'14:55:00', 'end_time': '14:55:00', 'end_time_valid': 1, 'stop_sell_when_dl': 1,'cancel_when_pl': 0, 'min_trade_amount': 100000}
                    algo_order(symbol=symbol, volume=trade_volume, side=OrderSide_Sell, order_type=OrderType_Limit, position_effect=PositionEffect_Close, price=new_price, algo_name='ATS-SMART', algo_param=algo_param)
                    print('{}:{}卖出委托，委托价格：{}，委托市值：{:.0f}'.format(now_str,symbol,new_price,trade_volume*new_price)) 
                else:
                    print('{}:{}可用数量不足，未成功下单！'.format(now_str,symbol))

        # 买入标的池中的股票（注：本策略交易以开盘价为交易价格，当调整定时任务时间时，需调整对应价格）
        for symbol in to_buy:
            # 当前价（tick数据，免费版本有时间权限限制；实时模式，返回当前最新 tick 数据，回测模式，返回回测当前时间点的最近一分钟的收盘价）
            new_price = current(symbols=symbol)[0]['price']
            # 普通下单
            # order_target_percent(symbol=symbol, percent=percent, order_type=OrderType_Limit,position_side=PositionSide_Long,price=new_price)
            
            # 交易算法下单
            Account_cash = get_cash()                                                                # 获取账户资金信息
            available_amount = min(Account_cash['nav']*percent,Account_cash['available'])            # 计算委托金额 
            trade_volume = int(np.floor(available_amount/new_price/100)*100)                         # 计算下单数量
            if symbol[:7]=='SHSE.68' and trade_volume<200:trade_volume = 0                           # 调整下单数量：科创板最小买入单位是200股
            # 下单
            if trade_volume>0:
                algo_param = {'start_time': '09:00:00', 'end_time_referred':'14:55:00', 'end_time': '14:55:00', 'end_time_valid': 1, 'stop_sell_when_dl': 1,'cancel_when_pl': 0, 'min_trade_amount': 100000}
                algo_order(symbol=symbol, volume=trade_volume, side=OrderSide_Buy, order_type=OrderType_Limit, position_effect=PositionEffect_Open, price=new_price, algo_name='ATS-SMART', algo_param=algo_param)
                print('{}:{}买入委托，委托价格：{}，委托市值：{:.0f}'.format(now_str,symbol,new_price,trade_volume*new_price)) 
            else:
                print('{}:{}可用资金不足，未成功下单！'.format(now_str,symbol))


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
        backtest_start_time='2019-01-01 08:00:00',
        backtest_end_time='2020-12-31 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)