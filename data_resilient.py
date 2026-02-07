import pandas as pd
import akshare as ak
import time
import random
import os
from datetime import datetime
from cache_manager import CacheManager
from data_sources import MultiSourceDataFetcher, SinaDataSource, EfinanceDataSource, AkshareBackupSource, BaostockDataSource

# Disable proxy for all requests
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('ALL_PROXY', None)
os.environ.pop('all_proxy', None)

# Configure curl_cffi to disable proxy
try:
    from curl_cffi import requests as curl_requests
    curl_requests.session.defaults = {'proxy': None}
except ImportError:
    pass
except Exception:
    pass


class DataResilient:
    """
    韧性数据获取类
    支持多数据源自动切换
    """

    # 类变量：多数据源获取器
    _multi_source_fetcher = MultiSourceDataFetcher()

    @staticmethod
    def fetch_stock_data(symbol: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
        """
        获取股票历史数据，支持多数据源自动切换

        Args:
            symbol: 股票代码 (如 000001.SZ)
            start_date: 开始日期 (格式: 20240101)
            end_date: 结束日期 (格式: 20240131)
            use_cache: 是否使用缓存

        Returns:
            DataFrame with columns: date, open, close, high, low, volume
        """
        # 检查缓存
        if use_cache:
            cached_data = CacheManager.load_stock_cache(symbol, start_date, end_date)
            if cached_data is not None:
                return cached_data

        # 使用多数据源获取
        df = DataResilient._fetch_with_multi_source(symbol, start_date, end_date)

        # 保存缓存
        if use_cache and df is not None and not df.empty:
            CacheManager.save_stock_cache(symbol, start_date, end_date, df)

        return df

    @staticmethod
    def _fetch_with_multi_source(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        使用多数据源获取数据，自动切换失败的数据源
        """
        print(f"获取 {symbol} 数据 ({start_date} - {end_date})...")

        df = DataResilient._multi_source_fetcher.fetch_stock_data(
            symbol, start_date, end_date, verbose=True
        )

        if df is None or df.empty:
            raise Exception(f"所有数据源均无法获取 {symbol} 的数据")

        return df

    @staticmethod
    def _fetch_with_retry_akshare(symbol: str, start_date: str, end_date: str, max_retries: int = 3) -> pd.DataFrame:
        """
        使用akshare获取数据（备用方法）
        """
        for attempt in range(max_retries + 1):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=symbol.split('.')[0],  # akshare不需要后缀
                    period="daily",
                    start_date=start_date,
                    end_date=end_date
                )

                if df is None or df.empty:
                    raise ValueError(f"获取数据为空: {symbol}")

                df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume'
                }, inplace=True)

                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)

                return df

            except Exception as e:
                if attempt < max_retries:
                    delay = random.uniform(1, 3)
                    print(f"重试获取 {symbol} (第{attempt + 1}次) - 延迟 {delay:.1f}秒...")
                    time.sleep(delay)
                else:
                    print(f"Akshare获取 {symbol} 失败: {str(e)}")
                    raise

    @staticmethod
    def fetch_macro_data(data_type: str, use_cache: bool = True) -> pd.DataFrame:
        if use_cache:
            cached_data = CacheManager.load_macro_cache(data_type)
            if cached_data is not None:
                return cached_data

        df = DataResilient._fetch_macro_with_retry(data_type)

        if use_cache and df is not None and not df.empty:
            CacheManager.save_macro_cache(data_type, df)

        return df

    @staticmethod
    def _fetch_macro_with_retry(data_type: str, max_retries: int = 3) -> pd.DataFrame:
        fetch_functions = {
            'cpi': lambda: ak.macro_china_cpi(),
            'gdp': lambda: ak.macro_china_gdp(),
            'pmi': lambda: ak.macro_china_pmi(),
            'fx': lambda: ak.fx_spot_quote()
        }

        if data_type not in fetch_functions:
            raise ValueError(f"不支持的宏观数据类型: {data_type}")

        for attempt in range(max_retries + 1):
            try:
                df = fetch_functions[data_type]()

                if df is None:
                    df = pd.DataFrame()

                return df

            except Exception as e:
                if attempt < max_retries:
                    delay = random.uniform(1, 3)
                    print(f"重试获取 {data_type} 数据 (第{attempt + 1}次) - 延迟 {delay:.1f}秒...")
                    time.sleep(delay)
                else:
                    print(f"获取 {data_type} 数据失败: {str(e)}")
                    return pd.DataFrame()

    @staticmethod
    def get_stock_info(use_cache: bool = True) -> pd.DataFrame:
        cache_key = 'stock_info'

        if use_cache:
            cached_data = CacheManager.load_macro_cache(cache_key)
            if cached_data is not None:
                return cached_data

        try:
            df = ak.stock_info_a_code_name()

            if use_cache and df is not None and not df.empty:
                CacheManager.save_macro_cache(cache_key, df)

            return df
        except Exception as e:
            print(f"获取股票信息失败: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def get_hs300_symbols(use_cache: bool = True) -> list:
        cache_key = 'hs300_symbols'

        if use_cache:
            cached_data = CacheManager.load_macro_cache(cache_key)
            if cached_data is not None:
                return cached_data

        try:
            hs300 = ak.index_stock_cons(symbol="000300")
            hs300 = hs300.drop_duplicates(subset=['品种代码'], keep='first')
            hs300['symbol'] = hs300['品种代码'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(6)
            hs300['symbol'] = hs300['symbol'].apply(lambda x: f"{x}.SZ" if x.startswith(('0','3')) else f"{x}.SH")
            symbols = hs300['symbol'].drop_duplicates().tolist()

            if use_cache:
                CacheManager.save_macro_cache(cache_key, symbols)

            return symbols
        except Exception as e:
            print(f"获取沪深300成分股失败: {str(e)}")
            return []

    @staticmethod
    def print_data_source_status():
        """打印数据源状态统计"""
        DataResilient._multi_source_fetcher.print_status()
