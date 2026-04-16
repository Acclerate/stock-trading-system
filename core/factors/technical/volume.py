"""Volume-oriented technical factor helpers."""

from __future__ import annotations

import pandas as pd


def add_volume_averages(df: pd.DataFrame, *, windows: tuple[int, ...]) -> pd.DataFrame:
    result = df.copy()
    for window in windows:
        rolling = result["volume"].rolling(window=window).mean()
        result[f"volume_ma{window}"] = rolling
        result[f"vol_ma{window}"] = rolling
    return result


def add_volume_features(
    df: pd.DataFrame,
    *,
    short_window: int = 5,
    base_window: int = 20,
    long_window: int = 60,
) -> pd.DataFrame:
    result = df.copy()

    short_column = f"volume_ma{short_window}"
    base_column = f"volume_ma{base_window}"
    long_column = f"volume_ma{long_window}"

    if short_column not in result.columns or base_column not in result.columns or long_column not in result.columns:
        raise ValueError("volume moving averages must be computed before volume features")

    result["vol_ratio"] = result["volume"] / result[short_column]
    result["volume_pct_change"] = result["volume"].pct_change(fill_method=None)
    result["volume_expansion"] = result[short_column] / result[base_column]
    result["volume_trend"] = result[base_column] / result[long_column]
    return result
