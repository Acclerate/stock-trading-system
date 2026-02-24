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
LOG_FILE = os.path.join(os.path.dirname(__file__), 'backtest_log_style_rotation_v2.txt')

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
风格轮动策略 v2.0 - 改进版

改进内容：
1. 止损机制 - 单股亏损9%坚决止损
2. 优化选股逻辑 - 结合估值、质量、动量因子
3. 降低调仓频率 - 季度调仓而非月度
4. 趋势过滤器 - 只在明确趋势时交易
5. 市场环境判断 - 熊市时空仓

策略逻辑：
以上证50、沪深300、中证500作为市场三个风格的代表
- 每季度选取表现最好的一种风格
- 综合评分选择成分股（质量40% + 估值30% + 动量30%）
- 市场趋势向上时才交易，趋势向下时减仓
- 单股亏损9%止损
'''


def init(context):
    # ========== 基础参数 ==========
    # 待轮动的风格指数(分别为：上证50、沪深300、中证500)
    context.index_list = ['SHSE.000016', 'SHSE.000300', 'SZSE.399625']
    # 市场指数(用于趋势判断)
    context.market_index = 'SHSE.000300'  # 沪深300

    # ========== 趋势过滤参数 ==========
    context.ma_short = 20      # 短期均线
    context.ma_medium = 60     # 中期均线
    context.ma_long = 120      # 长期均线
    context.ma_vlong = 250     # 超长期均线

    # ========== 选股参数 ==========
    context.holding_num = 12          # 持股数量
    context.momentum_days = 20        # 动量统计天数
    context.min_quality_score = 0.3   # 最低质量得分门槛

    # ========== 调仓参数 ==========
    # 季度调仓：1月、4月、7月、10月
    context.rebalance_months = [1, 4, 7, 10]
    context.last_rebalance_month = 0

    # ========== 止损参数 ==========
    context.stop_loss_pct = 0.09  # 单股止损9%
    context.buy_prices = {}       # 记录买入价 {symbol: buy_price}

    # ========== 仓位管理 ==========
    context.market_status = 'neutral'  # 市场状态: bullish/bearish/neutral
    context.base_position_ratio = 0.8  # 基础仓位80%

    # ========== 回测参数 ==========
    context.backtest_end_time = context.backtest_end_time

    # 每日定时任务
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:30:00')


def algo(context):
    now = context.now
    now_str = now.strftime('%Y-%m-%d')
    last_day = get_previous_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]

    # 1. 市场环境判断
    market_signal = check_market_trend(context, last_day)
    context.market_status = market_signal
    print('{}: 市场状态: {}'.format(now_str, market_signal))

    # 2. 止损检查 - 每日检查
    check_stop_loss(context, now_str, last_day)

    # 3. 季度调仓判断
    current_month = now.month
    is_rebalance_day = (current_month in context.rebalance_months and
                       current_month != context.last_rebalance_month)

    if is_rebalance_day:
        context.last_rebalance_month = current_month
        print('{}: === 季度调仓日 ==='.format(now_str))

        # 极度熊市时清仓，否则正常调仓
        if market_signal == 'bearish':
            print('{}: 市场极度看空，清空所有仓位'.format(now_str))
            clear_all_positions(context, now_str, last_day)
        else:
            do_rebalance(context, now_str, last_day)


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
        ma20 = np.mean(closes[-context.ma_short:])
        ma60 = np.mean(closes[-context.ma_medium:])
        ma120 = np.mean(closes[-context.ma_long:])
        ma250 = np.mean(closes[-context.ma_vlong:])
        current_price = closes[-1]

        # 趋势判断逻辑
        if current_price > ma20 and ma20 > ma60 and ma60 > ma120 and ma120 > ma250:
            return 'bullish'  # 多头排列，看多
        elif current_price < ma120 and ma120 < ma250:
            return 'bearish'  # 长期趋势向下，看空
        else:
            return 'neutral'  # 中性
    except Exception as e:
        print('趋势判断异常: {}'.format(str(e)))
        return 'neutral'


def check_stop_loss(context, now_str, last_day):
    """止损检查 - 单股亏损9%坚决止损"""
    positions = get_position()
    for position in positions:
        symbol = position['symbol']
        if symbol not in context.buy_prices:
            # 如果没有记录买入价，用成本价代替
            context.buy_prices[symbol] = position['vwap']

        buy_price = context.buy_prices[symbol]

        # 获取当前价格
        current_price = history_n(symbol=symbol, frequency='1d', count=1,
                                  end_time=last_day, fields='close',
                                  adjust=ADJUST_PREV,
                                  adjust_end_time=context.backtest_end_time, df=False)[0]['close']

        # 计算亏损比例
        loss_pct = (current_price - buy_price) / buy_price

        if loss_pct <= -context.stop_loss_pct:
            print('{}: [止损] {} 亏损{:.2%}, 买入价:{:.2f}, 当前价:{:.2f}'.format(
                now_str, symbol, loss_pct, buy_price, current_price))

            # 卖出止损
            new_price = history_n(symbol=symbol, frequency='1d', count=1,
                                end_time=now_str, fields='open', adjust=ADJUST_PREV,
                                adjust_end_time=context.backtest_end_time, df=False)[0]['open']
            order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,
                               position_side=PositionSide_Long, price=new_price)

            # 清除买入价记录
            if symbol in context.buy_prices:
                del context.buy_prices[symbol]


def do_rebalance(context, now_str, last_day):
    """执行调仓"""
    # 1. 选择最佳风格指数
    best_index = select_best_style(context, last_day)
    print('{}: 最佳风格指数: {}'.format(now_str, best_index))

    # 2. 获取指数成分股
    symbols = list(stk_get_index_constituents(index=best_index, trade_date=last_day)['symbol'])

    # 3. 过滤条件
    stocks_info = get_symbols(sec_type1=1010, symbols=symbols, trade_date=now_str,
                             skip_suspended=True, skip_st=True)
    symbols = [item['symbol'] for item in stocks_info
              if item['listed_date'] < context.now and item['delisted_date'] > context.now]

    print('{}: 可选股票池数量: {}'.format(now_str, len(symbols)))

    # 4. 综合评分选股
    selected_stocks = score_and_select_stocks(context, symbols, last_day, now_str)

    if not selected_stocks:
        print('{}: 没有符合条件的股票，保持空仓'.format(now_str))
        return

    symbols_pool = [s['symbol'] for s in selected_stocks]
    print('{}: 选中股票数量: {}'.format(now_str, len(symbols_pool)))

    # 打印前5只股票的得分
    for stock in selected_stocks[:5]:
        print('  {} - 质量:{:.2f}, 估值:{:.2f}, 动量:{:.2f}, 综合:{:.2f}'.format(
            stock['symbol'], stock['quality'], stock['value'], stock['momentum'], stock['total']))

    # 5. 执行调仓
    execute_rebalance(context, now_str, last_day, symbols_pool)


def select_best_style(context, trade_date):
    """
    选择最佳风格指数
    改进：不只看过去20天收益率，还要看趋势稳定性
    """
    return_index = pd.DataFrame(columns=['return', 'trend_score'])

    for index_symbol in context.index_list:
        # 获取指数历史数据
        hist = history_n(symbol=index_symbol, frequency='1d',
                        count=context.ma_medium + 10, end_time=trade_date,
                        fields='close', fill_missing='Last',
                        adjust=ADJUST_PREV, df=True)

        if len(hist) < context.ma_medium:
            continue

        closes = hist['close'].values

        # 1. 计算20天收益率
        return_20d = closes[-1] / closes[0] - 1

        # 2. 计算趋势得分 (均线多头排列)
        ma20 = np.mean(closes[-context.ma_short:])
        ma60 = np.mean(closes[-context.ma_medium:])
        trend_score = 0
        if closes[-1] > ma20:
            trend_score += 1
        if ma20 > ma60:
            trend_score += 1

        return_index.loc[index_symbol, 'return'] = return_20d
        return_index.loc[index_symbol, 'trend_score'] = trend_score

    # 综合评分：收益率70% + 趋势30%
    return_index['total_score'] = return_index['return'] * 0.7 + return_index['trend_score'] * 0.3

    # 选择得分最高的指数
    best_index = return_index['total_score'].idxmax()
    return best_index


def score_and_select_stocks(context, symbols, trade_date, now_str):
    """
    综合评分选股
    质量因子40% + 估值因子30% + 动量因子30%
    """
    scores = []

    for symbol in symbols:
        try:
            # 计算各项得分
            quality_score = calculate_quality_score(symbol, context, trade_date)
            value_score = calculate_value_score(symbol, context, trade_date)
            momentum_score = calculate_momentum_score(symbol, context, trade_date)

            # 最低质量门槛
            if quality_score < context.min_quality_score:
                continue

            # 综合得分
            total_score = (quality_score * 0.4 +
                          value_score * 0.3 +
                          momentum_score * 0.3)

            scores.append({
                'symbol': symbol,
                'quality': quality_score,
                'value': value_score,
                'momentum': momentum_score,
                'total': total_score
            })
        except Exception as e:
            continue

    if not scores:
        return []

    # 排序选股
    scores_df = pd.DataFrame(scores)
    scores_df = scores_df.sort_values('total', ascending=False)

    # 选择得分最高的股票
    selected = scores_df.head(context.holding_num)
    return selected.to_dict('records')


def calculate_quality_score(symbol, context, trade_date):
    """
    计算质量得分 - 衡量公司长期表现稳定性
    """
    try:
        hist = history_n(symbol=symbol, frequency='1d',
                        count=context.ma_long + 20, end_time=trade_date,
                        fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(hist) < context.ma_long:
            return 0

        closes = hist['close'].values

        # 1. 长期趋势得分 (MA60向上)
        ma60_first = np.mean(closes[-context.ma_long-20:-context.ma_long+40])
        ma60_last = np.mean(closes[-context.ma_long:])
        long_trend = (ma60_last - ma60_first) / ma60_first if ma60_first > 0 else 0
        trend_score = max(0, min(1, long_trend * 5))  # 归一化到0-1

        # 2. 波动率得分 (低波动=稳定)
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns) * np.sqrt(252)
        volatility_score = max(0, 1 - volatility / 0.5)

        # 3. 120日收益表现
        return_120d = (closes[-1] - closes[-context.ma_long]) / closes[-context.ma_long]
        return_score = max(0, min(1, return_120d * 2))

        # 综合质量得分
        quality_score = (trend_score * 0.3 +
                        volatility_score * 0.3 +
                        return_score * 0.4)

        return quality_score
    except:
        return 0


def calculate_value_score(symbol, context, trade_date):
    """
    计算估值得分 - 价格相对位置
    价格低于长期均线时得分高（低估）
    """
    try:
        hist = history_n(symbol=symbol, frequency='1d',
                        count=context.ma_vlong + 10, end_time=trade_date,
                        fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(hist) < context.ma_vlong:
            return 0

        closes = hist['close'].values
        current_price = closes[-1]

        # 计算各期均线
        ma60 = np.mean(closes[-context.ma_medium:])
        ma120 = np.mean(closes[-context.ma_long:])
        ma250 = np.mean(closes[-context.ma_vlong:])

        # 计算价格相对均线的位置
        ratio_to_ma60 = current_price / ma60
        ratio_to_ma120 = current_price / ma120
        ratio_to_ma250 = current_price / ma250

        # 估值得分: 价格低于长期均线时得分高
        value_score = 0

        # 相对MA250: 低于15%得满分，高于30%得0分
        if ratio_to_ma250 < 0.85:
            value_score += 0.5
        elif ratio_to_ma250 < 1.3:
            value_score += 0.5 * (1.3 - ratio_to_ma250) / 0.45

        # 相对MA120: 低于10%得满分，高于20%得0分
        if ratio_to_ma120 < 0.9:
            value_score += 0.3
        elif ratio_to_ma120 < 1.2:
            value_score += 0.3 * (1.2 - ratio_to_ma120) / 0.3

        # 相对MA60: 避免短期过热
        if ratio_to_ma60 < 1.1:
            value_score += 0.2
        elif ratio_to_ma60 > 1.25:
            value_score -= 0.2

        return max(0, min(1, value_score))
    except:
        return 0


def calculate_momentum_score(symbol, context, trade_date):
    """
    计算动量得分 - 但避免追高
    """
    try:
        hist = history_n(symbol=symbol, frequency='1d',
                        count=context.momentum_days + 10, end_time=trade_date,
                        fields='close', skip_suspended=True,
                        fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(hist) < context.momentum_days + 5:
            return 0

        closes = hist['close'].values

        # 20天收益率
        momentum = (closes[-1] - closes[-context.momentum_days-1]) / closes[-context.momentum_days-1]

        # 动量得分：适度动量得分高，过高追高扣分
        if -0.1 <= momentum <= 0.2:
            momentum_score = 0.5 + momentum * 2  # -10%到20%之间，线性打分
        elif momentum > 0.2:
            # 涨太多，可能是追高
            momentum_score = max(0, 1 - (momentum - 0.2) * 2)
        else:
            # 下跌太多
            momentum_score = max(0, 0.5 + momentum * 3)

        return max(0, min(1, momentum_score))
    except:
        return 0


def execute_rebalance(context, now_str, last_day, symbols_pool):
    """执行调仓"""
    positions = get_position()

    # 根据市场状态调整仓位
    if context.market_status == 'bullish':
        position_ratio = context.base_position_ratio  # 80%
    elif context.market_status == 'neutral':
        position_ratio = context.base_position_ratio * 0.7  # 56%
    else:  # bearish - 不应该到这里，因为前面已经清仓了
        position_ratio = 0

    # 计算单股仓位
    if len(symbols_pool) > 0 and position_ratio > 0:
        percent = position_ratio / len(symbols_pool)
    else:
        percent = 0

    print('{}: 仓位: {:.2%}, 单股仓位: {:.2%}'.format(
        now_str, position_ratio, percent if len(symbols_pool) > 0 else 0))

    # 卖出不在新池中的股票
    for position in positions:
        symbol = position['symbol']
        if symbol not in symbols_pool:
            new_price = history_n(symbol=symbol, frequency='1d', count=1,
                                end_time=now_str, fields='open', adjust=ADJUST_PREV,
                                adjust_end_time=context.backtest_end_time, df=False)[0]['open']
            order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,
                               position_side=PositionSide_Long, price=new_price)
            print('{}: [卖出] {} 不在新股票池中'.format(now_str, symbol))
            if symbol in context.buy_prices:
                del context.buy_prices[symbol]

    # 买入新池中的股票
    current_positions = [p['symbol'] for p in positions]
    for symbol in symbols_pool:
        if symbol not in current_positions:
            new_price = history_n(symbol=symbol, frequency='1d', count=1,
                                end_time=now_str, fields='open', adjust=ADJUST_PREV,
                                adjust_end_time=context.backtest_end_time, df=False)[0]['open']
            if percent > 0:
                order_target_percent(symbol=symbol, percent=percent, order_type=OrderType_Limit,
                                   position_side=PositionSide_Long, price=new_price)
                # 记录买入价
                context.buy_prices[symbol] = new_price
                print('{}: [买入] {} 价格:{:.2f}'.format(now_str, symbol, new_price))


def clear_all_positions(context, now_str, last_day):
    """清空所有仓位"""
    positions = get_position()
    for position in positions:
        symbol = position['symbol']
        new_price = history_n(symbol=symbol, frequency='1d', count=1,
                            end_time=now_str, fields='open', adjust=ADJUST_PREV,
                            adjust_end_time=context.backtest_end_time, df=False)[0]['open']
        order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Limit,
                           position_side=PositionSide_Long, price=new_price)
        print('{}: [清仓] {}'.format(now_str, symbol))
        if symbol in context.buy_prices:
            del context.buy_prices[symbol]


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
            context.now, symbol, order_type_word, side_effect, price,
            target_percent/100 if target_percent else 0))


def on_backtest_finished(context, indicator):
    """回测完成回调"""
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
        filename='style_rotation_v2',
        mode=MODE_BACKTEST,
        token=token,
        backtest_start_time='2024-01-01 08:00:00',
        backtest_end_time='2026-01-31 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
