"""Trend-oriented technical factor helpers."""

from __future__ import annotations

import pandas as pd


def add_moving_averages(df: pd.DataFrame, *, windows: tuple[int, ...]) -> pd.DataFrame:
    result = df.copy()
    for window in windows:
        result[f"ma{window}"] = result["close"].rolling(window=window).mean()
    return result


def add_price_position_features(
    df: pd.DataFrame,
    *,
    price_position_window: int,
    amplitude_windows: tuple[int, ...],
    trend_ma_window: int,
) -> pd.DataFrame:
    result = df.copy()

    high_column = f"high_{price_position_window}"
    low_column = f"low_{price_position_window}"
    result[high_column] = result["high"].rolling(window=price_position_window).max()
    result[low_column] = result["low"].rolling(window=price_position_window).min()
    result["price_position"] = result["close"] / result[high_column]

    ma_column = f"ma{trend_ma_window}"
    if ma_column not in result.columns:
        result[ma_column] = result["close"].rolling(window=trend_ma_window).mean()
    result["trend_strength"] = result["close"] / result[ma_column]
    result["recent_return_5"] = result["close"].pct_change(periods=5, fill_method=None)

    for window in amplitude_windows:
        rolling_high = result["high"].rolling(window=window).max()
        rolling_low = result["low"].rolling(window=window).min()
        result[f"amplitude_{window}"] = (rolling_high - rolling_low) / rolling_low

    ma20 = result["close"].rolling(window=20).mean()
    result["trend_slope_20"] = ma20.pct_change(periods=5, fill_method=None)
    return result
