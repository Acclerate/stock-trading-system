# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import os
import datetime
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 读取token
token = os.getenv('DIGGOLD_TOKEN')

'''
基本面价值投资策略 v5.0

策略思路：选择优质公司，在合理或低估价格买入，长期持有

核心逻辑：
1. 质量因子: 长期表现稳定，价格稳步上涨（而非短期暴涨）
2. 估值保护: 价格处于长期均值下方（低估）或合理区间
3. 趋势确认: 长期趋势向上（MA250），但短期不过热
4. 分散投资: 持有20-30只不同股票，分散风险
5. 长期持有: 每只股票持有3-6个月，降低交易成本
6. 价值平均: 定期调仓，卖出高估的，买入低估的
7. 熊市保护: 市场极度熊市时空仓
8. 沪深300选股池: 选择大盘蓝筹股
'''


def init(context):
    # 成分股指数 - 沪深300大盘蓝筹
    context.index_symbol = 'SHSE.000300'  # 沪深300
    context.market_index = 'SHSE.000300'  # 沪深300用于择时

    # 均线参数
    context.ma_short = 20
    context.ma_medium = 60
    context.ma_long = 120
    context.ma_vlong = 250

    # 选股参数
    context.max_position_count = 25  # 持有25只股票（分散投资）

    # 仓位管理
    context.base_position_ratio = 0.8  # 基础仓位80%（价值投资高仓位）

    # 择时参数
    context.market_status = 'neutral'

    # 调仓参数 - 季度调仓（长期持有）
    context.rebalance_month = [1, 4, 7, 10]  # 每季度调仓
    context.last_rebalance_month = 0
    context.min_holding_days = 60  # 最少持有60天

    # 记录买入日期（用于最少持有期检查）
    context.buy_dates = {}  # {symbol: buy_date}

    # 每个交易日执行
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:30:00')


def algo(context):
    now = context.now
    now_str = now.strftime('%Y-%m-%d')
    last_day = get_previous_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]

    # 1. 市场环境判断
    market_signal = check_market_trend(context, last_day)
    context.market_status = market_signal

    # 2. 季度调仓判断
    current_month = now.month
    is_rebalance_day = (current_month in context.rebalance_month and
                       current_month != context.last_rebalance_month)

    if is_rebalance_day:
        context.last_rebalance_month = current_month
        print('{}: 季度调仓日，市场状态: {}'.format(now, market_signal))

        # 极度熊市时清仓，否则正常调仓
        if market_signal == 'bearish':
            print('{}: 市场极度看空，清空所有仓位'.format(now))
            clear_all_positions(context, now)
        else:
            rebalance(context, now, last_day)


def check_market_trend(context, trade_date):
    """
    市场环境判断 - 使用MA趋势
    返回: 'bullish'(看多) / 'bearish'(看空) / 'neutral'(中性)
    """
    try:
        # 获取沪深300指数历史数据
        hist = history_n(symbol=context.market_index, frequency='1d',
                        count=context.ma_vlong + 10, end_time=trade_date,
                        fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(hist) < context.ma_vlong:
            return 'neutral'

        closes = hist['close'].values
        ma60 = np.mean(closes[-context.ma_medium:])
        ma120 = np.mean(closes[-context.ma_long:])
        ma250 = np.mean(closes[-context.ma_vlong:])
        current_price = closes[-1]

        # 趋势判断逻辑 - 价值投资更关注长期趋势
        if current_price > ma60 and ma60 > ma120 and ma120 > ma250:
            return 'bullish'  # 多头排列，看多
        elif current_price < ma120 and ma120 < ma250:
            return 'bearish'  # 长期趋势向下，看空
        else:
            return 'neutral'  # 中性
    except:
        return 'neutral'


def calculate_quality_score(symbol, context, trade_date):
    """
    计算质量得分 - 衡量公司长期表现稳定性
    使用: 长期趋势、波动率、相对强度
    """
    try:
        hist = history_n(symbol=symbol, frequency='1d',
                        count=context.ma_vlong + 10, end_time=trade_date,
                        fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(hist) < context.ma_vlong:
            return 0

        closes = hist['close'].values

        # 1. 长期趋势得分 (MA120向上)
        ma120_first = np.mean(closes[-context.ma_long-60:-context.ma_long])
        ma120_last = np.mean(closes[-context.ma_long:])
        long_trend = (ma120_last - ma120_first) / ma120_first if ma120_first > 0 else 0

        # 2. 波动率得分 (低波动=稳定)
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns) * np.sqrt(252)
        volatility_score = max(0, 1 - volatility / 0.5)  # 波动率50%以上得0分

        # 3. 250日收益表现 (长期正收益)
        return_250d = (closes[-1] - closes[-context.ma_vlong]) / closes[-context.ma_vlong]
        return_score = np.clip(return_250d * 2, 0, 1)  # 50%收益得满分

        # 综合质量得分
        quality_score = (max(0, long_trend * 5) * 0.3 +  # 长期趋势
                        volatility_score * 0.3 +          # 低波动
                        return_score * 0.4)               # 长期收益

        return quality_score
    except:
        return 0


def calculate_value_score(symbol, context, trade_date):
    """
    计算估值得分 - 价格相对于长期均线的位置
    价格越低于长期均线，估值越低，得分越高
    """
    try:
        hist = history_n(symbol=symbol, frequency='1d',
                        count=context.ma_vlong + 10, end_time=trade_date,
                        fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(hist) < context.ma_vlong:
            return 0

        closes = hist['close'].values

        # 计算各期均线
        ma60 = np.mean(closes[-context.ma_medium:])
        ma120 = np.mean(closes[-context.ma_long:])
        ma250 = np.mean(closes[-context.ma_vlong:])
        current_price = closes[-1]

        # 计算价格相对均线的位置
        ratio_to_ma60 = current_price / ma60
        ratio_to_ma120 = current_price / ma120
        ratio_to_ma250 = current_price / ma250

        # 估值得分: 价格低于长期均线时得分高
        value_score = 0

        # 相对MA250: 低于20%得满分，高于20%得0分
        if ratio_to_ma250 < 0.8:
            value_score += 0.5
        elif ratio_to_ma250 < 1.2:
            value_score += 0.5 * (1.2 - ratio_to_ma250) / 0.4

        # 相对MA120: 低于10%得满分，高于30%得0分
        if ratio_to_ma120 < 0.9:
            value_score += 0.3
        elif ratio_to_ma120 < 1.3:
            value_score += 0.3 * (1.3 - ratio_to_ma120) / 0.4

        # 相对MA60: 避免短期过热
        if ratio_to_ma60 < 1.1:
            value_score += 0.2
        elif ratio_to_ma60 > 1.3:
            value_score -= 0.2  # 短期过热扣分

        return max(0, min(1, value_score))
    except:
        return 0


def calculate_trend_confirmation_score(symbol, context, trade_date):
    """
    计算趋势确认得分 - 确保长期趋势向上但不过热
    """
    try:
        hist = history_n(symbol=symbol, frequency='1d',
                        count=context.ma_vlong + 10, end_time=trade_date,
                        fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(hist) < context.ma_vlong:
            return 0

        closes = hist['close'].values

        ma20 = np.mean(closes[-context.ma_short:])
        ma60 = np.mean(closes[-context.ma_medium:])
        ma120 = np.mean(closes[-context.ma_long:])
        ma250 = np.mean(closes[-context.ma_vlong:])
        current_price = closes[-1]

        trend_score = 0

        # 1. 长期趋势向上 (MA60 > MA120 > MA250)
        if ma60 > ma120:
            trend_score += 0.3
        if ma120 > ma250:
            trend_score += 0.3

        # 2. 价格在长期均线上方
        if current_price > ma120:
            trend_score += 0.2
        if current_price > ma250:
            trend_score += 0.2

        # 3. 避免短期过热 (价格不应远高于MA20)
        if current_price / ma20 < 1.15:  # 不超过MA20的15%
            trend_score += 0.1
        else:
            trend_score -= 0.2  # 短期过热扣分

        return max(0, min(1, trend_score))
    except:
        return 0


def calculate_volatility_score(symbol, context, trade_date):
    """计算波动率得分(波动率越低得分越高)"""
    try:
        hist = history_n(symbol=symbol, frequency='1d',
                        count=context.volatility_period + 10, end_time=trade_date,
                        fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(hist) < context.volatility_period:
            return 0

        closes = hist['close'].values
        returns = np.diff(closes) / closes[:-1]

        # 计算年化波动率
        volatility = np.std(returns[-context.volatility_period:]) * np.sqrt(252)

        # 转换为得分: 波动率越低得分越高
        if volatility <= 0:
            return 0
        volatility_score = 1 / (1 + volatility)  # 归一化

        return volatility_score
    except:
        return 0


def rebalance(context, now, last_day):
    """调仓逻辑"""
    # 获取中证1000成分股
    stock_pool = stk_get_index_constituents(index=context.index_symbol, trade_date=last_day)['symbol'].tolist()

    # 过滤条件
    stocks_info = get_symbols(sec_type1=1010, symbols=stock_pool,
                             trade_date=now.strftime('%Y-%m-%d'),
                             skip_suspended=True, skip_st=True)
    stock_pool = [item['symbol'] for item in stocks_info
                  if item['listed_date'] < now and item['delisted_date'] > now]

    print('{}: 可选股票池数量: {}'.format(now, len(stock_pool)))

    # 计算因子得分
    scores = []
    for symbol in stock_pool:
        quality_score = calculate_quality_score(symbol, context, last_day)
        value_score = calculate_value_score(symbol, context, last_day)
        trend_score = calculate_trend_confirmation_score(symbol, context, last_day)

        # 综合得分: 质量40% + 估值35% + 趋势25%
        total_score = quality_score * 0.4 + value_score * 0.35 + trend_score * 0.25

        # 最低质量门槛: 质量得分必须>0.3
        if quality_score < 0.3:
            continue

        scores.append({
            'symbol': symbol,
            'quality': quality_score,
            'value': value_score,
            'trend': trend_score,
            'total': total_score
        })

    # 排序选股
    if not scores:
        print('{}: 没有符合质量条件的股票，保持空仓'.format(now))
        return

    scores_df = pd.DataFrame(scores)
    scores_df = scores_df.sort_values('total', ascending=False)

    # 选择得分最高的股票
    selected = scores_df.head(context.max_position_count)
    symbols_pool = selected['symbol'].tolist()

    print('{}: 选中股票数量: {}'.format(now, len(symbols_pool)))
    for _, row in selected.head(5).iterrows():
        print('  {} - 质量:{:.4f}, 估值:{:.4f}, 趋势:{:.4f}, 综合:{:.4f}'.format(
            row['symbol'], row['quality'], row['value'], row['trend'], row['total']))

    # 执行调仓
    execute_rebalance(context, now, symbols_pool)


def execute_rebalance(context, now, symbols_pool):
    """执行调仓"""
    positions = get_position()

    # 使用基础仓位比例
    position_ratio = context.base_position_ratio

    # 计算单股仓位
    if len(symbols_pool) > 0:
        percent = position_ratio / len(symbols_pool)
    else:
        percent = 0

    print('{}: 仓位: {:.2%}, 单股仓位: {:.2%}'.format(
        now, position_ratio, percent if len(symbols_pool) > 0 else 0))

    # 卖出不在新池中的股票（考虑最少持有期）
    for position in positions:
        symbol = position['symbol']
        if symbol not in symbols_pool:
            # 检查是否满足最少持有期
            if symbol in context.buy_dates:
                holding_days = (now.date() - context.buy_dates[symbol]).days
                if holding_days < context.min_holding_days:
                    print('{}: {} 持有{}天，未满{}天，暂不卖出'.format(
                        now, symbol, holding_days, context.min_holding_days))
                    continue  # 保留这个股票

            new_price = history_n(symbol=symbol, frequency='1d', count=1,
                                 end_time=now, fields='open', adjust=ADJUST_PREV,
                                 adjust_end_time=context.backtest_end_time, df=False)[0]['open']
            order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,
                               position_side=PositionSide_Long, price=new_price)
            if symbol in context.buy_dates:
                del context.buy_dates[symbol]

    # 买入新池中的股票
    current_positions = [p['symbol'] for p in positions]
    for symbol in symbols_pool:
        if symbol not in current_positions:
            new_price = history_n(symbol=symbol, frequency='1d', count=1,
                                 end_time=now, fields='open', adjust=ADJUST_PREV,
                                 adjust_end_time=context.backtest_end_time, df=False)[0]['open']
            order_target_percent(symbol=symbol, percent=percent, order_type=OrderType_Limit,
                               position_side=PositionSide_Long, price=new_price)
            # 记录买入日期
            context.buy_dates[symbol] = now.date()


def clear_all_positions(context, now):
    """清空所有仓位"""
    positions = get_position()
    for position in positions:
        symbol = position['symbol']
        current_price = history_n(symbol=symbol, frequency='1d', count=1,
                                  end_time=now, fields='open', adjust=ADJUST_PREV,
                                  adjust_end_time=context.backtest_end_time, df=False)[0]['open']
        order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,
                           position_side=PositionSide_Long, price=current_price)
        if symbol in context.buy_dates:
            del context.buy_dates[symbol]


def on_order_status(context, order):
    """订单状态回调"""
    symbol = order['symbol']
    price = order['price']
    target_percent = order['target_percent']
    status = order['status']
    side = order['side']
    effect = order['position_effect']
    order_type = order['order_type']

    if status == 3:  # 全部成交
        if effect == 1:  # 开仓
            if side == 1:
                side_effect = '开多仓'
            else:
                side_effect = '开空仓'
        else:  # 平仓
            if side == 1:
                side_effect = '平空仓'
            else:
                side_effect = '平多仓'

        order_type_word = '限价' if order_type == 1 else '市价'
        print('{}:标的：{}，操作：以{}{}，委托价格：{}，目标仓位：{:.2%}'.format(
            context.now, symbol, order_type_word, side_effect, price, target_percent))


def on_backtest_finished(context, indicator):
    """回测完成回调"""
    print('*'*50)
    print('回测已完成，请通过右上角"回测历史"功能查询详情。')
    print('最终资金: {:.2f}'.format(indicator['pnl_ratio']))
    print('总收益率: {:.2%}'.format(indicator['pnl_ratio'] / 100 - 1))


if __name__ == '__main__':
    run(strategy_id='strategy_id',
        filename='multi_factor_strategy',
        mode=MODE_BACKTEST,
        token=token,
        backtest_start_time='2024-08-01 08:00:00',
        backtest_end_time='2026-02-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
