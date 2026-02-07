# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import datetime
import numpy as np
import pandas as pd

'''
示例策略仅供参考，不建议直接实盘使用。

本策略基于Fama-French三因子模型。
假设三因子模型可以完全解释市场，以三因子模型对每股股票进行回归计算其Alpha值，当alpha为负表明市场低估该股，因此应该买入。
策略思路：
计算市场收益率、个股的账面市值比和市值,并对后两个进行了分类,
根据分类得到的组合分别计算其市值加权收益率、SMB和HML. 
对各个股票进行回归(假设无风险收益率等于0)得到Alpha值.
选取Alpha值小于0并为最小的10只股票进入标的池，每月初移仓换股
'''


def init(context):
    # 成分股指数
    context.index_symbol = 'SHSE.000300'
    # 数据滑窗
    context.date = 20
    # 设置开仓的最大资金量
    context.ratio = 0.8
    # 账面市值比的大/中/小分类
    context.BM_HIGH = 3.0
    context.BM_MIDDLE = 2.0
    context.BM_LOW = 1.0
    # 市值大/小分类
    context.MV_BIG = 2.0
    context.MV_SMALL = 1.0
    # 每个交易日的09:40 定时执行algo任务
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:30:00')
    

def algo(context):
    # 当前时间
    now = context.now
    now_str = now.strftime('%Y-%m-%d')  
    # 获取上一个交易日的日期
    last_day = get_previous_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]
    # 判断是否为每个月第一个交易日
    if now.month!=pd.Timestamp(last_day).month:
        # 获取沪深300成份股
        stock300 = stk_get_index_constituents(index=context.index_symbol, trade_date=last_day)['symbol'].tolist()
        # 过滤停牌、ST、退市及未上市的股票
        stocks_info =  get_symbols(sec_type1=1010, symbols=stock300, trade_date=now.strftime('%Y-%m-%d'), skip_suspended=True, skip_st=True)
        stock300 = [item['symbol'] for item in stocks_info if item['listed_date']<now and item['delisted_date']>now]
        # 获取所有股票市值
        fin = stk_get_daily_mktvalue_pt(symbols=stock300, fields='tot_mv', trade_date=last_day, df=True).sort_values(by='tot_mv')
        # 净资产
        ttl_eqy = stk_get_fundamentals_balance_pt(symbols=stock300, date=last_day, fields='ttl_eqy', df=True)
        ttl_eqy['max_rpt_date'] = ttl_eqy.groupby(['symbol'])['rpt_date'].max == ttl_eqy['rpt_date']
        ttl_eqy = ttl_eqy[ttl_eqy['max_rpt_date'] == True]
        # 计算PB
        fin = fin.merge(ttl_eqy,on=['symbol'],how='left')
        fin['PB'] = fin['tot_mv']/fin['ttl_eqy']    

        # 计算账面市值比,为P/B的倒数
        fin.loc[:,'PB'] = (fin['PB'] ** -1)

        # 计算市值的50%的分位点,用于后面的分类
        size_gate = fin['tot_mv'].quantile(0.50)

        # 计算账面市值比的30%和70%分位点,用于后面的分类
        bm_gate = [fin['PB'].quantile(0.30), fin['PB'].quantile(0.70)]
        fin.index = fin.symbol

        # 设置存放股票收益率的变量
        data_df = pd.DataFrame()
        # 对未停牌的股票进行处理
        for symbol in fin.symbol:
            # 计算收益率
            close = history_n(symbol=symbol, frequency='1d', count=context.date + 1, end_time=last_day, fields='close',
                            skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)['close'].values
            stock_return = close[-1] / close[0] - 1
            pb = fin['PB'][symbol]
            market_value = fin['tot_mv'][symbol]

            # 获取[股票代码， 股票收益率, 账面市值比的分类, 市值的分类, 市值]
            # 其中账面市值比的分类为：高（3）、中（2）、低（1）
            # 市值的分类：大（2）、小（1）
            if pb < bm_gate[0]:
                if market_value < size_gate:
                    label = [symbol, stock_return, context.BM_LOW, context.MV_SMALL, market_value]# 小市值/低BM                
                else:
                    label = [symbol, stock_return, context.BM_LOW, context.MV_BIG, market_value]# 大市值/低BM
            elif pb < bm_gate[1]:
                if market_value < size_gate:
                    label = [symbol, stock_return, context.BM_MIDDLE, context.MV_SMALL, market_value]# 小市值/中BM
                else:
                    label = [symbol, stock_return, context.BM_MIDDLE, context.MV_BIG, market_value]# 大市值/中BM
            elif market_value < size_gate:
                label = [symbol, stock_return, context.BM_HIGH, context.MV_SMALL, market_value]# 小市值/高BM
            else:
                label = [symbol, stock_return, context.BM_HIGH, context.MV_BIG, market_value]# 大市值/高BM
            data_df = pd.concat([data_df,pd.DataFrame(label,index=['symbol', 'return', 'BM', 'tot_mv', 'mv']).T])
        data_df.set_index('symbol',inplace=True)

        # 调整数据类型
        for column in data_df.columns:
            data_df[column] = data_df[column].astype(np.float64)

        # 计算小市值组合的收益率（组内以市值加权计算收益率，组间以等权计算收益率）
        smb_s = (market_value_weighted(data_df, context.MV_SMALL, context.BM_LOW) +
                market_value_weighted(data_df, context.MV_SMALL, context.BM_MIDDLE) +
                market_value_weighted(data_df, context.MV_SMALL, context.BM_HIGH)) / 3
        # 计算大市值组合的收益率（组内以市值加权计算收益率，组间以等权计算收益率）
        smb_b = (market_value_weighted(data_df, context.MV_BIG, context.BM_LOW) +
                market_value_weighted(data_df, context.MV_BIG, context.BM_MIDDLE) +
                market_value_weighted(data_df, context.MV_BIG, context.BM_HIGH)) / 3
        # 计算规模因子的收益率（小市值组收益率-大市值组收益率）
        smb = smb_s - smb_b

        # 计算高BM组合的收益率（组内以市值加权计算收益率，组间以等权计算收益率）
        hml_b = (market_value_weighted(data_df, context.MV_SMALL, context.BM_HIGH) +
                market_value_weighted(data_df, context.MV_BIG, context.BM_HIGH)) / 2
        # 计算低BM组合的收益率（组内以市值加权计算收益率，组间以等权计算收益率）
        hml_s = (market_value_weighted(data_df, context.MV_SMALL, context.BM_LOW) +
                market_value_weighted(data_df, context.MV_BIG, context.BM_LOW)) / 2
        # 计算价值因子的收益率（高BM组收益率-低BM市值组收益率）
        hml = hml_b - hml_s

        # 获取市场收益率
        close = history_n(symbol=context.index_symbol, frequency='1d', count=context.date + 1,
                        end_time=last_day, fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)['close'].values
        market_return = close[-1] / close[0] - 1
        coff_pool = []

        # 对每只股票进行回归获取其alpha值
        for stock in data_df.index:
            x_value = np.array([[market_return], [smb], [hml], [1.0]])
            y_value = np.array([data_df['return'][stock]])
            # OLS估计系数
            coff = np.linalg.lstsq(x_value.T, y_value, rcond=None)[0][3]
            coff_pool.append(coff)

        # 获取alpha最小并且小于0的10只的股票进行操作(若少于10只则全部买入)
        data_df.loc[:,'alpha'] = coff_pool
        symbols_pool = data_df[data_df.alpha < 0].sort_values(by='alpha').head(10).index.tolist()
        positions = get_position()

        # 平不在标的池的股票（注：本策略交易以开盘价为交易价格，当调整定时任务时间时，需调整对应价格）
        for position in positions:
            symbol = position['symbol']
            if symbol not in symbols_pool:
                # 开盘价（日频数据）
                new_price = history_n(symbol=symbol, frequency='1d', count=1, end_time=context.now, fields='open', adjust=ADJUST_PREV, adjust_end_time=context.backtest_end_time, df=False)[0]['open']
                # # 当前价（tick数据，免费版本有时间权限限制；实时模式，返回当前最新 tick 数据，回测模式，返回回测当前时间点的最近一分钟的收盘价）
                # new_price = current(symbols=symbol)[0]['price']
                order_info = order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,position_side=PositionSide_Long,price=new_price)

        # 获取股票的权重
        percent = context.ratio / len(symbols_pool)

        # 买在标的池中的股票（注：本策略交易以开盘价为交易价格，当调整定时任务时间时，需调整对应价格）
        for symbol in symbols_pool:
            # 开盘价（日频数据）
            new_price = history_n(symbol=symbol, frequency='1d', count=1, end_time=context.now, fields='open', adjust=ADJUST_PREV, adjust_end_time=context.backtest_end_time, df=False)[0]['open']
            # # 当前价（tick数据，免费版本有时间权限限制；实时模式，返回当前最新 tick 数据，回测模式，返回回测当前时间点的最近一分钟的收盘价）
            # new_price = current(symbols=symbol)[0]['price']
            order_info = order_target_percent(symbol=symbol, percent=percent, order_type=OrderType_Limit,position_side=PositionSide_Long,price=new_price)


def market_value_weighted(df, MV, BM):
    """
    计算市值加权下的收益率
    :param MV：MV为市值的分类对应的组别
    :param BM：BM账目市值比的分类对应的组别
    """
    select = df[(df['tot_mv'] == MV) & (df['BM'] == BM)] # 选出市值为MV，账目市值比为BM的所有股票数据
    mv_weighted = select['mv']/np.sum(select['mv'])# 市值加权的权重
    return_weighted = select['return']*mv_weighted# 市值加权下的收益率
    return np.sum(return_weighted)


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
        print('{}:标的：{}，操作：以{}{}，委托价格：{}，目标仓位：{:.2%}'.format(context.now,symbol,order_type_word,side_effect,price,target_percent))


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
        backtest_start_time='2021-08-01 08:00:00',
        backtest_end_time='2022-02-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)