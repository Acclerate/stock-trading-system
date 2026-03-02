# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import datetime
import os
import sys
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 读取token
token = os.getenv('DIGGOLD_TOKEN')

# 设置日志文件路径
LOG_FILE = os.path.join(os.path.dirname(__file__), 'backtest_log_ml_strategy.txt')

class Logger:
    def __init__(self, filename):
        self.filename = filename
        self.terminal = sys.stdout
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('')
    def write(self, message):
        self.terminal.write(message)
        with open(self.filename, 'a', encoding='utf-8') as f:
            f.write(message)
    def flush(self):
        self.terminal.flush()

sys.stdout = Logger(LOG_FILE)
try:
    from sklearn import svm
except:
    import os
    print('正在安装scikit-learn库...')
    os.system('pip install scikit-learn')
    from sklearn import svm
    print('安装scikit-learn库完成！')

'''
示例策略仅供参考，不建议直接实盘使用。

本策略以支持向量机算法为基础，训练一个二分类（上涨/下跌）的模型，模型以历史N天数据的数据预测未来M天的涨跌与否。
特征变量为:1.收盘价/均值、2.现量/均量、3.最高价/均价、4.最低价/均价、5.现量、6.区间收益率、7.区间标准差。
若没有仓位，则在每个星期一预测涨跌,并在预测结果为上涨的时候购买标的.
若已经持有仓位，则在盈利大于10%的时候止盈,在星期五涨幅小于2%的时候止盈止损.
'''

def init(context):
    # 股票标的
    context.symbol = 'SHSE.600000'
    # 历史窗口长度，N
    context.history_len = 10
    # 预测窗口长度，M
    context.forecast_len = 5
    # 训练样本长度
    context.training_len = 90  # 20天为一个交易月
    # 止盈幅度
    context.earn_rate = 0.10
    # 最小涨幅卖出幅度
    context.sell_rate = 0.02
    # 每日09:31执行策略
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:31:00')


def algo(context):
    # 当前时间
    now = context.now
    now_str = now.strftime('%Y-%m-%d')
    # 获取当前时间的星期
    weekday = now.isoweekday()
    # 获取持仓
    position = get_position()

    # 获取当前价格
    current_price = history_n(symbol=context.symbol, frequency='1d', count=1, end_time=now_str, fields='close', adjust=ADJUST_PREV, df=True)['close'].iloc[-1]

    # 如果当前时间是星期一且没有仓位，则开始预测
    if weekday == 1 and not position:
        # 获取预测用的历史数据
        features = clf_fit(context, now_str)
        features = np.array(features).reshape(1, -1)
        prediction = context.clf.predict(features)[0]

        # 若预测值为上涨则买入
        if prediction == 1:
            order_target_percent(symbol=context.symbol, percent=1, order_type=OrderType_Market, position_side=PositionSide_Long)

    # 当涨幅大于10%,平掉所有仓位止盈
    elif position and current_price/position[0]['vwap'] >= 1+context.earn_rate:
        order_close_all()

    # 当时间为周五并且涨幅小于2%时,平掉所有仓位止损
    elif position and weekday == 5 and current_price/position[0]['vwap'] < 1+context.sell_rate:
        order_close_all()


def clf_fit(context, end_date):
    """
    训练支持向量机模型
    :param end_date:训练样本结束时间
    """
    # 获取目标股票的daily历史行情 - 使用history_n避免180天时间范围限制
    recent_data = history_n(symbol=context.symbol, frequency='1d', count=context.training_len, end_time=end_date, fill_missing='Last', adjust=ADJUST_PREV, df=True).set_index('eob')
    days = list(recent_data['bob'])

    x_train = []
    y_train = []
    # 整理训练数据
    for index in range(context.history_len, len(recent_data)):
        ## 自变量 X
        # 回溯N个交易日相关数据
        start_date = recent_data.index[index-context.history_len]
        end_date = recent_data.index[index]
        data = recent_data.loc[start_date:end_date,:]
        # 准备训练数据
        close = data['close'].values
        max_x = data['high'].values
        min_n = data['low'].values
        volume = data['volume'].values
        close_mean = close[-1] / np.mean(close)  # 收盘价/均值
        volume_mean = volume[-1] / np.mean(volume)  # 现量/均量
        max_mean = max_x[-1] / np.mean(max_x)  # 最高价/均价
        min_mean = min_n[-1] / np.mean(min_n)  # 最低价/均价
        vol = volume[-1]  # 现量
        return_now = close[-1] / close[0]  # 区间收益率
        std = np.std(np.array(close), axis=0)  # 区间标准差
        # 将计算出的指标添加到训练集X
        x_train.append([close_mean, volume_mean, max_mean, min_mean, vol, return_now, std])
        
        ## 因变量 Y
        if index<len(recent_data)-context.forecast_len:
            y_start_date = recent_data.index[index+1]
            y_end_date = recent_data.index[index+context.forecast_len]
            y_data = recent_data.loc[y_start_date:y_end_date,'close']
            if y_data.iloc[-1] > y_data.iloc[0]:
                label = 1
            else:
                label = 0
            y_train.append(label)
        
        # 最新一期的数据(返回该数据，作为待预测的数据)
        if index==len(recent_data)-1:
            new_x_traain = [close_mean, volume_mean, max_mean, min_mean, vol, return_now, std]
    else:
        # 剔除最后context.forecast_len期的数据
        x_train = x_train[:-context.forecast_len]

    # 训练SVM
    context.clf = svm.SVC(C=1.0, kernel='rbf', degree=3, gamma='auto', coef0=0.0, shrinking=True, probability=False,
                          tol=0.001, cache_size=200, verbose=False, max_iter=-1,decision_function_shape='ovr', random_state=None)
    context.clf.fit(x_train, y_train)

    # 返回最新数据
    return new_x_traain


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
        action = ''
        # A股卖出是"平昨仓"(effect=4)，期货等才是"平仓"(effect=2)
        if effect == 1 and side == 1:
            action = '开多仓'
        elif (effect == 2 or effect == 4) and side == 2:
            action = '平多仓'

        if action:
            order_type_word = '限价' if order_type==1 else '市价'
            # target_percent已经是小数形式（如0.05表示5%），直接用于格式化
            tgt_pct = target_percent if target_percent <= 1 else target_percent / 100
            print('{}:标的：{}，操作：以{}{}，委托价格：{}，目标仓位：{:.2%}'.format(
                context.now, symbol, order_type_word, action, price, tgt_pct if tgt_pct else 0))
       

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
    # 回测时间范围: 2025年2月1日 ~ 2026年2月28日
    backtest_start_time = '2025-02-01 09:30:00'
    backtest_end_time = '2026-02-28 15:00:00'
    run(strategy_id='strategy_id',
        filename='ml_strategy',
        mode=MODE_BACKTEST,
        token=token,
        backtest_start_time=backtest_start_time,
        backtest_end_time=backtest_end_time,
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)