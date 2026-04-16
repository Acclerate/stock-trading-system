import numpy as np
import pandas as pd

from core.factors import TechnicalFactorConfig, build_technical_factor_frame


def build_sample_price_frame(rows=320):
    index = pd.date_range("2023-01-01", periods=rows, freq="D")
    close = pd.Series(np.linspace(10.0, 20.0, rows), index=index)
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 0.4,
            "low": close - 0.5,
            "close": close,
            "volume": np.linspace(1_000_000, 2_000_000, rows),
        },
        index=index,
    )


def test_build_technical_factor_frame_adds_pilot_columns():
    df = build_sample_price_frame()

    factors = build_technical_factor_frame(df)

    expected_columns = {
        "ma5",
        "ma10",
        "ma20",
        "ma30",
        "ma60",
        "volume_ma5",
        "volume_ma20",
        "volume_ma60",
        "vol_ma5",
        "vol_ma10",
        "vol_ma20",
        "price_position",
        "volume_expansion",
        "volume_trend",
        "trend_strength",
        "recent_return_5",
        "amplitude_120",
        "amplitude_250",
        "macd",
        "macd_signal",
        "macd_hist",
        "rsi",
        "boll_upper",
        "boll_mid",
        "boll_lower",
        "boll_width",
        "boll_position",
        "true_range",
        "atr14",
        "adx14",
    }

    assert expected_columns.issubset(factors.columns)


def test_build_technical_factor_frame_matches_low_volume_breakout_core_formulas():
    df = build_sample_price_frame()
    config = TechnicalFactorConfig(price_position_window=250, amplitude_windows=(120, 250), trend_ma_window=60)

    factors = build_technical_factor_frame(df, config=config)
    latest = factors.iloc[-1]

    expected_price_position = latest["close"] / latest["high_250"]
    expected_volume_expansion = latest["volume_ma5"] / latest["volume_ma20"]
    expected_volume_trend = latest["volume_ma20"] / latest["volume_ma60"]
    expected_trend_strength = latest["close"] / latest["ma60"]

    assert latest["price_position"] == expected_price_position
    assert latest["volume_expansion"] == expected_volume_expansion
    assert latest["volume_trend"] == expected_volume_trend
    assert latest["trend_strength"] == expected_trend_strength


def test_build_technical_factor_frame_rejects_missing_columns():
    df = pd.DataFrame({"close": [1, 2, 3]})

    try:
        build_technical_factor_frame(df)
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected missing-column validation to raise ValueError")
