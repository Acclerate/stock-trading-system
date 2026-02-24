# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import os
import sys
import datetime
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('DIGGOLD_TOKEN')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'backtest_log_style_rotation_v3.txt')

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

SECTOR_MAPPING = {
    '金融': ['银行', '保险', '证券', '信托'],
    '科技': ['软件', '半导体', '电子', '通信', '互联网'],
    '消费': ['食品', '饮料', '白酒', '家电', '纺织', '商贸'],
    '医药': ['医药', '生物', '医疗', '化学制药'],
    '能源': ['石油', '煤炭', '天然气', '新能源'],
    '材料': ['钢铁', '有色', '化工', '建材'],
    '工业': ['机械', '设备', '制造', '军工'],
    '公用': ['电力', '水务', '环保', '燃气'],
    '地产': ['房地产', '建筑', '装修'],
    '交运': ['交通', '运输', '物流', '航空']
}

def init(context):
    context.index_list = ['SHSE.000016', 'SHSE.000300', 'SZSE.399625']
    context.market_index = 'SHSE.000300'
    context.ma_short = 20
    context.ma_medium = 60
    context.ma_long = 120
    context.ma_vlong = 250
    context.holding_num = 15
    context.momentum_days = 20
    context.min_quality_score = 0.2
    context.volatility_period = 60
    context.rebalance_months = [1, 4, 7, 10]
    context.last_rebalance_month = 0
    context.stop_loss_base = 0.12
    context.stop_loss_max = 0.15
    context.buy_prices = {}
    context.market_status = 'neutral'
    context.base_position_ratio = 0.8
    context.min_position_ratio = 0.5
    context.max_position_ratio = 0.95
    context.sector_lookback = 20
    context.hot_sectors = []
    context.custom_end_time = '2026-01-31 16:00:00'
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:30:00')

def algo(context):
    now = context.now
    now_str = now.strftime('%Y-%m-%d')
    last_day = get_previous_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]
    
    market_signal = check_market_trend(context, last_day)
    context.market_status = market_signal
    market_vol = calculate_market_volatility(context, last_day)
    volatility_level = get_volatility_level(market_vol)
    
    check_dynamic_stop_loss(context, now_str, last_day)
    
    current_month = now.month
    is_rebalance_day = (current_month in context.rebalance_months and current_month != context.last_rebalance_month)
    
    if is_rebalance_day:
        context.last_rebalance_month = current_month
        print('{}: === 季度调仓日，市场状态: {}, 波动率: {:.2%} ({}) ==='.format(now_str, market_signal, market_vol, volatility_level))
        if market_signal == 'bearish':
            print('{}: 市场极度看空，清空所有仓位'.format(now_str))
            clear_all_positions(context, now_str, last_day)
        else:
            do_rebalance(context, now_str, last_day, market_vol)

def check_market_trend(context, trade_date):
    try:
        hist = history_n(symbol=context.market_index, frequency='1d', count=context.ma_vlong + 10, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.ma_vlong: return 'neutral'
        closes = hist['close'].values
        ma20, ma60, ma120, ma250 = np.mean(closes[-context.ma_short:]), np.mean(closes[-context.ma_medium:]), np.mean(closes[-context.ma_long:]), np.mean(closes[-context.ma_vlong:])
        if closes[-1] > ma20 and ma20 > ma60 and ma60 > ma120 and ma120 > ma250: return 'bullish'
        elif closes[-1] < ma120 and ma120 < ma250: return 'bearish'
        else: return 'neutral'
    except: return 'neutral'

def calculate_market_volatility(context, trade_date):
    try:
        hist = history_n(symbol=context.market_index, frequency='1d', count=context.volatility_period + 10, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.volatility_period: return 0.15
        returns = np.diff(hist['close'].values) / hist['close'].values[:-1]
        return np.std(returns[-context.volatility_period:]) * np.sqrt(252)
    except: return 0.15

def get_volatility_level(volatility):
    if volatility < 0.12: return '低'
    elif volatility < 0.20: return '中'
    else: return '高'

def get_dynamic_position_ratio(context, market_vol):
    if market_vol < 0.12: return context.max_position_ratio
    elif market_vol < 0.20: return context.base_position_ratio
    else: return context.min_position_ratio

def check_dynamic_stop_loss(context, now_str, last_day):
    # 兼容两种 API 获取持仓方式
    try: positions = context.account().positions()
    except: positions = get_position()
    
    for pos in positions:
        try: symbol = pos.symbol
        except: symbol = pos['symbol']

        if symbol not in context.buy_prices:
            context.buy_prices[symbol] = {'price': pos.vwap if hasattr(pos, 'vwap') else pos['vwap'], 'volatility': 0.15}
        
        buy_price = context.buy_prices[symbol]['price']
        if buy_price <= 0: continue
            
        try:
            current_price = history_n(symbol=symbol, frequency='1d', count=1, end_time=last_day, fields='close', adjust=ADJUST_PREV, adjust_end_time=context.custom_end_time, df=False)[0]['close']
        except: continue

        stock_vol = calculate_stock_volatility(symbol, context, last_day)
        context.buy_prices[symbol]['volatility'] = stock_vol
        stop_loss_pct = context.stop_loss_max if stock_vol > 0.35 else (0.135 if stock_vol > 0.25 else context.stop_loss_base)
        loss_pct = (current_price - buy_price) / buy_price

        if loss_pct <= -stop_loss_pct:
            print('{}: [动态止损] {} 亏损{:.2%} (止损线:{:.1%})'.format(now_str, symbol, loss_pct, stop_loss_pct))
            order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Market, position_side=PositionSide_Long, price=0)
            if symbol in context.buy_prices: del context.buy_prices[symbol]

def calculate_stock_volatility(symbol, context, trade_date):
    try:
        hist = history_n(symbol=symbol, frequency='1d', count=context.volatility_period + 10, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.volatility_period: return 0.2
        returns = np.diff(hist['close'].values) / hist['close'].values[:-1]
        return min(np.std(returns[-context.volatility_period:]) * np.sqrt(252), 0.5)
    except: return 0.2

def do_rebalance(context, now_str, last_day, market_vol):
    position_ratio = get_dynamic_position_ratio(context, market_vol)
    if context.market_status == 'neutral': position_ratio *= 0.8
    best_index = select_best_style(context, last_day)
    hot_sectors = identify_hot_sectors(context, last_day)
    context.hot_sectors = hot_sectors
    
    symbols = list(set(list(stk_get_index_constituents(index=best_index, trade_date=last_day)['symbol'])))
    stocks_info = get_symbols(sec_type1=1010, symbols=symbols, trade_date=now_str, skip_suspended=True, skip_st=True)
    symbols = list(set([item['symbol'] for item in stocks_info if item['listed_date'] < context.now and item['delisted_date'] > context.now]))
    
    selected_stocks = score_and_select_stocks(context, symbols, last_day, now_str, hot_sectors)
    if not selected_stocks: return
    symbols_pool = [s['symbol'] for s in selected_stocks]
    execute_rebalance(context, now_str, last_day, symbols_pool, position_ratio)

def select_best_style(context, trade_date):
    return_index = pd.DataFrame(columns=['return', 'trend_score', 'volatility_score'])
    for index_symbol in context.index_list:
        hist = history_n(symbol=index_symbol, frequency='1d', count=context.ma_medium + 10, end_time=trade_date, fields='close', fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.ma_medium: continue
        closes = hist['close'].values
        return_20d = closes[-1] / closes[-21] - 1 if len(closes) >= 21 else 0
        ma20, ma60 = np.mean(closes[-context.ma_short:]), np.mean(closes[-context.ma_medium:])
        trend_score = (1 if closes[-1] > ma20 else 0) + (1 if ma20 > ma60 else 0)
        # Calculate 20-day volatility: take last 21 closes to get 20 returns
        recent_closes = closes[-21:] if len(closes) >= 21 else closes
        returns = np.diff(recent_closes) / recent_closes[:-1]
        volatility = np.std(returns) * np.sqrt(252)
        return_index.loc[index_symbol] = [return_20d, trend_score, max(0, 1 - volatility / 0.3)]
    return_index['total_score'] = return_index['return'] * 0.6 + return_index['trend_score'] * 0.25 + return_index['volatility_score'] * 0.15
    return return_index['total_score'].idxmax()

def identify_hot_sectors(context, trade_date):
    sector_momentum = {}
    for index_symbol in context.index_list:
        hist = history_n(symbol=index_symbol, frequency='1d', count=context.sector_lookback + 1, end_time=trade_date, fields='close', fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.sector_lookback + 1: continue
        momentum = (hist['close'].values[-1] - hist['close'].values[0]) / hist['close'].values[0]
        name = '大盘蓝筹' if '000016' in index_symbol else '中大盘' if '000300' in index_symbol else '中小盘'
        sector_momentum[name] = momentum
    return [s[0] for s in sorted(sector_momentum.items(), key=lambda x: x[1], reverse=True) if s[1] > 0]

def score_and_select_stocks(context, symbols, trade_date, now_str, hot_sectors):
    scores = []
    for symbol in symbols:
        try:
            quality, value, momentum = calculate_quality_score(symbol, context, trade_date), calculate_value_score(symbol, context, trade_date), calculate_momentum_score(symbol, context, trade_date)
            if quality < context.min_quality_score: continue
            sector = calculate_sector_score(symbol, context, trade_date, hot_sectors)
            scores.append({'symbol': symbol, 'quality': quality, 'value': value, 'momentum': momentum, 'sector': sector, 'total': quality * 0.35 + value * 0.25 + momentum * 0.25 + sector * 0.15})
        except: continue
    if not scores: return []
    return pd.DataFrame(scores).sort_values('total', ascending=False).head(context.holding_num).to_dict('records')

def calculate_quality_score(symbol, context, trade_date):
    try:
        hist = history_n(symbol=symbol, frequency='1d', count=context.ma_long + 20, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.ma_long: return 0
        closes = hist['close'].values
        ma60_first, ma60_last = np.mean(closes[-context.ma_long-20:-context.ma_long+40]), np.mean(closes[-context.ma_long:])
        trend_score = max(0, min(1, ((ma60_last - ma60_first) / ma60_first if ma60_first > 0 else 0) * 5))
        volatility_score = max(0, 1 - (np.std(np.diff(closes) / closes[:-1]) * np.sqrt(252)) / 0.5)
        return trend_score * 0.3 + volatility_score * 0.3 + max(0, min(1, ((closes[-1] - closes[-context.ma_long]) / closes[-context.ma_long]) * 2)) * 0.4
    except: return 0

def calculate_value_score(symbol, context, trade_date):
    try:
        hist = history_n(symbol=symbol, frequency='1d', count=context.ma_vlong + 10, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.ma_vlong: return 0
        price = hist['close'].values[-1]
        r60, r120, r250 = price / np.mean(hist['close'].values[-60:]), price / np.mean(hist['close'].values[-120:]), price / np.mean(hist['close'].values[-250:])
        score = (0.5 if r250 < 0.85 else 0.5 * (1.35 - r250) / 0.5 if r250 < 1.35 else 0) + (0.3 if r120 < 0.9 else 0.3 * (1.25 - r120) / 0.35 if r120 < 1.25 else 0) + (0.2 if r60 < 1.15 else -0.2 if r60 > 1.3 else 0)
        return max(0, min(1, score))
    except: return 0

def calculate_momentum_score(symbol, context, trade_date):
    try:
        hist = history_n(symbol=symbol, frequency='1d', count=context.momentum_days + 10, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.momentum_days + 5: return 0
        mom = (hist['close'].values[-1] - hist['close'].values[-context.momentum_days-1]) / hist['close'].values[-context.momentum_days-1]
        if -0.15 <= mom <= 0.3: return 0.6 + mom * 1.5
        elif mom > 0.3: return max(0, 1 - (mom - 0.3))
        else: return max(0, 0.6 + mom * 2)
    except: return 0

def calculate_sector_score(symbol, context, trade_date, hot_sectors):
    return min(1, 0.7 if hot_sectors else 0.5)

def execute_rebalance(context, now_str, last_day, symbols_pool, position_ratio):
    try: positions = context.account().positions()
    except: positions = get_position()
    
    percent = position_ratio / len(symbols_pool) if len(symbols_pool) > 0 and position_ratio > 0 else 0

    # 统一使用 OrderType_Market 确保100%成交
    for pos in positions:
        try: symbol = pos.symbol
        except: symbol = pos['symbol']
        if symbol not in symbols_pool:
            order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Market, position_side=PositionSide_Long, price=0)
            if symbol in context.buy_prices: del context.buy_prices[symbol]

    current_positions = [p.symbol if hasattr(p, 'symbol') else p['symbol'] for p in positions]
    for symbol in symbols_pool:
        if symbol not in current_positions and percent > 0:
            order_target_percent(symbol=symbol, percent=percent, order_type=OrderType_Market, position_side=PositionSide_Long, price=0)
            context.buy_prices[symbol] = {'price': 0, 'volatility': 0.2}

def clear_all_positions(context, now_str, last_day):
    try: positions = context.account().positions()
    except: positions = get_position()
    for pos in positions:
        try: symbol = pos.symbol
        except: symbol = pos['symbol']
        order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Market, position_side=PositionSide_Long, price=0)
        if symbol in context.buy_prices: del context.buy_prices[symbol]

def on_order_status(context, order):
    # 兼容对象和字典的读取，实现完美回调打印
    try:
        status, effect, side = order.status, order.position_effect, order.side
        symbol, price, tgt_pct = order.symbol, order.price, order.target_percent
    except AttributeError:
        status, effect, side = order['status'], order['position_effect'], order['side']
        symbol, price, tgt_pct = order['symbol'], order['price'], order['target_percent']

    if status == 3: # 订单完全成交
        action = ''
        if effect == 1 and side == 1: 
            action = '开多仓'
        # 核心修复：A股卖出是“平昨仓”(effect=4)，期货等才是“平仓”(effect=2)
        elif (effect == 2 or effect == 4) and side == 2: 
            action = '平多仓'
        
        if action:
            # 修复百分比显示：tgt_pct 已经是 0.05 这种小数了，不用再除以100
            print('{}:标的：{}，操作：以市价{}，委托价格：{}，目标仓位：{:.2%}'.format(
                context.now, symbol, action, price, tgt_pct if tgt_pct else 0))
            if action == '开多仓' and symbol in context.buy_prices:
                context.buy_prices[symbol]['price'] = price

def on_backtest_finished(context, indicator):
    print('*'*50 + '\n回测已完成！\n' + '='*50 + '\n【回测结果摘要】')
    for key, value in indicator.items(): print('{}: {}'.format(key, value))

if __name__ == '__main__':
    run(strategy_id='strategy_id',
        filename='style_rotation_v3',
        mode=MODE_BACKTEST,
        token=token,
        backtest_start_time='2024-01-01 08:00:00',
        backtest_end_time='2026-01-31 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)