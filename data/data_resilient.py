"""
数据获取模块 - 使用东财掘金SDK作为默认数据源
多数据源容错机制，掘金SDK优先
"""
import pandas as pd
import akshare as ak
import time
import random
import os
from datetime import datetime
from .cache_manager import CacheManager
from config_data_source import DATA_SOURCE_CONFIG, get_enabled_sources

# 强制禁用所有代理（解决 Connection aborted 问题）
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

# 配置 requests 禁用代理
try:
    import requests
    requests.Session().trust_env = False
except:
    pass

# 配置 curl_cffi 禁用代理
try:
    from curl_cffi import requests as curl_requests
    curl_requests.session.defaults = {'proxy': None}
except:
    pass

# ========== 尝试导入各数据源 ==========
DIGGOLD_AVAILABLE = False
DIGGOLD_TOKEN = None

try:
    from gm.api import set_token, history, history_n, get_instruments
    DIGGOLD_AVAILABLE = True
    DIGGOLD_TOKEN = DATA_SOURCE_CONFIG['sources']['diggold']['token']
    # 初始化掘金SDK
    set_token(DIGGOLD_TOKEN)
    print(f"[数据源] 东财掘金SDK已初始化 (Token: {DIGGOLD_TOKEN[:16]}...)")
except ImportError:
    print("[数据源] 东财掘金SDK未安装")
except Exception as e:
    print(f"[数据源] 东财掘金SDK初始化失败: {e}")


class DataResilient:
    """数据获取类 - 掘金SDK优先"""

    @staticmethod
    def fetch_stock_data(symbol: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
        """
        获取股票历史数据

        优先使用掘金SDK，失败时根据配置决定是否使用备用数据源
        """
        # 1. 尝试从缓存加载
        if use_cache:
            cached_data = CacheManager.load_stock_cache(symbol, start_date, end_date)
            if cached_data is not None:
                return cached_data

        # 2. 从数据源获取
        df = DataResilient._fetch_with_multi_source(symbol, start_date, end_date)

        # 3. 保存到缓存
        if use_cache and df is not None and not df.empty:
            CacheManager.save_stock_cache(symbol, start_date, end_date, df)

        return df

    @staticmethod
    def _fetch_with_multi_source(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """多数据源容错机制 - 根据配置文件决定使用哪些数据源"""

        # 获取启用的数据源（按优先级排序）
        enabled_sources = get_enabled_sources()

        if not enabled_sources:
            raise ValueError("没有启用的数据源，请检查 config_data_source.py 配置")

        # 构建数据源函数映射
        source_functions = {
            'diggold': lambda s=symbol, sd=start_date, ed=end_date: DataResilient._fetch_from_diggold(s, sd, ed),
            'akshare_primary': lambda s=start_date, e=end_date: ak.stock_zh_a_hist(
                symbol=symbol, period="daily", start_date=s, end_date=e
            ),
            'akshare_daily_qfq': lambda s=start_date, e=end_date: ak.stock_zh_a_daily(
                symbol=f"sh{symbol}", start_date=s, end_date=e, adjust="qfq"
            ),
            'akshare_daily_hfq': lambda s=start_date, e=end_date: ak.stock_zh_a_daily(
                symbol=f"sh{symbol}", start_date=s, end_date=e, adjust="hfq"
            ),
            'baostock': lambda s=symbol, sd=start_date, ed=end_date: DataResilient._fetch_from_baostock(s, sd, ed),
            'efinance': lambda s=symbol, sd=start_date, ed=end_date: DataResilient._fetch_from_efinance(s, sd, ed),
        }

        max_retries = DATA_SOURCE_CONFIG.get('max_retries', 3)
        retry_delay = DATA_SOURCE_CONFIG.get('retry_delay', (0.5, 1.5))
        auto_fallback = DATA_SOURCE_CONFIG.get('auto_fallback', True)

        # 按优先级尝试每个数据源
        for source_id, source_config in enabled_sources:
            source_name = source_config['name']

            # 检查数据源是否可用
            if source_id == 'diggold' and not DIGGOLD_AVAILABLE:
                continue
            if source_id.startswith('akshare') and not source_config['enabled']:
                continue
            if source_id == 'baostock':
                try:
                    import baostock as bs
                except ImportError:
                    continue
            if source_id == 'efinance':
                try:
                    import efinance as ef
                except ImportError:
                    continue

            # 尝试获取数据
            for attempt in range(max_retries + 1):
                try:
                    print(f"尝试使用 {source_name} 获取 {symbol} 数据...")
                    df = source_functions[source_id]()

                    if df is None or df.empty:
                        raise ValueError(f"获取数据为空: {symbol}")

                    # 标准化数据格式
                    df = DataResilient._standardize_dataframe(df)
                    print(f"成功使用 {source_name} 获取 {len(df)} 条数据")

                    return df

                except Exception as e:
                    if attempt < max_retries:
                        delay = random.uniform(retry_delay[0], retry_delay[1])
                        print(f"  {source_name} 失败，重试中... ({str(e)[:40]})")
                        time.sleep(delay)
                    else:
                        print(f"  {source_name} 失败")
                        # 如果不启用自动降级，直接抛出异常
                        if not auto_fallback:
                            raise
                        break

        raise ValueError(f"所有数据源均失败: {symbol}")

    @staticmethod
    def _fetch_from_diggold(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """使用掘金SDK获取数据（默认且最稳定）"""
        if not DIGGOLD_AVAILABLE:
            raise ValueError("掘金SDK未安装或未初始化")

        # 转换日期格式: YYYYMMDD -> YYYY-MM-DD
        start_date_diggold = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_date_diggold = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        # 转换股票代码: 600519 -> SHSE.600519, 000001 -> SZSE.000001
        if symbol.startswith('6') or symbol.startswith('5'):
            diggold_symbol = f"SHSE.{symbol}"
        else:
            diggold_symbol = f"SZSE.{symbol}"

        # 获取数据
        data = history(
            symbol=diggold_symbol,
            frequency='1d',
            start_time=start_date_diggold,
            end_time=end_date_diggold,
            adjust=1,  # 前复权
            df=True
        )

        if data.empty:
            raise ValueError(f"掘金SDK返回空数据: {symbol}")

        # 处理日期列 - 掘金返回 eob/bob 列
        if 'eob' in data.columns:
            data['date'] = pd.to_datetime(data['eob'])
            data = data.drop(columns=['eob'])
        elif 'bob' in data.columns:
            data['date'] = pd.to_datetime(data['bob'])
            data = data.drop(columns=['bob'])

        # 设置日期索引
        if 'date' in data.columns:
            data.set_index('date', inplace=True)

        # 只保留需要的列
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        available_cols = [col for col in required_cols if col in data.columns]

        return data[available_cols]

    @staticmethod
    def _fetch_from_baostock(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """使用 Baostock 获取数据（备用数据源）"""
        import baostock as bs

        # 转换日期格式
        start_date_baostock = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_date_baostock = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        # 判断市场
        market = 'sh' if symbol.startswith('6') else 'sz'

        bs.login()
        rs = bs.query_history_k_data_plus(
            f"{market}.{symbol}",
            "date,open,high,low,close,volume,amount",
            start_date=start_date_baostock,
            end_date=end_date_baostock,
            frequency="d",
            adjustflag="2"  # 前复权
        )

        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())

        bs.logout()

        if not data_list:
            raise ValueError(f"Baostock 返回空数据: {symbol}")

        df = pd.DataFrame(data_list)
        df.columns = rs.fields

        # 转换数据类型
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    @staticmethod
    def _fetch_from_efinance(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """使用 Efinance 获取数据"""
        import efinance as ef

        # efinance 使用不同的日期格式
        start_date_ef = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_date_ef = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        df = ef.stock.get_quote_history(
            stock_codes=symbol,
            beg=start_date_ef,
            end=end_date_ef,
            klt=1  # 日K线
        )

        if df is None or df.empty:
            raise ValueError(f"Efinance 返回空数据: {symbol}")

        # efinance 返回的列名需要映射
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        }

        df.rename(columns=column_mapping, inplace=True)
        df['date'] = pd.to_datetime(df['date'])

        return df

    @staticmethod
    def _standardize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """标准化数据框格式"""
        # 检查并重命名列（支持中英文列名）
        rename_map = {}
        for col in df.columns:
            if col in ['日期', 'date', 'eob', 'bob']:
                rename_map[col] = 'date'
            elif col in ['开盘', 'open']:
                rename_map[col] = 'open'
            elif col in ['收盘', 'close']:
                rename_map[col] = 'close'
            elif col in ['最高', 'high']:
                rename_map[col] = 'high'
            elif col in ['最低', 'low']:
                rename_map[col] = 'low'
            elif col in ['成交量', 'volume']:
                rename_map[col] = 'volume'

        # 避免重复的列名映射
        seen_targets = set()
        final_rename_map = {}
        for src, tgt in rename_map.items():
            if tgt not in seen_targets or src == 'date':
                final_rename_map[src] = tgt
                seen_targets.add(tgt)

        if final_rename_map:
            df.rename(columns=final_rename_map, inplace=True)

        # 确保日期为索引
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

        # 确保数值列为正确类型
        for col in ['open', 'close', 'high', 'low', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    @staticmethod
    def fetch_macro_data(data_type: str, use_cache: bool = True) -> pd.DataFrame:
        """获取宏观数据（使用AkShare）"""
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
        """宏观数据获取重试机制"""
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
        """获取股票信息"""
        cache_key = 'stock_info'

        if use_cache:
            cached_data = CacheManager.load_macro_cache(cache_key)
            if cached_data is not None:
                return cached_data

        try:
            # 优先使用掘金SDK
            if DIGGOLD_AVAILABLE:
                df = get_instruments(sec_types=1, df=True)
                if not df.empty and 'symbol' in df.columns and 'sec_name' in df.columns:
                    # 转换为标准格式
                    result = pd.DataFrame({
                        'code': df['symbol'].apply(lambda x: x.split('.')[-1]),
                        'name': df['sec_name']
                    })
                    if use_cache:
                        CacheManager.save_macro_cache(cache_key, result)
                    return result

            # 降级使用AkShare
            df = ak.stock_info_a_code_name()

            if use_cache and df is not None and not df.empty:
                CacheManager.save_macro_cache(cache_key, df)

            return df
        except Exception as e:
            print(f"获取股票信息失败: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def get_hs300_symbols(use_cache: bool = True) -> list:
        """获取沪深300成分股"""
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
