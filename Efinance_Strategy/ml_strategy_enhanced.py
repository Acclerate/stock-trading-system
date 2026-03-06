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
LOG_FILE = os.path.join(os.path.dirname(__file__), 'backtest_log_ml_optimized.txt')

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
机器学习策略优化版
改进点：
1. 增强特征工程：添加技术指标（MACD、RSI、布林带、动量）
2. 特征标准化：使用StandardScaler
3. 概率阈值：只用高置信度预测
4. 优化交易规则：技术指标过滤 + 动态止盈止损
5. 市场环境判断：趋势/震荡市场自适应
'''

def init(context):
    # 股票标的
    context.symbol = 'SHSE.600000'
    # 历史窗口长度，N
    context.history_len = 20
    # 预测窗口长度，M
    context.forecast_len = 5
    # 训练样本长度（增加到180天）
    context.training_len = 180
    # 止盈幅度（动态）
    context.earn_rate = 0.08
    # 止损幅度（动态）
    context.stop_loss_rate = 0.05
    # 预测概率阈值（只使用高置信度预测）
    context.prob_threshold = 0.65
    # 每日09:31执行策略
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:31:00')


def algo(context):
    now = context.now
    now_str = now.strftime('%Y-%m-%d')
    weekday = now.isoweekday()
    position = get_position()

    # 获取当前价格和行情数据
    current_data = history_n(symbol=context.symbol, frequency='1d', count=context.history_len + 20,
                             end_time=now_str, fields='close,high,low,volume',
                             adjust=ADJUST_PREV, df=True)
    if len(current_data) < context.history_len + 10:
        return

    current_price = current_data['close'].iloc[-1]

    # 计算市场环境指标
    market_state = check_market_state(current_data)

    # 如果当前时间是星期一且没有仓位，则开始预测
    if weekday == 1 and not position:
        # 获取预测用的历史数据
        result = clf_fit(context, now_str)
        if result is None:
            return

        prediction, probability = result

        # 综合判断：模型预测 + 技术指标过滤 + 市场环境
        if prediction == 1 and probability >= context.prob_threshold:
            # 技术指标确认
            tech_confirm = check_technical_indicators(current_data)

            if tech_confirm and market_state != 'bearish':
                # 动态调整仓位：牛市100%，震荡市70%，熊市不操作
                if market_state == 'bullish':
                    target_pos = 1.0
                elif market_state == 'neutral':
                    target_pos = 0.7
                else:
                    target_pos = 0.0

                if target_pos > 0:
                    order_target_percent(symbol=context.symbol, percent=target_pos,
                                       order_type=OrderType_Market, position_side=PositionSide_Long)

    # 动态止盈止损
    elif position:
        entry_price = position[0]['vwap']
        profit_pct = (current_price - entry_price) / entry_price

        # 止盈
        if profit_pct >= context.earn_rate:
            order_close_all()
        # 止损
        elif profit_pct <= -context.stop_loss_rate:
            order_close_all()
        # 时间止损（持有超过20天）
        elif hasattr(context, 'hold_days') and context.hold_days >= 20:
            order_close_all()
        # 技术止损：跌破均线
        elif current_price < current_data['close'].iloc[-20:].mean() * 0.97:
            order_close_all()


def check_market_state(data):
    """判断市场状态：牛市/震荡/熊市"""
    close = data['close'].values
    # 计算短期和长期均线
    ma_short = np.mean(close[-20:])
    ma_long = np.mean(close[-60:])

    # 计算RSI
    rsi = calculate_rsi(close, 14)

    # 判断市场状态
    if ma_short > ma_long * 1.02 and rsi < 70:
        return 'bullish'
    elif ma_short < ma_long * 0.98:
        return 'bearish'
    else:
        return 'neutral'


def calculate_rsi(prices, period=14):
    """计算RSI指标"""
    deltas = np.diff(prices)
    gain = np.where(deltas > 0, deltas, 0)
    loss = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def check_technical_indicators(data):
    """技术指标确认"""
    close = data['close'].values

    # 1. 短期趋势：MA5 > MA20
    ma5 = np.mean(close[-5:])
    ma20 = np.mean(close[-20:])

    # 2. RSI不超买
    rsi = calculate_rsi(close, 14)

    # 3. 价格在布林带中下轨附近
    bb_middle = np.mean(close[-20:])
    bb_std = np.std(close[-20:])
    bb_upper = bb_middle + 2 * bb_std
    bb_lower = bb_middle - 2 * bb_std
    current_price = close[-1]

    # 综合判断
    conditions = [
        ma5 > ma20 * 0.998,  # 短期均线向上
        rsi < 70,             # RSI不超买
        current_price > bb_lower * 0.98,  # 不在布林带下轨破位
        current_price < bb_upper * 1.02,  # 不在布林带上轨超买
    ]

    return sum(conditions) >= 3  # 至少满足3个条件


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    prices = pd.Series(prices)
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]


def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """计算布林带"""
    ma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    return ma, upper, lower


def clf_fit(context, end_date):
    """训练支持向量机模型（优化版）"""
    # 获取更多历史数据
    recent_data = history_n(symbol=context.symbol, frequency='1d',
                           count=context.training_len + 50, end_time=end_date,
                           fill_missing='Last', adjust=ADJUST_PREV, df=True).set_index('eob')

    if len(recent_data) < context.history_len + 50:
        return None

    x_train = []
    y_train = []

    # 整理训练数据
    for index in range(context.history_len + 20, len(recent_data)):
        data = recent_data.iloc[index-context.history_len-20:index]
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values
        volume = data['volume'].values

        # ===== 原始特征 =====
        close_mean = close[-1] / np.mean(close)
        volume_mean = volume[-1] / np.mean(volume) if np.mean(volume) > 0 else 1
        max_mean = high[-1] / np.mean(high)
        min_mean = low[-1] / np.mean(low)
        vol = volume[-1]
        return_now = close[-1] / close[0]
        std = np.std(close)

        # ===== 新增技术指标特征 =====
        # MACD
        macd, signal, hist = calculate_macd(close)
        # RSI
        rsi = calculate_rsi(close)
        # 布林带位置
        bb_mid, bb_upper, bb_lower = calculate_bollinger_bands(close)
        bb_position = (close[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5
        # 动量
        momentum = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0
        # 波动率
        volatility = np.std(np.diff(close) / close[:-1]) * np.sqrt(252) if len(close) > 1 else 0

        # 组合特征
        features = [close_mean, volume_mean, max_mean, min_mean, vol,
                   return_now, std, macd, signal, hist, rsi, bb_position,
                   momentum, volatility]

        x_train.append(features)

        # 标签：未来5天是否上涨
        if index < len(recent_data) - context.forecast_len:
            future_close = recent_data['close'].iloc[index+1:index+context.forecast_len+1].values
            if future_close[-1] > future_close[0] * 1.01:  # 至少上涨1%
                label = 1
            else:
                label = 0
            y_train.append(label)

    # 剔除最后forecast_len期
    x_train = x_train[:-context.forecast_len] if len(x_train) > context.forecast_len else x_train

    if len(x_train) < 20 or len(y_train) < 20:
        return None

    # 特征标准化
    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)

    # 训练优化的SVM
    context.scaler = scaler
    context.clf = svm.SVC(
        C=10.0,                    # 增大正则化参数
        kernel='rbf',
        gamma=0.1,                 # 显式指定gamma
        probability=True,          # 启用概率预测
        class_weight='balanced',   # 处理样本不平衡
        cache_size=500,
        random_state=42
    )
    context.clf.fit(x_train_scaled, y_train)

    # 准备预测数据
    data = recent_data.iloc[-context.history_len-20:]
    close = data['close'].values
    high = data['high'].values
    low = data['low'].values
    volume = data['volume'].values

    close_mean = close[-1] / np.mean(close)
    volume_mean = volume[-1] / np.mean(volume) if np.mean(volume) > 0 else 1
    max_mean = high[-1] / np.mean(high)
    min_mean = low[-1] / np.mean(low)
    vol = volume[-1]
    return_now = close[-1] / close[0]
    std = np.std(close)

    macd, signal, hist = calculate_macd(close)
    rsi = calculate_rsi(close)
    bb_mid, bb_upper, bb_lower = calculate_bollinger_bands(close)
    bb_position = (close[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5
    momentum = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0
    volatility = np.std(np.diff(close) / close[:-1]) * np.sqrt(252) if len(close) > 1 else 0

    new_x = [close_mean, volume_mean, max_mean, min_mean, vol,
            return_now, std, macd, signal, hist, rsi, bb_position,
            momentum, volatility]

    # 标准化预测数据
    new_x_scaled = scaler.transform([new_x])

    # 获取预测和概率
    prediction = context.clf.predict(new_x_scaled)[0]
    probability = context.clf.predict_proba(new_x_scaled)[0, 1]  # 上涨概率

    return prediction, probability


def on_order_status(context, order):
    symbol = order['symbol']
    price = order['price']
    target_percent = order['target_percent']
    status = order['status']
    side = order['side']
    effect = order['position_effect']
    order_type = order['order_type']

    if status == 3:
        action = ''
        if effect == 1 and side == 1:
            action = '开多仓'
        elif (effect == 2 or effect == 4) and side == 2:
            action = '平多仓'

        if action:
            order_type_word = '限价' if order_type==1 else '市价'
            tgt_pct = target_percent if target_percent <= 1 else target_percent / 100
            print('{}:标的：{}，操作：以{}{}，委托价格：{}，目标仓位：{:.2%}'.format(
                context.now, symbol, order_type_word, action, price, tgt_pct if tgt_pct else 0))


def on_backtest_finished(context, indicator):
    print('*'*50)
    print('回测已完成，请通过右上角"回测历史"功能查询详情。')
    print('【回测结果摘要】')
    for key, value in indicator.items():
        print(f'{key}: {value}')


if __name__ == '__main__':
    run(strategy_id='strategy_id',
        filename='机器学习_优化版',
        mode=MODE_BACKTEST,
        token=token,
        backtest_start_time='2025-02-01 09:30:00',
        backtest_end_time='2026-02-28 15:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
