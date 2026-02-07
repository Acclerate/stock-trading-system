"""
测试备选数据源
当东方财富网不可用时，尝试其他数据源
"""
import pandas as pd
from datetime import datetime, timedelta
import sys
import io

# 修复 Windows 中文乱码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print("=" * 70)
print("测试备选数据源")
print("=" * 70)

symbol = "600519"  # 贵州茅台
end_date = datetime.now().strftime("%Y%m%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

print(f"\n测试股票: {symbol}")
print(f"时间范围: {start_date} - {end_date}\n")

# ========== 1. Baostock 测试 ==========
print("【1】Baostock（证券宝）")
try:
    import baostock as bs

    bs.login()
    rs = bs.query_history_k_data_plus(
        f"sh.{symbol}",
        "date,open,high,low,close,volume,amount",
        start_date='2024-01-01',
        end_date='2024-12-31',
        frequency="d",
        adjustflag="2"  # 前复权
    )

    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())

    df_bs = pd.DataFrame(data_list, columns=rs.fields)
    bs.logout()

    if not df_bs.empty:
        print(f"    [OK] 成功 - 获取 {len(df_bs)} 条数据")
        print(f"    数据列: {list(df_bs.columns)}")
    else:
        print(f"    [FAIL] 数据为空")
except ImportError:
    print(f"    [WARN] 未安装 baostock")
    print(f"    安装命令: pip install baostock")
except Exception as e:
    print(f"    [FAIL] 失败 - {str(e)[:50]}")

# ========== 2. Efinance 测试 ==========
print("\n【2】Efinance（东方财富备用）")
try:
    import efinance as ef

    df_ef = ef.stock.get_quote_history(
        stock_codes=symbol,
        beg='20240101',
        end='20241231',
        klt=1  # 日K线
    )

    if df_ef is not None and not df_ef.empty:
        print(f"    [OK] 成功 - 获取 {len(df_ef)} 条数据")
        print(f"    数据列: {list(df_ef.columns)}")
    else:
        print(f"    [FAIL] 数据为空")
except ImportError:
    print(f"    [WARN] 未安装 efinance")
    print(f"    安装命令: pip install efinance")
except Exception as e:
    print(f"    [FAIL] 失败 - {str(e)[:50]}")

# ========== 3. Tushare 测试（需要token）==========
print("\n【3】Tushare（需要token）")
try:
    import tushare as ts

    # 检查是否已设置token
    try:
        pro = ts.pro_api()
        df_ts = pro.daily(
            ts_code=f'{symbol}.SH',
            start_date='20240101',
            end_date='20241231'
        )

        if df_ts is not None and not df_ts.empty:
            print(f"    [OK] 成功 - 获取 {len(df_ts)} 条数据")
            print(f"    数据列: {list(df_ts.columns)}")
        else:
            print(f"    [FAIL] 数据为空或未设置token")
    except Exception as token_error:
        print(f"    [WARN] 需要设置token: {str(token_error)[:50]}")
        print(f"    获取token: https://tushare.pro/register")

except ImportError:
    print(f"    [WARN] 未安装 tushare")
    print(f"    安装命令: pip install tushare")
except Exception as e:
    print(f"    [FAIL] 失败 - {str(e)[:50]}")

# ========== 4. AkShare 不同参数测试 ==========
print("\n【4】AkShare - 不同复权参数")
for adjust_type, name in [("", "不复权"), ("qfq", "前复权"), ("hfq", "后复权")]:
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust_type
        )
        print(f"    {name}: [OK] 成功 - {len(df)} 条")
    except Exception as e:
        print(f"    {name}: [FAIL] 失败")

print("\n" + "=" * 70)
print("总结")
print("=" * 70)
print("推荐优先级:")
print("1. Baostock - 免费，稳定，无需注册")
print("2. Efinance - 轻量级，速度快")
print("3. Tushare - 数据质量高，但需要token")
print("=" * 70)
