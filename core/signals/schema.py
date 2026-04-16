"""Standard signal schema shared by v2 strategies and outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Any, Iterable

import pandas as pd

SIGNAL_COLUMNS = [
    "symbol",
    "trade_date",
    "strategy_name",
    "action",
    "score",
    "price",
    "position_hint",
    "tags",
    "risk_flags",
    "reason",
    "metadata",
]


class SignalAction(str, Enum):
    BUY = "buy"
    WAIT = "wait"
    SELL = "sell"


@dataclass(slots=True)
class SignalRecord:
    symbol: str
    trade_date: str | pd.Timestamp
    strategy_name: str
    action: SignalAction | str
    score: float
    price: float | None = None
    position_hint: float | None = None
    tags: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "symbol": self._normalize_symbol(self.symbol),
            "trade_date": self._normalize_trade_date(self.trade_date),
            "strategy_name": self.strategy_name,
            "action": self._normalize_action(self.action).value,
            "score": float(self.score),
            "price": None if self.price is None else float(self.price),
            "position_hint": None if self.position_hint is None else float(self.position_hint),
            "tags": json.dumps(self.tags, ensure_ascii=False),
            "risk_flags": json.dumps(self.risk_flags, ensure_ascii=False),
            "reason": self.reason,
            "metadata": json.dumps(self.metadata, ensure_ascii=False, sort_keys=True),
        }

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("signal symbol must not be empty")
        return normalized

    @staticmethod
    def _normalize_trade_date(trade_date: str | pd.Timestamp) -> pd.Timestamp:
        timestamp = pd.to_datetime(trade_date, errors="coerce")
        if pd.isna(timestamp):
            raise ValueError(f"invalid trade_date: {trade_date}")
        return timestamp.normalize()

    @staticmethod
    def _normalize_action(action: SignalAction | str) -> SignalAction:
        if isinstance(action, SignalAction):
            return action
        normalized = action.strip().lower()
        return SignalAction(normalized)


def signals_to_frame(records: Iterable[SignalRecord]) -> pd.DataFrame:
    rows = [record.to_row() for record in records]
    frame = pd.DataFrame(rows, columns=SIGNAL_COLUMNS)
    return normalize_signal_frame(frame)


def normalize_signal_frame(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    for column in SIGNAL_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = None

    normalized = normalized[SIGNAL_COLUMNS]
    normalized["symbol"] = normalized["symbol"].astype(str).str.strip().str.upper()
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"], errors="coerce").dt.normalize()
    normalized["strategy_name"] = normalized["strategy_name"].astype(str).str.strip()
    normalized["action"] = normalized["action"].astype(str).str.strip().str.lower()
    normalized["score"] = pd.to_numeric(normalized["score"], errors="coerce")
    normalized["price"] = pd.to_numeric(normalized["price"], errors="coerce")
    normalized["position_hint"] = pd.to_numeric(normalized["position_hint"], errors="coerce")
    normalized["reason"] = normalized["reason"].fillna("").astype(str)
    normalized["tags"] = normalized["tags"].apply(_coerce_json_string)
    normalized["risk_flags"] = normalized["risk_flags"].apply(_coerce_json_string)
    normalized["metadata"] = normalized["metadata"].apply(_coerce_json_string)

    invalid_rows = normalized[
        normalized["symbol"].eq("")
        | normalized["trade_date"].isna()
        | normalized["strategy_name"].eq("")
        | normalized["action"].eq("")
        | normalized["score"].isna()
    ]
    if not invalid_rows.empty:
        raise ValueError("signal frame contains invalid required fields")

    return normalized


def _coerce_json_string(value: Any) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "[]"
        return stripped
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, (list, tuple, set)):
        return json.dumps(list(value), ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)
