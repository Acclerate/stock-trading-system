# -*- coding: utf-8 -*-
"""
测试掘金SDK实际返回的数据量
"""
import os
from gm.api import history_n
from data.diggold_data import DiggoldDataSource
import pandas as pd
from datetime import datetime, timedelta

def test_diggold_data_range():
    """测试掘金SDK实际能返回多少天的数据"""

    print("=" * 70)
    print("掘金SDK数据范围测试")
    print("=" * 70)

    # 先初始化掘金SDK
    print("\n正在初始化掘金SDK...")
    try:
        DiggoldDataSource.init()
        print("掘金SDK初始化成功\n")
    except Exception as e:
        print(f"掘金SDK初始化失败: {e}\n")
        return

    # 测试股票列表
    test_stocks = [
        'SHSE.600004',  # 白云机场
        'SHSE.600036',  # 招商银行
        'SZSE.000001',  # 平安银行
        'SZSE.000002',  # 万科A
    ]

    for symbol in test_stocks:
        print(f"\n{'='*70}")
        print(f"测试股票: {symbol}")
        print(f"{'='*70}")

        # 测试1: 请求不同数量的数据
        print(f"\n【测试1】请求数量对返回数据的影响")
        for request_count in [100, 200, 300, 500, 1000]:
            try:
                df = history_n(
                    symbol=symbol,
                    frequency='1d',
                    count=request_count,
                    end_time='2026-02-24',
                    adjust=1,
                    df=True
                )

                if df is not None and not df.empty:
                    actual_count = len(df)
                    print(f"  请求 {request_count:4d} 天 → 实际返回 {actual_count:4d} 天")
                else:
                    print(f"  请求 {request_count:4d} 天 → 返回空数据")
            except Exception as e:
                print(f"  请求 {request_count:4d} 天 → 错误: {e}")

        # 测试2: 不同的end_date
        print(f"\n【测试2】end_date对返回数据的影响 (请求500天)")
        print(f"  {'end_date':<15} {'实际数量':<10} {'数据范围(起)'}  {'数据范围(止)'}")
        print(f"  {'-'*15:<15} {'-'*10:<10} {'-'*22} {'-'*22}")

        test_dates = [
            '2026-02-24',  # 最新
            '2026-01-01',  # 1个月前
            '2025-12-31',  # 约1年前
            '2025-06-01',  # 约8个月前
        ]

        for end_date in test_dates:
            try:
                df = history_n(
                    symbol=symbol,
                    frequency='1d',
                    count=500,
                    end_time=end_date,
                    adjust=1,
                    df=True
                )

                if df is not None and not df.empty:
                    actual_count = len(df)
                    # 检查索引类型
                    if hasattr(df.index, 'min'):
                        start_date = str(df.index.min())
                        end_actual = str(df.index.max())
                    else:
                        start_date = str(df.index[0])
                        end_actual = str(df.index[-1])

                    # 获取第一行和最后一行的实际日期数据
                    if 'eob' in df.columns:
                        df['date'] = pd.to_datetime(df['eob'])
                    elif 'bob' in df.columns:
                        df['date'] = pd.to_datetime(df['bob'])
                    else:
                        df['date'] = pd.to_datetime(df.index)

                    first_date = str(df['date'].iloc[0])[:10]
                    last_date = str(df['date'].iloc[-1])[:10]

                    print(f"  {end_date:<15} {actual_count:<10} {first_date}  {last_date}")
                else:
                    print(f"  {end_date:<15} {'空数据':<10}")
            except Exception as e:
                print(f"  {end_date:<15} {f'错误: {e}'}")

        # 测试3: 找出实际能返回的最大天数
        print(f"\n【测试3】探测最大可返回天数")
        max_found = 0
        for request_count in [100, 150, 180, 200, 220, 230, 240, 250, 260, 270, 280, 290, 300]:
            try:
                df = history_n(
                    symbol=symbol,
                    frequency='1d',
                    count=request_count,
                    end_time='2026-02-24',
                    adjust=1,
                    df=True
                )

                if df is not None and not df.empty:
                    actual_count = len(df)
                    if actual_count > max_found:
                        max_found = actual_count
                    if actual_count >= request_count:
                        print(f"  请求 {request_count:4d} 天 → 实际 {actual_count:4d} 天 (足够)")
                        break  # 找到了足够的量
                    else:
                        print(f"  请求 {request_count:4d} 天 → 实际 {actual_count:4d} 天 (不足)")
                else:
                    print(f"  请求 {request_count:4d} 天 → 空数据")
                    break
            except Exception as e:
                print(f"  请求 {request_count:4d} 天 → 错误: {e}")
                break

        print(f"\n  结论: {symbol} 最大可返回约 {max_found} 天数据")


def test_multiple_dates():
    """测试多个end_date，看数据量的变化"""
    print("\n" + "="*70)
    print("测试不同end_date的数据量")
    print("="*70)

    # 先初始化掘金SDK
    print("\n正在初始化掘金SDK...")
    try:
        DiggoldDataSource.init()
        print("掘金SDK初始化成功\n")
    except Exception as e:
        print(f"掘金SDK初始化失败: {e}\n")
        return

    symbol = 'SHSE.600004'
    end_dates = [
        '2024-01-01',
        '2024-06-01',
        '2024-12-31',
        '2025-06-01',
        '2025-12-31',
        '2026-01-01',
        '2026-02-24',
    ]

    print(f"股票: {symbol}")
    print(f"{'end_date':<15} {'请求':<10} {'实际':<10} {'数据起止'}")
    print("-" * 70)

    for end_date in end_dates:
        try:
            df = history_n(
                symbol=symbol,
                frequency='1d',
                count=500,
                end_time=end_date,
                adjust=1,
                df=True
            )

            if df is not None and not df.empty:
                actual_count = len(df)

                # 获取实际的日期范围
                if 'eob' in df.columns:
                    df['date'] = pd.to_datetime(df['eob'])
                elif 'bob' in df.columns:
                    df['date'] = pd.to_datetime(df['bob'])
                else:
                    df['date'] = pd.to_datetime(df.index)

                first_date = str(df['date'].iloc[0])[:10]
                last_date = str(df['date'].iloc[-1])[:10]

                print(f"{end_date:<15} {500:<10} {actual_count:<10} {first_date} → {last_date}")
            else:
                print(f"{end_date:<15} {500:<10} {'空数据':<10}")
        except Exception as e:
            print(f"{end_date:<15} {500:<10} {f'错误: {e}'}")


if __name__ == '__main__':
    test_diggold_data_range()
    test_multiple_dates()
