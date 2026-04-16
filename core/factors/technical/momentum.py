"""Momentum-oriented technical factor helpers."""

from __future__ import annotations

import pandas as pd


def add_macd(
    df: pd.DataFrame,
    *,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    result = df.copy()
    exp_fast = result["close"].ewm(span=fast_period, adjust=False).mean()
    exp_slow = result["close"].ewm(span=slow_period, adjust=False).mean()
    result["macd"] = exp_fast - exp_slow
    result["macd_signal"] = result["macd"].ewm(span=signal_period, adjust=False).mean()
    result["macd_hist"] = result["macd"] - result["macd_signal"]
    return result


def add_rsi(df: pd.DataFrame, *, period: int = 14) -> pd.DataFrame:
    result = df.copy()
    delta = result["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    result["rsi"] = 100 - (100 / (1 + rs))
    return result
