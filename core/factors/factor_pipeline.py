"""Shared technical factor pipeline for pilot v2 strategies."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .technical import (
    add_bollinger_bands,
    add_macd,
    add_moving_averages,
    add_price_position_features,
    add_rsi,
    add_volume_averages,
    add_volume_features,
    add_volatility_indicators,
)

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(slots=True)
class TechnicalFactorConfig:
    ma_windows: tuple[int, ...] = (5, 10, 20, 30, 60)
    volume_windows: tuple[int, ...] = (5, 10, 20, 60)
    price_position_window: int = 250
    amplitude_windows: tuple[int, ...] = (120, 250)
    rsi_period: int = 14
    boll_period: int = 20
    boll_std: float = 2.0
    atr_period: int = 14
    adx_period: int = 14
    trend_ma_window: int = 60


def build_technical_factor_frame(
    df: pd.DataFrame,
    config: TechnicalFactorConfig | None = None,
) -> pd.DataFrame:
    """Build a reusable technical factor frame from normalized OHLCV input."""

    config = config or TechnicalFactorConfig()
    _validate_input_frame(df)

    factors = df.copy()
    factors = add_moving_averages(factors, windows=config.ma_windows)
    factors = add_volume_averages(factors, windows=config.volume_windows)
    factors = add_price_position_features(
        factors,
        price_position_window=config.price_position_window,
        amplitude_windows=config.amplitude_windows,
        trend_ma_window=config.trend_ma_window,
    )
    factors = add_volume_features(factors)
    factors = add_macd(factors)
    factors = add_rsi(factors, period=config.rsi_period)
    factors = add_bollinger_bands(
        factors,
        period=config.boll_period,
        std_num=config.boll_std,
    )
    factors = add_volatility_indicators(
        factors,
        atr_period=config.atr_period,
        adx_period=config.adx_period,
    )
    return factors


def _validate_input_frame(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        raise ValueError("input price frame must not be empty")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"input price frame missing required columns: {', '.join(missing_columns)}")
