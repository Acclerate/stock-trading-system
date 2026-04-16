import pandas as pd

from core.data.providers import CompositeDataProvider


def test_fetch_price_history_normalizes_frame(monkeypatch):
    raw_df = pd.DataFrame(
        {
            "日期": ["2024-01-03", "2024-01-02", "2024-01-02"],
            "开盘": ["10.0", "9.5", "9.6"],
            "最高": ["10.5", "9.8", "9.9"],
            "最低": ["9.8", "9.2", "9.3"],
            "收盘": ["10.2", "9.7", "9.8"],
            "成交量": ["1000", "900", "950"],
        }
    )

    def fake_fetch_stock_data(symbol, start_date, end_date, use_cache):
        assert symbol == "600000"
        assert start_date == "20240101"
        assert end_date == "20240103"
        assert use_cache is True
        return raw_df

    monkeypatch.setattr(
        "core.data.providers.composite_provider.DataResilient.fetch_stock_data",
        fake_fetch_stock_data,
    )

    provider = CompositeDataProvider()
    result = provider.fetch_price_history("SHSE.600000", "20240101", "20240103")

    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert list(result.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert result.loc[pd.Timestamp("2024-01-02"), "close"] == 9.8
    assert result.attrs["canonical_symbol"] == "600000.SH"
    assert result.index.name == "date"


def test_get_stock_info_adds_canonical_symbol(monkeypatch):
    stock_info = pd.DataFrame(
        {
            "code": ["600000", "000001"],
            "name": ["浦发银行", "平安银行"],
        }
    )

    monkeypatch.setattr(
        "core.data.providers.composite_provider.DataResilient.get_stock_info",
        lambda use_cache: stock_info,
    )

    provider = CompositeDataProvider()
    result = provider.get_stock_info()

    assert list(result.columns) == ["code", "name", "symbol"]
    assert result["symbol"].tolist() == ["600000.SH", "000001.SZ"]


def test_get_hs300_symbols_deduplicates_and_normalizes(monkeypatch):
    monkeypatch.setattr(
        "core.data.providers.composite_provider.DataResilient.get_hs300_symbols",
        lambda use_cache: ["600000", "600000.SH", "SZSE.000001"],
    )

    provider = CompositeDataProvider()

    assert provider.get_hs300_symbols() == ["600000.SH", "000001.SZ"]
