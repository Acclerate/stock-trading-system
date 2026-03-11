#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时强弱分析配置文件
用户可以在这里修改订阅的股票列表和参数
"""

# ========== 订阅配置 ==========
# 订阅的股票列表（掘金格式）
# 用户可以自由添加/删除股票
STOCK_LIST = [
    'SHSE.600644',  # 乐山电力
    'SZSE.000818',  # 航锦科技
    'SZSE.002202',  # 金风科技
    'SZSE.000988',  # 华工科技
]

# K线频率
FREQUENCY = '60s'  # 1分钟K线

# ========== 告警配置 ==========
ALERT_THRESHOLDS = {
    'strong': 70,      # 强势告警阈值（综合评分）
    'weak': 30,        # 弱势告警阈值
    'surge': 5,        # 短期涨幅告警(%)
    'plunge': -5,      # 短期跌幅告警(%)
    'rsi_overbought': 75,   # RSI超买告警
    'rsi_oversold': 25,     # RSI超卖告警
}

# 告警冷却时间（秒）- 避免重复告警
ALERT_COOLDOWN = 300

# ========== 数据持久化配置 ==========
OUTPUT_DIR = 'outputs/realtime_strength'
SAVE_INTERVAL = 60  # 每60个bar保存一次数据
LOG_TO_FILE = True
LOG_FILE = 'realtime_strength.log'  # 日志文件名（不带路径，会自动存到logs目录）

# ========== 技术指标参数 ==========
MA_SHORT = 5
MA_LONG = 20
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
RSI_PERIOD = 14
BOLL_PERIOD = 20
BOLL_STD = 2
ADX_PERIOD = 14
ATR_PERIOD = 14

# ========== 掘金SDK配置 ==========
# Token从环境变量读取，或在这里直接设置（不推荐提交到git）
# DIGGOLD_TOKEN = os.getenv('DIGGOLD_TOKEN', '')

# ========== 策略参数 ==========
# 最小K线数量（用于计算技术指标）
MIN_BARS_FOR_ANALYSIS = 30

# 数据存储窗口（保留最近N条数据）
DATA_WINDOW_SIZE = 1000

# 是否启用声音告警
ENABLE_SOUND_ALERT = True

# 是否启用数据持久化
ENABLE_DATA_PERSISTENCE = True
