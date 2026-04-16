from datetime import date

import pandas as pd
import pytest

from core.data.loaders import PriceLoadRequest, PriceLoader


class StubProvider:
    def __init__(self):
        self.calls = []

    def fetch_price_history(self, symbol, start_date, end_date, use_cache=True):
        self.calls.append((symbol, start_date, end_date, use_cache))
        return pd.DataFrame(
            {
                "open": [10.0, 10.5],
                "high": [10.2, 10.8],
                "low": [9.9, 10.3],
                "close": [10.1, 10.6],
                "volume": [1000, 1100],
            },
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )


def test_load_coerces_dates_to_yyyymmdd():
    provider = StubProvider()
    loader = PriceLoader(provider=provider)

    result = loader.load(
        PriceLoadRequest(
            symbol="600000",
            start_date=date(2024, 1, 1),
            end_date=pd.Timestamp("2024-01-03"),
        )
    )

    assert len(result) == 2
    assert provider.calls == [("600000", "20240101", "20240103", True)]


def test_load_price_history_uses_convenience_api():
    provider = StubProvider()
    loader = PriceLoader(provider=provider)

    loader.load_price_history("000001.SZ", "2024-01-01", "2024-01-03", use_cache=False)

    assert provider.calls == [("000001.SZ", "20240101", "20240103", False)]


def test_load_rejects_invalid_min_rows():
    loader = PriceLoader(provider=StubProvider())

    with pytest.raises(ValueError, match="min_rows must be at least 1"):
        loader.load(PriceLoadRequest(symbol="600000", start_date="20240101", end_date="20240103", min_rows=0))


def test_load_rejects_when_result_too_short():
    loader = PriceLoader(provider=StubProvider())

    with pytest.raises(ValueError, match="fewer than required 3"):
        loader.load(PriceLoadRequest(symbol="600000", start_date="20240101", end_date="20240103", min_rows=3))


def test_load_rejects_unparseable_dates():
    loader = PriceLoader(provider=StubProvider())

    with pytest.raises(ValueError, match="start_date could not be parsed"):
        loader.load(PriceLoadRequest(symbol="600000", start_date="bad-date", end_date="20240103"))
