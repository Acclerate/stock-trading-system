"""Historical price loader for v2 strategies."""

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from core.data.providers import CompositeDataProvider


@dataclass(slots=True, frozen=True)
class PriceLoadRequest:
    """Single historical price loading request."""

    symbol: str
    start_date: str | date | datetime | pd.Timestamp
    end_date: str | date | datetime | pd.Timestamp
    min_rows: int = 1
    use_cache: bool = True


class PriceLoader:
    """Strategy-facing wrapper around the shared composite provider."""

    def __init__(self, provider: CompositeDataProvider | None = None) -> None:
        self.provider = provider or CompositeDataProvider()

    def load(self, request: PriceLoadRequest) -> pd.DataFrame:
        if request.min_rows < 1:
            raise ValueError("min_rows must be at least 1")

        start_date = self._coerce_ymd(request.start_date, field_name="start_date")
        end_date = self._coerce_ymd(request.end_date, field_name="end_date")

        df = self.provider.fetch_price_history(
            symbol=request.symbol,
            start_date=start_date,
            end_date=end_date,
            use_cache=request.use_cache,
        )

        if len(df) < request.min_rows:
            raise ValueError(
                f"{request.symbol} only returned {len(df)} rows, fewer than required {request.min_rows}"
            )

        return df

    def load_price_history(
        self,
        symbol: str,
        start_date: str | date | datetime | pd.Timestamp,
        end_date: str | date | datetime | pd.Timestamp,
        *,
        min_rows: int = 1,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        return self.load(
            PriceLoadRequest(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                min_rows=min_rows,
                use_cache=use_cache,
            )
        )

    @staticmethod
    def _coerce_ymd(
        value: str | date | datetime | pd.Timestamp,
        *,
        field_name: str,
    ) -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if len(normalized) == 8 and normalized.isdigit():
                return normalized
            timestamp = pd.to_datetime(normalized, errors="coerce")
        elif isinstance(value, (date, datetime, pd.Timestamp)):
            timestamp = pd.Timestamp(value)
        else:
            raise TypeError(f"{field_name} must be a string or date-like value")

        if pd.isna(timestamp):
            raise ValueError(f"{field_name} could not be parsed: {value}")

        return timestamp.strftime("%Y%m%d")
