# -*- coding: utf-8 -*-
"""
多数据源股票数据获取模块
支持多个备用数据源，当主数据源失败时自动切换
"""
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional, List
import time
import random


class DataSourceBase:
    """数据源基类"""

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据"""
        raise NotImplementedError

    def get_name(self) -> str:
        """获取数据源名称"""
        raise NotImplementedError


class SinaDataSource(DataSourceBase):
    """
    新浪财经数据源
    API: http://finance.sina.com.cn/realstock/company/
    """

    def get_name(self) -> str:
        return "新浪财经"

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从新浪财经获取股票数据
        symbol格式: 000001.SZ 或 600000.SH
        """
        try:
            # 转换symbol格式: 000001.SZ -> sz000001
            symbol_clean = self._convert_symbol(symbol)

            # 新浪财经历史数据API
            url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"

            # 计算日期范围 - 新浪API需要更多数据来筛选
            start = datetime.strptime(start_date, "%Y%m%d")
            end = datetime.strptime(end_date, "%Y%m%d")

            # 请求更长的时间范围以确保获取到目标数据
            request_start = start - timedelta(days=365)
            request_end = end + timedelta(days=30)

            params = {
                'symbol': symbol_clean,
                'scale': '240',  # 日线数据
                'ma': 'no',
                'datalen': '2000'  # 获取更多数据点
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://finance.sina.com.cn',
                'Accept': '*/*'
            }

            response = requests.get(url, params=params, headers=headers, timeout=20)

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            # 解析JSON响应
            import json
            data = json.loads(response.text)

            if not data:
                raise Exception("返回数据为空")

            # 转换为DataFrame
            df = pd.DataFrame(data)

            # 重命名列
            df.rename(columns={
                'day': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }, inplace=True)

            # 类型转换
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 筛选日期范围
            df = df[(df['date'] >= start) & (df['date'] <= end)]

            if df.empty:
                raise Exception("筛选后数据为空")

            # 去除空值
            df = df.dropna()

            df.set_index('date', inplace=True)

            # 确保列顺序
            df = df[['open', 'close', 'high', 'low', 'volume']]

            return df

        except Exception as e:
            raise Exception(f"新浪数据源获取失败: {str(e)}")

    def _convert_symbol(self, symbol: str) -> str:
        """转换股票代码格式: 000001.SZ -> sz000001"""
        if '.' in symbol:
            code, exchange = symbol.split('.')
            if exchange == 'SH':
                return f'sh{code}'
            elif exchange == 'SZ':
                return f'sz{code}'
        return symbol


class EfinanceDataSource(DataSourceBase):
    """
    Efinance数据源 (东方财富)
    需要安装: pip install efinance
    """

    def get_name(self) -> str:
        return "Efinance"

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        使用efinance获取股票数据
        """
        try:
            import efinance as ef

            # 转换代码格式
            code = symbol.split('.')[0]

            # 获取历史数据
            df = ef.stock.get_quote_history(
                stock_codes=code,
                beg=start_date,
                end=end_date
            )

            if df is None or df.empty:
                raise Exception("efinance返回数据为空")

            # 重命名列
            column_mapping = {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume'
            }

            # 检查列是否存在
            available_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}

            if not available_mapping:
                # 尝试英文列名
                column_mapping_en = {
                    'trade_date': 'date',
                    'open': 'open',
                    'close': 'close',
                    'high': 'high',
                    'low': 'low',
                    'volume': 'volume'
                }
                available_mapping = {k: v for k, v in column_mapping_en.items() if k in df.columns}

            df.rename(columns=available_mapping, inplace=True)

            # 确保日期列存在
            if 'date' not in df.columns:
                raise Exception("无法识别日期列")

            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # 确保数值列正确
            for col in ['open', 'close', 'high', 'low', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 确保列顺序
            df = df[['open', 'close', 'high', 'low', 'volume']]

            return df

        except ImportError:
            raise Exception("efinance库未安装，请使用: pip install efinance")
        except Exception as e:
            raise Exception(f"Efinance数据源获取失败: {str(e)}")


class BaostockDataSource(DataSourceBase):
    """
    Baostock数据源
    完全免费，专为A股设计
    """

    def get_name(self) -> str:
        return "Baostock"

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """使用baostock获取股票数据"""
        try:
            import baostock as bs

            # 登录系统
            lg = bs.login()
            if lg.error_code != '0':
                raise Exception(f"Baostock登录失败: {lg.error_msg}")

            # 转换代码格式: 000001.SZ -> sz.000001
            code = symbol.split('.')[0]
            if symbol.endswith('.SH'):
                stock_code = f"sh.{code}"
            else:
                stock_code = f"sz.{code}"

            # 转换日期格式
            start = start_date.replace('-', '')[:8]
            end = end_date.replace('-', '')[:8]

            # 获取历史数据
            rs = bs.query_history_k_data_plus(
                stock_code,
                start_date=start,
                end_date=end,
                frequency="d",  # 日线
                adjustflag="2",  # 2: 不复权
                fields="date,open,high,low,close,volume,amount"
            )

            # 登出系统
            bs.logout()

            if rs.error_code != '0':
                raise Exception(f"Baostock查询失败: {rs.error_msg}")

            # 转换为DataFrame
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                raise Exception("Baostock返回数据为空")

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 重命名列
            df.rename(columns={
                'date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'amount': 'amount'
            }, inplace=True)

            # 类型转换
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 删除空值
            df = df.dropna()

            if df.empty:
                raise Exception("处理后数据为空")

            df.set_index('date', inplace=True)

            # 确保列顺序
            df = df[['open', 'close', 'high', 'low', 'volume']]

            return df

        except ImportError:
            raise Exception("baostock库未安装，请使用: pip install baostock")
        except Exception as e:
            raise Exception(f"Baostock数据源获取失败: {str(e)}")


class AkshareBackupSource(DataSourceBase):
    """
    Akshare备用数据源
    原始东财接口可能被屏蔽，作为备用
    """

    def get_name(self) -> str:
        return "Akshare备用"

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        使用akshare获取股票数据（尝试多种方法）
        """
        try:
            import akshare as ak

            code = symbol.split('.')[0]

            # 尝试不同的akshare接口
            methods = [
                # 方法1: stock_zh_a_hist
                lambda: ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=""
                ),
                # 方法2: stock_zh_a_daily
                lambda: ak.stock_zh_a_daily(
                    symbol=f"sz{code}" if symbol.endswith('.SZ') else f"sh{code}",
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', ''),
                    adjust="qfq"
                )
            ]

            for i, method in enumerate(methods):
                try:
                    df = method()

                    if df is not None and not df.empty:
                        # 检查是否已经有date作为索引
                        if isinstance(df.index, pd.DatetimeIndex):
                            # 索引已经是日期，直接使用
                            df.index.name = 'date'
                        else:
                            # 重命名列
                            rename_map = {
                                '日期': 'date',
                                '开盘': 'open',
                                '收盘': 'close',
                                '最高': 'high',
                                '最低': 'low',
                                '成交量': 'volume',
                            }

                            # 只重命名存在的列
                            for old_name, new_name in rename_map.items():
                                if old_name in df.columns:
                                    df.rename(columns={old_name: new_name}, inplace=True)

                            # 处理日期列
                            if 'date' in df.columns:
                                df['date'] = pd.to_datetime(df['date'])
                                df.set_index('date', inplace=True)

                        # 确保数值列正确
                        for col in ['open', 'close', 'high', 'low', 'volume']:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce')

                        # 确保列顺序（只选择存在的列）
                        available_cols = [col for col in ['open', 'close', 'high', 'low', 'volume'] if col in df.columns]
                        df = df[available_cols]

                        # 删除空值行
                        df = df.dropna()

                        if df.empty:
                            raise Exception("处理后数据为空")

                        return df
                except Exception as e:
                    if i == len(methods) - 1:
                        raise
                    continue

            raise Exception("所有akshare方法均失败")

        except Exception as e:
            raise Exception(f"Akshare备用数据源获取失败: {str(e)}")


class MultiSourceDataFetcher:
    """
    多数据源获取器
    自动在多个数据源之间切换，提高可用性
    """

    def __init__(self, sources: Optional[List[DataSourceBase]] = None):
        """
        初始化数据源列表
        """
        if sources is None:
            # 默认数据源列表（按优先级排序）
            self.sources = [
                BaostockDataSource(),  # 最稳定的免费源
                SinaDataSource(),
                EfinanceDataSource(),
                AkshareBackupSource(),
            ]
        else:
            self.sources = sources

        self.source_status = {source.get_name(): {'success': 0, 'failure': 0} for source in self.sources}
        self.last_success_source = None

    def fetch_stock_data(self, symbol: str, start_date: str, end_date: str, verbose: bool = True) -> Optional[pd.DataFrame]:
        """
        尝试从所有数据源获取数据，直到成功

        Args:
            symbol: 股票代码 (如 000001.SZ)
            start_date: 开始日期 (格式: 20240101)
            end_date: 结束日期 (格式: 20240131)
            verbose: 是否打印详细日志

        Returns:
            DataFrame or None
        """
        # 如果上次成功的源优先尝试
        sources_to_try = self.sources.copy()

        # 打乱顺序，避免总是访问同一个源
        random.shuffle(sources_to_try)

        for source in sources_to_try:
            try:
                if verbose:
                    print(f"  尝试 {source.get_name()}...")

                df = source.fetch_stock_data(symbol, start_date, end_date)

                if df is not None and not df.empty:
                    self.source_status[source.get_name()]['success'] += 1
                    self.last_success_source = source.get_name()

                    if verbose:
                        print(f"  [OK] {source.get_name()} 成功获取 {len(df)} 条数据")

                    return df

            except Exception as e:
                self.source_status[source.get_name()]['failure'] += 1
                if verbose:
                    print(f"  [FAIL] {source.get_name()} 失败: {str(e)}")
                continue

        if verbose:
            print(f"  [FAIL] 所有数据源均失败")
        return None

    def get_status(self) -> dict:
        """获取各数据源状态统计"""
        return self.source_status

    def print_status(self):
        """打印数据源状态"""
        print("\n数据源状态统计:")
        print("-" * 60)
        for name, status in self.source_status.items():
            total = status['success'] + status['failure']
            if total > 0:
                success_rate = status['success'] / total * 100
            else:
                success_rate = 0
            print(f"{name:12} | 成功: {status['success']:3} | 失败: {status['failure']:3} | 成功率: {success_rate:.1f}%")
        print("-" * 60)


# 便捷函数
def fetch_stock_data_multi_source(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    使用多数据源获取股票数据的便捷函数

    Args:
        symbol: 股票代码 (如 000001.SZ)
        start_date: 开始日期 (格式: 20240101)
        end_date: 结束日期 (格式: 20240131)

    Returns:
        DataFrame or None
    """
    fetcher = MultiSourceDataFetcher()
    return fetcher.fetch_stock_data(symbol, start_date, end_date)


if __name__ == "__main__":
    # 测试代码
    print("测试多数据源获取器...")

    fetcher = MultiSourceDataFetcher()

    # 测试获取平安银行数据
    symbol = "000001.SZ"
    start_date = "20240101"
    end_date = "20240131"

    print(f"\n获取 {symbol} 数据 ({start_date} - {end_date}):")
    df = fetcher.fetch_stock_data(symbol, start_date, end_date)

    if df is not None:
        print(f"\n成功获取数据:")
        print(df.head())
        print(f"\n共 {len(df)} 条记录")
    else:
        print("\n获取失败")

    print("\n" + "=" * 60)
    fetcher.print_status()
