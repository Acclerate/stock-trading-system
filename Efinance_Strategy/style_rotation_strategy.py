# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import os
import sys
import datetime
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 读取token
token = os.getenv('DIGGOLD_TOKEN')

# 日志文件配置
LOG_FILE = os.path.join(os.path.dirname(__file__), 'backtest_log_style_rotation.txt')

# 重定向print到日志文件
class Logger:
    def __init__(self, filename):
        self.filename = filename
        self.terminal = sys.stdout
        # 清空旧日志
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('')

    def write(self, message):
        self.terminal.write(message)
        with open(self.filename, 'a', encoding='utf-8') as f:
            f.write(message)

    def flush(self):
        self.terminal.flush()

# 启用日志记录
sys.stdout = Logger(LOG_FILE)

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
    # 回测结束时间(用于获取历史数据)
    context.backtest_end_time = context.backtest_end_time
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

        # 平不在标的池的股票（使用普通下单，回测模式不支持算法交易）
        for position in positions:
            symbol = position['symbol']
            if symbol not in to_buy:
                # 获取开盘价进行交易
                new_price = history_n(symbol=symbol, frequency='1d', count=1,
                                    end_time=now_str, fields='open', adjust=ADJUST_PREV,
                                    adjust_end_time=context.backtest_end_time, df=False)[0]['open']
                # 普通下单
                order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,
                                   position_side=PositionSide_Long, price=new_price)
                print('{}:{}卖出委托，委托价格：{}'.format(now_str, symbol, new_price))

        # 买入标的池中的股票（使用普通下单，回测模式不支持算法交易）
        for symbol in to_buy:
            # 获取开盘价进行交易
            new_price = history_n(symbol=symbol, frequency='1d', count=1,
                                end_time=now_str, fields='open', adjust=ADJUST_PREV,
                                adjust_end_time=context.backtest_end_time, df=False)[0]['open']
            # 普通下单
            order_target_percent(symbol=symbol, percent=percent, order_type=OrderType_Limit,
                               position_side=PositionSide_Long, price=new_price)
            print('{}:{}买入委托，委托价格：{}'.format(now_str, symbol, new_price))


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
        # 输出目标仓位百分比，供backtest_analyzer.py解析
        print('{}:标的：{}，操作：以{}{}，委托价格：{}，目标仓位：{:.2%}'.format(
            context.now, symbol, order_type_word, side_effect, price, target_percent/100 if target_percent else 0))
       
       
def on_backtest_finished(context, indicator):
    print('*'*50)
    print('回测已完成！')
    print('='*50)
    print('【回测结果摘要】')

    # 使用get方法安全地访问指标，打印所有可用的指标
    for key, value in indicator.items():
        print('{}: {}'.format(key, value))

    print('='*50)
    print('详细日志已保存到: {}'.format(LOG_FILE))
    print('可使用以下命令分析日志:')
    print('  python backtest_analyzer.py {}'.format(LOG_FILE))
    print('='*50)


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
        filename='style_rotation_strategy',
        mode=MODE_BACKTEST,
        token=token,
        backtest_start_time='2024-01-01 08:00:00',
        backtest_end_time='2026-01-31 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)