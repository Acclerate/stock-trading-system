"""Volatility-oriented technical factor helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_bollinger_bands(
    df: pd.DataFrame,
    *,
    period: int = 20,
    std_num: float = 2.0,
) -> pd.DataFrame:
    result = df.copy()
    result["boll_mid"] = result["close"].rolling(window=period).mean()
    rolling_std = result["close"].rolling(window=period).std()
    result["boll_upper"] = result["boll_mid"] + rolling_std * std_num
    result["boll_lower"] = result["boll_mid"] - rolling_std * std_num
    result["boll_width"] = (result["boll_upper"] - result["boll_lower"]) / result["boll_mid"]
    result["boll_position"] = (result["close"] - result["boll_lower"]) / (
        result["boll_upper"] - result["boll_lower"]
    )
    result.loc[(result["boll_upper"] - result["boll_lower"]) == 0, "boll_position"] = 0.5
    return result


def add_volatility_indicators(
    df: pd.DataFrame,
    *,
    atr_period: int = 14,
    adx_period: int = 14,
) -> pd.DataFrame:
    result = df.copy()

    previous_close = result["close"].shift(1)
    true_range = pd.concat(
        [
            result["high"] - result["low"],
            (result["high"] - previous_close).abs(),
            (result["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    result["true_range"] = true_range
    result[f"atr{atr_period}"] = true_range.rolling(window=atr_period).mean()

    up_move = result["high"].diff()
    down_move = -result["low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=result.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=result.index,
    )

    tr_sum = true_range.rolling(window=adx_period).sum()
    plus_di = 100 * (plus_dm.rolling(window=adx_period).sum() / tr_sum)
    minus_di = 100 * (minus_dm.rolling(window=adx_period).sum() / tr_sum)
    directional_index = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    result[f"plus_di{adx_period}"] = plus_di
    result[f"minus_di{adx_period}"] = minus_di
    result[f"adx{adx_period}"] = directional_index.rolling(window=adx_period).mean()
    return result
