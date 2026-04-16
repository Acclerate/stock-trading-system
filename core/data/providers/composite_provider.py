"""Composite data provider backed by the existing repository data layer."""

from __future__ import annotations

import pandas as pd

from core.data.cache import V2CacheManager
from data.data_resilient import DataResilient

REQUIRED_PRICE_COLUMNS = ("open", "high", "low", "close", "volume")
INDEX_SYMBOL_ALIASES = {
    "300": "000300",
    "905": "000905",
    "852": "000852",
}
INDEX_SYMBOLS = {"000300", "000852", "000905", "399001", "399006"}


class CompositeDataProvider:
    """Expose normalized access to the current multi-source data backend."""

    def __init__(self) -> None:
        V2CacheManager.initialize()

    def fetch_price_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        base_code, canonical_symbol = self._normalize_symbol(symbol)
        df = DataResilient.fetch_stock_data(
            symbol=base_code,
            start_date=start_date,
            end_date=end_date,
            use_cache=use_cache,
        )
        return self._normalize_price_frame(df, canonical_symbol)

    def fetch_macro_data(self, data_type: str, use_cache: bool = True) -> pd.DataFrame:
        df = DataResilient.fetch_macro_data(data_type=data_type, use_cache=use_cache)
        if df is None:
            return pd.DataFrame()
        return df.copy()

    def get_stock_info(self, use_cache: bool = True) -> pd.DataFrame:
        df = DataResilient.get_stock_info(use_cache=use_cache)
        return self._normalize_stock_info(df)

    def get_hs300_symbols(self, use_cache: bool = True) -> list[str]:
        raw_symbols = DataResilient.get_hs300_symbols(use_cache=use_cache)
        normalized_symbols: list[str] = []
        seen_symbols: set[str] = set()
        for symbol in raw_symbols:
            _, canonical_symbol = self._normalize_symbol(symbol)
            if canonical_symbol in seen_symbols:
                continue
            seen_symbols.add(canonical_symbol)
            normalized_symbols.append(canonical_symbol)
        return normalized_symbols

    @staticmethod
    def _normalize_symbol(symbol: str) -> tuple[str, str]:
        raw_symbol = symbol.strip().upper()
        if not raw_symbol:
            raise ValueError("symbol must not be empty")

        if raw_symbol in INDEX_SYMBOL_ALIASES:
            raw_symbol = INDEX_SYMBOL_ALIASES[raw_symbol]

        if raw_symbol in INDEX_SYMBOLS:
            return raw_symbol, raw_symbol

        if raw_symbol.startswith(("SHSE.", "SZSE.")):
            market, code = raw_symbol.split(".", 1)
            if code in INDEX_SYMBOLS:
                return code, code
            suffix = ".SH" if market == "SHSE" else ".SZ"
            return code, f"{code}{suffix}"

        if raw_symbol.endswith((".SH", ".SZ")):
            code = raw_symbol[:6]
            if code in INDEX_SYMBOLS:
                return code, code
            return code, raw_symbol

        if len(raw_symbol) == 6 and raw_symbol.isdigit():
            suffix = ".SH" if raw_symbol.startswith(("5", "6", "9")) else ".SZ"
            return raw_symbol, f"{raw_symbol}{suffix}"

        raise ValueError(f"unsupported symbol format: {symbol}")

    @staticmethod
    def _normalize_price_frame(df: pd.DataFrame, canonical_symbol: str) -> pd.DataFrame:
        if df is None or df.empty:
            raise ValueError(f"no price data returned for {canonical_symbol}")

        normalized = df.copy()
        if any(column not in normalized.columns for column in REQUIRED_PRICE_COLUMNS):
            normalized = DataResilient._standardize_dataframe(normalized)

        if "date" in normalized.columns:
            normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
            normalized = normalized.set_index("date")
        elif not isinstance(normalized.index, pd.DatetimeIndex):
            normalized.index = pd.to_datetime(normalized.index, errors="coerce")
        else:
            normalized.index = pd.to_datetime(normalized.index, errors="coerce")

        normalized = normalized[~normalized.index.isna()]
        normalized.index.name = "date"
        normalized = normalized.sort_index()
        normalized = normalized[~normalized.index.duplicated(keep="last")]

        missing_columns = [column for column in REQUIRED_PRICE_COLUMNS if column not in normalized.columns]
        if missing_columns:
            raise ValueError(
                f"{canonical_symbol} price data missing required columns: {', '.join(missing_columns)}"
            )

        for column in REQUIRED_PRICE_COLUMNS:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

        normalized = normalized.dropna(subset=list(REQUIRED_PRICE_COLUMNS))
        if normalized.empty:
            raise ValueError(f"{canonical_symbol} price data became empty after normalization")

        normalized.attrs["canonical_symbol"] = canonical_symbol
        normalized.attrs["base_code"] = canonical_symbol.split(".", 1)[0] if "." in canonical_symbol else canonical_symbol
        return normalized

    @classmethod
    def _normalize_stock_info(cls, df: pd.DataFrame | None) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["code", "name", "symbol"])

        normalized = df.copy()

        if "code" not in normalized.columns and "symbol" in normalized.columns:
            normalized["code"] = normalized["symbol"].astype(str).str.extract(r"(\d{6})")[0]

        if "name" not in normalized.columns:
            if "sec_name" in normalized.columns:
                normalized["name"] = normalized["sec_name"]
            else:
                normalized["name"] = ""

        if "code" not in normalized.columns:
            raise ValueError("stock info data missing code column")

        normalized["code"] = normalized["code"].astype(str).str.extract(r"(\d{6})")[0]
        normalized = normalized.dropna(subset=["code"]).drop_duplicates(subset=["code"], keep="first")
        normalized["symbol"] = normalized["code"].map(lambda value: cls._normalize_symbol(value)[1])
        return normalized[["code", "name", "symbol"]].reset_index(drop=True)
