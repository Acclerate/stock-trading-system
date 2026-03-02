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
LOG_FILE = os.path.join(os.path.dirname(__file__), 'backtest_log_style_ml_enhanced.txt')

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
    from sklearn.preprocessing import StandardScaler
except:
    import os
    os.system('pip install scikit-learn')
    from sklearn import svm
    from sklearn.preprocessing import StandardScaler

'''
风格轮动 + ML增强策略
ML作为辅助信号：
1. 对选出的股票用ML预测上涨概率
2. 只买入概率 >= 阈值的股票
3. 根据预测概率动态调整仓位权重
'''

# ========== 板块映射 ==========
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
    '其他': []
}

for key in SECTOR_MAPPING:
    SECTOR_MAPPING['其他'].extend([v for v in SECTOR_MAPPING[key] if v not in SECTOR_MAPPING['其他']])

# ========== 初始化 ==========
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
    context.custom_end_time = '2026-02-28 16:00:00'

    # ML相关参数
    context.ml_training_len = 180
    context.ml_history_len = 20
    context.ml_prob_threshold = 0.55  # ML概率阈值，只买入预测概率>=55%的股票
    context.ml_enabled = True  # 是否启用ML过滤

    schedule(schedule_func=algo, date_rule='1d', time_rule='09:31:00')


# ========== 主策略 ==========
def algo(context):
    now = context.now
    now_str = now.strftime('%Y-%m-%d')
    last_day = get_previous_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]

    # 检查季度调仓
    if now.month in context.rebalance_months and context.last_rebalance_month != now.month:
        market_signal = check_market_trend(context, last_day)
        context.market_status = market_signal['status']
        context.market_volatility = market_signal['volatility']

        if context.market_status == '极度看空':
            clear_all_positions(context, now_str, last_day)
            print(f'{now_str}: 市场极度看空，清空所有仓位')
        else:
            # 获取股票池
            symbols_pool = get_stock_pool(context)
            if symbols_pool:
                # ML增强：预测每只股票的上涨概率
                ml_scores = predict_stock_probs(context, symbols_pool, now_str)

                # 结合ML分数调整选股
                selected = score_and_select_stocks_ml(context, symbols_pool, last_day, now_str, ml_scores)

                if selected:
                    # 动态调整仓位
                    if context.market_status == '极度看多':
                        position_ratio = context.max_position_ratio
                    elif context.market_status == '看多':
                        position_ratio = context.base_position_ratio
                    elif context.market_status == '看空':
                        position_ratio = context.min_position_ratio
                    else:
                        position_ratio = 0.6

                    # 根据ML预测动态调整持仓数量
                    if len(selected) < context.holding_num // 2:
                        position_ratio *= 0.7

                    execute_rebalance(context, now_str, last_day, [s['symbol'] for s in selected], position_ratio)
                    print(f'{now_str}: 季度调仓日，市场状态: {context.market_status}, 持仓: {len(selected)}只')
                else:
                    print(f'{now_str}: 季度调仓日，无符合条件的股票')

        context.last_rebalance_month = now.month

    # 动态止损检查（每周执行）
    if now.weekday() == 5:  # 周五
        check_dynamic_stop_loss(context, now_str, last_day)


# ========== ML增强：预测股票上涨概率 ==========
def predict_stock_probs(context, symbols, end_date):
    """
    用ML预测每只股票的上涨概率
    返回: {symbol: probability}
    """
    if not context.ml_enabled:
        return {s: 0.5 for s in symbols}

    ml_scores = {}
    scaler = StandardScaler()

    # 批量获取所有股票的历史数据
    all_features = []
    valid_symbols = []

    for symbol in symbols:
        try:
            features = extract_stock_features(symbol, context, end_date)
            if features is not None:
                all_features.append(features)
                valid_symbols.append(symbol)
        except:
            ml_scores[symbol] = 0.5

    if len(all_features) < 10:
        return {s: 0.5 for s in symbols}

    # 标准化特征
    try:
        all_features_scaled = scaler.fit_transform(all_features)
    except:
        return {s: 0.5 for s in symbols}

    # 训练模型并预测
    try:
        # 使用市场指数数据训练
        index_data = history_n(symbol=context.market_index, frequency='1d',
                              count=context.ml_training_len + 50, end_time=end_date,
                              fields='close,high,low,volume',
                              fill_missing='Last', adjust=ADJUST_PREV, df=True)

        if len(index_data) < context.ml_history_len + 50:
            return {s: 0.5 for s in symbols}

        # 准备训练数据
        x_train, y_train = prepare_training_data(index_data, context)

        if len(x_train) < 30:
            return {s: 0.5 for s in symbols}

        x_train_scaled = scaler.fit_transform(x_train)

        # 训练SVM
        clf = svm.SVC(C=5.0, kernel='rbf', gamma='scale', probability=True,
                      class_weight='balanced', random_state=42)
        clf.fit(x_train_scaled, y_train)

        # 预测每只股票
        probs = clf.predict_proba(all_features_scaled)[:, 1]

        for i, symbol in enumerate(valid_symbols):
            ml_scores[symbol] = probs[i]

        # 对未成功预测的股票赋予默认概率
        for symbol in symbols:
            if symbol not in ml_scores:
                ml_scores[symbol] = 0.5

    except Exception as e:
        print(f'ML预测出错: {e}')
        return {s: 0.5 for s in symbols}

    return ml_scores


def extract_stock_features(symbol, context, end_date):
    """提取单只股票的特征"""
    data = history_n(symbol=symbol, frequency='1d', count=context.ml_history_len + 20,
                     end_time=end_date, fields='close,high,low,volume',
                     fill_missing='Last', adjust=ADJUST_PREV, df=True)

    if len(data) < context.ml_history_len:
        return None

    close = data['close'].values[-context.ml_history_len:]
    high = data['high'].values[-context.ml_history_len:]
    low = data['low'].values[-context.ml_history_len:]
    volume = data['volume'].values[-context.ml_history_len:]

    # 基础特征
    close_mean = close[-1] / np.mean(close)
    return_rate = (close[-1] - close[0]) / close[0]
    volatility = np.std(close) / np.mean(close) if np.mean(close) > 0 else 0

    # 技术指标
    rsi = calculate_rsi(close)

    # 价格动量
    momentum_5 = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0
    momentum_10 = (close[-1] - close[-10]) / close[-10] if len(close) >= 10 else 0

    # 趋势特征
    ma_short = np.mean(close[-5:])
    ma_long = np.mean(close[-20:])
    trend = (ma_short - ma_long) / ma_long if ma_long > 0 else 0

    # 返回7个特征（与训练数据一致）
    return [close_mean, return_rate, volatility, rsi, momentum_5, momentum_10, trend]


def prepare_training_data(index_data, context):
    """准备训练数据"""
    # 检查是否有eob列，如果没有则使用行索引
    if 'eob' in index_data.columns:
        data = index_data.set_index('eob')
    else:
        data = index_data.copy()

    x_train = []
    y_train = []
    close_values = data['close'].values

    for i in range(context.ml_history_len + 10, len(close_values) - 5):
        close = close_values[i - context.ml_history_len:i]

        if len(close) < context.ml_history_len:
            continue

        close_mean = close[-1] / np.mean(close)
        return_rate = (close[-1] - close[0]) / close[0]
        volatility = np.std(close) / np.mean(close) if np.mean(close) > 0 else 0

        rsi = calculate_rsi(close)
        momentum_5 = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0
        momentum_10 = (close[-1] - close[-10]) / close[-10] if len(close) >= 10 else 0

        ma_short = np.mean(close[-5:])
        ma_long = np.mean(close[-20:])
        trend = (ma_short - ma_long) / ma_long if ma_long > 0 else 0

        x_train.append([close_mean, return_rate, volatility, rsi, momentum_5, momentum_10, trend])

        # 标签：未来5天是否上涨
        future_close = close_values[i+1:i+6]
        label = 1 if future_close[-1] > future_close[0] * 1.005 else 0
        y_train.append(label)

    return x_train, y_train


def calculate_rsi(prices, period=14):
    """计算RSI"""
    if len(prices) < period + 1:
        return 50
    deltas = np.diff(prices)
    gain = np.where(deltas > 0, deltas, 0)
    loss = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ========== ML增强选股 ==========
def score_and_select_stocks_ml(context, symbols, trade_date, now_str, ml_scores):
    """
    ML增强的选股函数
    结合多因子评分和ML预测概率
    """
    scores = []
    hot_sectors = get_hot_sectors(context, trade_date)

    for symbol in symbols:
        try:
            quality = calculate_quality_score(symbol, context, trade_date)
            if quality < context.min_quality_score:
                continue

            value = calculate_value_score(symbol, context, trade_date)
            momentum = calculate_momentum_score(symbol, context, trade_date)
            sector = calculate_sector_score(symbol, context, trade_date, hot_sectors)

            # 获取ML预测概率
            ml_prob = ml_scores.get(symbol, 0.5)

            # ML概率过滤：低于阈值的不考虑
            if ml_prob < context.ml_prob_threshold:
                continue

            # 综合评分 = 多因子评分 * 0.7 + ML概率 * 0.3
            factor_score = quality * 0.35 + value * 0.25 + momentum * 0.25 + sector * 0.15
            total_score = factor_score * 0.7 + ml_prob * 0.3

            scores.append({
                'symbol': symbol,
                'quality': quality,
                'value': value,
                'momentum': momentum,
                'sector': sector,
                'ml_prob': ml_prob,
                'total': total_score
            })
        except:
            continue

    if not scores:
        return []

    # 按综合评分排序，取前N只
    scores = sorted(scores, key=lambda x: x['total'], reverse=True)

    # 输出ML增强信息
    print(f'  ML预测结果（前5只）:')
    for s in scores[:5]:
        print(f'    {s["symbol"]}: 多因子={s["quality"]*0.35+s["value"]*0.25+s["momentum"]*0.25+s["sector"]*0.15:.3f}, ML概率={s["ml_prob"]:.2%}, 综合={s["total"]:.3f}')

    return scores[:context.holding_num]


# ========== 以下是原风格轮动策略的核心函数 ==========
def get_stock_pool(context):
    """获取股票池 - 选择最佳风格的指数成分股"""
    last_day = context.now.strftime('%Y-%m-%d')
    now_str = last_day

    # 选择最佳风格指数
    best_index = select_best_style(context, last_day)

    # 获取成分股
    try:
        symbols = list(set(list(stk_get_index_constituents(index=best_index, trade_date=last_day)['symbol'])))
        stocks_info = get_symbols(sec_type1=1010, symbols=symbols, trade_date=now_str,
                                  skip_suspended=True, skip_st=True)
        symbols = list(set([item['symbol'] for item in stocks_info
                           if item['listed_date'] < context.now and item['delisted_date'] > context.now]))
        return symbols
    except Exception as e:
        print(f'获取股票池出错: {e}')
        return []

def select_best_style(context, trade_date):
    """选择最佳风格指数"""
    style_scores = {}
    for index in context.index_list:
        try:
            hist = history_n(symbol=index, frequency='1d', count=context.ma_long + 20,
                           end_time=trade_date, fields='close', adjust=ADJUST_PREV, df=True)
            if len(hist) < context.ma_long:
                continue
            closes = hist['close'].values
            ma60_first = np.mean(closes[-context.ma_long-20:-context.ma_long+40]) if len(closes) >= context.ma_long + 20 else np.mean(closes[:-context.ma_long])
            ma60_last = np.mean(closes[-context.ma_long:])
            momentum = (ma60_last - ma60_first) / ma60_first if ma60_first > 0 else 0
            volatility = np.std(np.diff(closes[-context.volatility_period:]) / closes[-context.volatility_period:-1]) * np.sqrt(252) if len(closes) > context.volatility_period else 0.2
            sharpe = momentum / (volatility + 0.01) if volatility > 0 else 0
            style_scores[index] = sharpe
        except:
            continue

    if not style_scores:
        return context.market_index

    return max(style_scores, key=style_scores.get)

def get_hot_sectors(context, trade_date):
    """获取热门板块"""
    sector_momentum = {}
    for sector_name in SECTOR_MAPPING.keys():
        if sector_name == '其他':
            continue
        try:
            hist = history_n(symbol=context.market_index, frequency='1d', count=context.sector_lookback + 1,
                           end_time=trade_date, fields='close', adjust=ADJUST_PREV, df=True)
            if len(hist) < context.sector_lookback:
                continue
            momentum = (hist['close'].values[-1] - hist['close'].values[0]) / hist['close'].values[0]
            sector_momentum[sector_name] = momentum
        except:
            continue
    return [s for s in sorted(sector_momentum.items(), key=lambda x: x[1], reverse=True) if s[1] > 0]

def check_market_trend(context, trade_date):
    """检查市场趋势"""
    try:
        hist = history_n(symbol=context.market_index, frequency='1d', count=context.ma_vlong + 10, end_time=trade_date, fields='close', fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.ma_vlong:
            return {'status': 'neutral', 'volatility': 0.15}
        closes = hist['close'].values
        ma20, ma60, ma250 = np.mean(closes[-context.ma_short:]), np.mean(closes[-context.ma_medium:]), np.mean(closes[-context.ma_long:])
        volatility = np.std(np.diff(closes[-context.volatility_period:]) / closes[-context.volatility_period:-1]) * np.sqrt(252) if len(closes) > context.volatility_period else 0.15
        ma20_60_slope = (ma20 - ma60) / ma60 if ma60 > 0 else 0
        if ma20 > ma250 * 1.05 and ma20_60_slope > 0.02 and volatility < 0.25:
            return {'status': '极度看多', 'volatility': volatility}
        elif ma20 > ma60 * 1.02 and volatility < 0.25:
            return {'status': '看多', 'volatility': volatility}
        elif ma20 < ma250 * 0.95 and ma20_60_slope < -0.02:
            return {'status': '极度看空', 'volatility': volatility}
        elif ma20 < ma60 * 0.98:
            return {'status': '看空', 'volatility': volatility}
        else:
            return {'status': 'neutral', 'volatility': volatility}
    except:
        return {'status': 'neutral', 'volatility': 0.15}

def get_hot_sectors(context, trade_date):
    """获取热门板块"""
    return []

def calculate_quality_score(symbol, context, trade_date):
    try:
        hist = history_n(symbol=symbol, frequency='1d', count=context.ma_long + 20, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.ma_long:
            return 0
        closes = hist['close'].values
        ma60_first = np.mean(closes[-context.ma_long-20:-context.ma_long+40]) if len(closes) >= context.ma_long + 20 else np.mean(closes[:-context.ma_long])
        ma60_last = np.mean(closes[-context.ma_long:])
        trend_score = max(0, min(1, ((ma60_last - ma60_first) / ma60_first if ma60_first > 0 else 0) * 5))
        volatility_score = max(0, 1 - (np.std(np.diff(closes) / closes[:-1]) * np.sqrt(252)) / 0.5)
        return trend_score * 0.3 + volatility_score * 0.3 + max(0, min(1, ((closes[-1] - closes[-context.ma_long]) / closes[-context.ma_long]) * 2)) * 0.4
    except:
        return 0

def calculate_value_score(symbol, context, trade_date):
    try:
        hist = history_n(symbol=symbol, frequency='1d', count=context.ma_vlong + 10, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.ma_vlong:
            return 0
        price = hist['close'].values[-1]
        r60 = price / np.mean(hist['close'].values[-60:])
        r120 = price / np.mean(hist['close'].values[-120:])
        r250 = price / np.mean(hist['close'].values[-250:])
        score = (0.5 if r250 < 0.85 else 0.5 * (1.35 - r250) / 0.5 if r250 < 1.35 else 0) + (0.3 if r120 < 0.9 else 0.3 * (1.25 - r120) / 0.35 if r120 < 1.25 else 0) + (0.2 if r60 < 1.15 else -0.2 if r60 > 1.3 else 0)
        return max(0, min(1, score))
    except:
        return 0

def calculate_momentum_score(symbol, context, trade_date):
    try:
        hist = history_n(symbol=symbol, frequency='1d', count=context.momentum_days + 10, end_time=trade_date, fields='close', skip_suspended=True, fill_missing='Last', adjust=ADJUST_PREV, df=True)
        if len(hist) < context.momentum_days + 5:
            return 0
        mom = (hist['close'].values[-1] - hist['close'].values[-context.momentum_days-1]) / hist['close'].values[-context.momentum_days-1]
        if -0.15 <= mom <= 0.3:
            return 0.6 + mom * 1.5
        elif mom > 0.3:
            return max(0, 1 - (mom - 0.3))
        else:
            return max(0, 0.6 + mom * 2)
    except:
        return 0

def calculate_sector_score(symbol, context, trade_date, hot_sectors):
    return min(1, 0.7 if hot_sectors else 0.5)

def execute_rebalance(context, now_str, last_day, symbols_pool, position_ratio):
    try:
        positions = context.account().positions()
    except:
        positions = get_position()

    percent = position_ratio / len(symbols_pool) if len(symbols_pool) > 0 and position_ratio > 0 else 0

    for pos in positions:
        try:
            symbol = pos.symbol
        except:
            symbol = pos['symbol']
        if symbol not in symbols_pool:
            order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Market, position_side=PositionSide_Long, price=0)
            if symbol in context.buy_prices:
                del context.buy_prices[symbol]

    current_positions = [p.symbol if hasattr(p, 'symbol') else p['symbol'] for p in positions]
    for symbol in symbols_pool:
        if symbol not in current_positions and percent > 0:
            order_target_percent(symbol=symbol, percent=percent, order_type=OrderType_Market, position_side=PositionSide_Long, price=0)
            context.buy_prices[symbol] = {'price': 0, 'volatility': 0.2}

def clear_all_positions(context, now_str, last_day):
    try:
        positions = context.account().positions()
    except:
        positions = get_position()
    for pos in positions:
        try:
            symbol = pos.symbol
        except:
            symbol = pos['symbol']
        order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Market, position_side=PositionSide_Long, price=0)
        if symbol in context.buy_prices:
            del context.buy_prices[symbol]

def check_dynamic_stop_loss(context, now_str, last_day):
    """动态止损"""
    try:
        positions = context.account().positions()
    except:
        positions = get_position()

    for pos in positions:
        try:
            symbol = pos.symbol
            current_price = pos.price
            vwap = pos.vwap
            amount = pos.amount
        except:
            symbol = pos['symbol']
            continue

        if symbol in context.buy_prices:
            buy_price = context.buy_prices[symbol]['price']
            if buy_price == 0:
                context.buy_prices[symbol]['price'] = vwap
                buy_price = vwap

            profit_loss_pct = (current_price - buy_price) / buy_price if buy_price > 0 else 0

            stop_loss = context.stop_loss_base
            if context.market_status == '看空' or context.market_status == '极度看空':
                stop_loss = context.stop_loss_max

            if profit_loss_pct <= -stop_loss:
                order_target_percent(symbol=symbol, percent=0, order_type=OrderType_Market, position_side=PositionSide_Long, price=0)
                print(f'{now_str}: [动态止损] {symbol} 亏损{profit_loss_pct*100:.2f}% (止损线:{stop_loss*100:.0f}%)')
                if symbol in context.buy_prices:
                    del context.buy_prices[symbol]

def on_order_status(context, order):
    try:
        status, effect, side = order.status, order.position_effect, order.side
        symbol, price, tgt_pct = order.symbol, order.price, order.target_percent
    except AttributeError:
        status, effect, side = order['status'], order['position_effect'], order['side']
        symbol, price, tgt_pct = order['symbol'], order['price'], order['target_percent']

    if status == 3:
        action = ''
        if effect == 1 and side == 1:
            action = '开多仓'
        elif (effect == 2 or effect == 4) and side == 2:
            action = '平多仓'

        if action:
            print('{}:标的：{}，操作：以市价{}，委托价格：{}，目标仓位：{:.2%}'.format(
                context.now, symbol, action, price, tgt_pct if tgt_pct else 0))
            if action == '开多仓' and symbol in context.buy_prices:
                context.buy_prices[symbol]['price'] = price

def on_backtest_finished(context, indicator):
    print('*'*50 + '\n回测已完成！\n' + '='*50 + '\n【回测结果摘要】')
    for key, value in indicator.items():
        print(f'{key}: {value}')

if __name__ == '__main__':
    run(strategy_id='strategy_id',
        filename='style_ml_enhanced',
        mode=MODE_BACKTEST,
        token=token,
        backtest_start_time='2024-01-01 08:00:00',
        backtest_end_time='2026-01-31 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
