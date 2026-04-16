import pandas as pd
import pytest

from core.signals import (
    SignalAction,
    SignalRecord,
    filter_by_action,
    filter_by_min_score,
    normalize_signal_frame,
    signals_to_frame,
    weighted_score,
)


def test_signals_to_frame_normalizes_records():
    frame = signals_to_frame(
        [
            SignalRecord(
                symbol="600000.sh",
                trade_date="2024-06-28 15:00:00",
                strategy_name="low_volume_breakout_v2",
                action=SignalAction.BUY,
                score=87.5,
                price=7.68,
                position_hint=0.2,
                tags=["breakout", "volume"],
                risk_flags=["rsi-high"],
                reason="放量突破",
                metadata={"source": "pilot"},
            )
        ]
    )

    row = frame.iloc[0]
    assert row["symbol"] == "600000.SH"
    assert row["trade_date"] == pd.Timestamp("2024-06-28")
    assert row["action"] == "buy"
    assert row["tags"] == '["breakout", "volume"]'
    assert row["risk_flags"] == '["rsi-high"]'
    assert row["metadata"] == '{"source": "pilot"}'


def test_normalize_signal_frame_rejects_missing_required_fields():
    frame = pd.DataFrame([{"symbol": "", "trade_date": None, "strategy_name": "", "action": "", "score": None}])

    with pytest.raises(ValueError, match="invalid required fields"):
        normalize_signal_frame(frame)


def test_signal_filters_and_weighted_score_work_together():
    frame = signals_to_frame(
        [
            SignalRecord("600000.SH", "2024-06-28", "lvb", "buy", 90),
            SignalRecord("000001.SZ", "2024-06-28", "lvb", "wait", 45),
        ]
    )

    assert len(filter_by_min_score(frame, 50)) == 1
    assert len(filter_by_action(frame, "buy")) == 1
    assert weighted_score((0.6, 0.5), (0.8, 0.5)) == 0.7
