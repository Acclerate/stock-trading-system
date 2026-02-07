"""
Technical indicators helper module using numpy/pandas
Replaces pandas_ta for Windows compatibility
"""
import pandas as pd
import numpy as np


def add_indicators(df):
    """Add technical indicators to dataframe"""
    # Moving averages
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()

    # MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp12 - exp26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df['boll_mid'] = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    df['boll_upper'] = df['boll_mid'] + (std * 2)
    df['boll_lower'] = df['boll_mid'] - (std * 2)

    # Volume indicators
    df['volume_ma3'] = df['volume'].rolling(window=3).mean()
    df['volume_pct_change'] = (df['volume'] / df['volume_ma3'].shift(1)) - 1

    # ADX for market regime
    df['adx'] = calculate_adx(df, 14)

    return df.dropna()


def calculate_adx(df, period=14):
    """Calculate Average Directional Index"""
    high = df['high']
    low = df['low']
    close = df['close']

    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    df['+dm'] = high.diff()
    df['-dm'] = -low.diff()

    df['+dm'] = df['+dm'].where((df['+dm'] > 0) & (df['+dm'] > df['-dm']), 0)
    df['-dm'] = df['-dm'].where((df['-dm'] > 0) & (df['-dm'] > df['+dm']), 0)

    # Smoothed values
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    df['+di'] = 100 * (df['+dm'].ewm(alpha=1/period, adjust=False).mean() / atr)
    df['-di'] = 100 * (df['-dm'].ewm(alpha=1/period, adjust=False).mean() / atr)

    # DX and ADX
    dx = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    # Clean up temporary columns
    df.drop(['+dm', '-dm', '+di', '-di'], axis=1, inplace=True, errors='ignore')

    return adx
