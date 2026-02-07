"""
东财掘金SDK数据获取模块
使用掘金量化终端SDK获取稳定的股票交易数据
"""
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.config_data_source import DATA_SOURCE_CONFIG

# 掘金SDK
from gm.api import (
    set_token,
    history,
    history_n,
    get_instruments,
    get_trading_dates,
    get_symbol_infos
)


class DiggoldDataSource:
    """东财掘金SDK数据源"""

    # Token从配置文件读取
    TOKEN = DATA_SOURCE_CONFIG['sources']['diggold']['token']

    # 频率常量
    FREQ_TICK = 'tick'       # 逐笔
    FREQ_60S = '60s'         # 1分钟
    FREQ_300S = '300s'       # 5分钟
    FREQ_900S = '900s'       # 15分钟
    FREQ_1800S = '1800s'     # 30分钟
    FREQ_1D = '1d'           # 日线
    FREQ_1W = '1w'           # 周线
    FREQ_1M = '1m'           # 月线

    # 复权类型
    ADJUST_NONE = 0      # 不复权
    ADJUST_PREV = 1      # 前复权
    ADJUST_POST = 2      # 后复权

    @staticmethod
    def init():
        """初始化SDK"""
        try:
            token = DATA_SOURCE_CONFIG['sources']['diggold']['token']
            set_token(token)
            print(f"掘金SDK初始化成功 (Token: {token[:16]}...)")
            return True
        except Exception as e:
            print(f"掘金SDK初始化失败: {e}")
            return False

    @staticmethod
    def get_stock_history(symbol, start_date, end_date, frequency='1d', adjust=ADJUST_PREV, df=True):
        """
        获取股票历史数据

        参数:
            symbol: 股票代码，如 'SHSE.600519' 或 'SZSE.000001'
            start_date: 开始日期 '2024-01-01'
            end_date: 结束日期 '2024-12-31'
            frequency: 数据频率 'tick', '60s', '300s', '900s', '1800s', '1d', '1w', '1m'
            adjust: 复权类型 0=不复权, 1=前复权, 2=后复权
            df: 是否返回DataFrame

        返回:
            DataFrame或List
        """
        try:
            data = history(
                symbol=symbol,
                frequency=frequency,
                start_time=start_date,
                end_time=end_date,
                adjust=adjust,
                df=df
            )

            if df and not data.empty:
                # 处理日期列 - eob/bob 可能存在
                date_col = None
                if 'eob' in data.columns:
                    date_col = 'eob'
                elif 'bob' in data.columns:
                    date_col = 'bob'

                # 如果存在日期列，先创建一个副本作为date
                if date_col:
                    data['date'] = pd.to_datetime(data[date_col])
                    data = data.drop(columns=[date_col])

                # 设置索引
                if 'date' in data.columns:
                    data.set_index('date', inplace=True)

            return data

        except Exception as e:
            print(f"获取历史数据失败: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame() if df else []

    @staticmethod
    def get_stock_history_n(symbol, count=100, end_date=None, frequency='1d', adjust=ADJUST_PREV, df=True):
        """
        获取最近N条股票数据

        参数:
            symbol: 股票代码
            count: 获取条数
            end_date: 结束日期，默认为当前日期
            frequency: 数据频率
            adjust: 复权类型
            df: 是否返回DataFrame

        返回:
            DataFrame或List
        """
        try:
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')

            data = history_n(
                symbol=symbol,
                frequency=frequency,
                count=count,
                end_time=end_date,
                adjust=adjust,
                df=df
            )

            if df and not data.empty:
                # 处理日期列
                date_col = None
                if 'eob' in data.columns:
                    date_col = 'eob'
                elif 'bob' in data.columns:
                    date_col = 'bob'

                if date_col:
                    data['date'] = pd.to_datetime(data[date_col])
                    data = data.drop(columns=[date_col])

                if 'date' in data.columns:
                    data.set_index('date', inplace=True)

            return data

        except Exception as e:
            print(f"获取最近N条数据失败: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame() if df else []

    @staticmethod
    def get_stock_list(exchanges=None, sec_types=1, df=True):
        """
        获取股票列表

        参数:
            exchanges: 交易所 'SHSE', 'SZSE'
            sec_types: 证券类型 1=股票
            df: 是否返回DataFrame

        返回:
            股票列表DataFrame
        """
        try:
            data = get_instruments(
                exchanges=exchanges,
                sec_types=sec_types,
                df=df
            )

            if df and not data.empty:
                # 提取关键列
                result_cols = ['symbol', 'sec_name', 'exchange', 'list_date']
                available_cols = [col for col in result_cols if col in data.columns]
                return data[available_cols]

            return data

        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return pd.DataFrame() if df else []

    @staticmethod
    def convert_symbol_to_diggold(symbol):
        """
        转换股票代码为掘金格式

        参数:
            symbol: 原始代码 '600519' 或 '600519.SH'

        返回:
            'SHSE.600519' 或 'SZSE.000001'
        """
        # 清理代码
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.sh', '').replace('.sz', '')

        # 判断市场
        if code.startswith('6') or code.startswith('5'):
            return f'SHSE.{code}'
        elif code.startswith(('0', '3')):
            return f'SZSE.{code}'
        else:
            # 默认上海
            return f'SHSE.{code}'

    @staticmethod
    def convert_symbol_from_diggold(symbol):
        """
        从掘金格式转换回标准格式

        参数:
            symbol: 'SHSE.600519'

        返回:
            '600519.SH'
        """
        if '.' in symbol:
            exchange, code = symbol.split('.')
            if exchange == 'SHSE':
                return f'{code}.SH'
            elif exchange == 'SZSE':
                return f'{code}.SZ'
        return symbol


# ========== 测试代码 ==========
if __name__ == "__main__":
    print("=" * 70)
    print("东财掘金SDK数据获取测试")
    print("=" * 70)

    # 初始化
    if not DiggoldDataSource.init():
        print("初始化失败，退出")
        exit(1)

    # 测试获取历史数据
    print("\n【1】测试获取贵州茅台历史数据")
    diggold_symbol = DiggoldDataSource.convert_symbol_to_diggold("600519")
    print(f"掘金代码: {diggold_symbol}")

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    df = DiggoldDataSource.get_stock_history(
        symbol=diggold_symbol,
        start_date=start_date,
        end_date=end_date,
        frequency='1d',
        adjust=DiggoldDataSource.ADJUST_PREV
    )

    if not df.empty:
        print(f"成功获取 {len(df)} 条数据")
        print(f"\n最近5天数据:")
        print(df.tail())
        print(f"\n数据列: {list(df.columns)}")
    else:
        print("获取数据失败")

    # 测试获取最近N条数据
    print("\n【2】测试获取最近10条数据")
    df_n = DiggoldDataSource.get_stock_history_n(
        symbol=diggold_symbol,
        count=10,
        frequency='1d'
    )

    if not df_n.empty:
        print(f"成功获取 {len(df_n)} 条数据")
        print(df_n.tail(3))
    else:
        print("获取数据失败")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
