import pandas as pd
import talib

"""指标计算模块"""
class Indicators:
    @staticmethod
    def calculate_indicators(df):
        """计算技术指标：均线、MACD、RSI、BOLL、成交量（使用TA-Lib）"""
        close = df['close'].values

        # 均线
        df['ma5'] = talib.SMA(close, timeperiod=5)
        df['ma20'] = talib.SMA(close, timeperiod=20)

        # MACD
        macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist

        # RSI
        df['rsi'] = talib.RSI(close, timeperiod=14)

        # BOLL
        boll_upper, boll_mid, boll_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
        df['boll_upper'] = boll_upper
        df['boll_mid'] = boll_mid
        df['boll_lower'] = boll_lower

        # 成交量指标
        df['volume_ma3'] = df['volume'].rolling(window=3).mean()
        df['volume_pct_change'] = (df['volume'] / df['volume_ma3'].shift(1)) - 1

        return df
