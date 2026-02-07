import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

print("=" * 70)
print("akshare 可用的A股历史数据获取方式")
print("=" * 70)

# 测试参数
symbol = "600519"  # 贵州茅台
end_date = datetime.now().strftime("%Y%m%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

print(f"\n测试股票: {symbol}")
print(f"时间范围: {start_date} - {end_date}\n")

sources = []

# 1. 当前使用的方式（东方财富）
print("【1】stock_zh_a_hist - 东方财富网（当前使用）")
try:
    df1 = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)
    print(f"    ✓ 成功 - 获取 {len(df1)} 条数据")
    print(f"    域名: push2his.eastmoney.com")
    sources.append(("stock_zh_a_hist", df1))
except Exception as e:
    print(f"    ✗ 失败 - {str(e)[:50]}")

# 2. 东方财富备用接口
print("\n【2】stock_zh_a_daily - 东方财富网备用")
try:
    df2 = ak.stock_zh_a_daily(symbol=f"sh{symbol}", start_date=start_date, end_date=end_date, adjust="qfq")
    print(f"    ✓ 成功 - 获取 {len(df2)} 条数据")
    sources.append(("stock_zh_a_daily", df2))
except Exception as e:
    print(f"    ✗ 失败 - {str(e)[:50]}")

# 3. 新浪财经
print("\n【3】stock_zh_a_spot - 新浪财经（实时）")
try:
    df3 = ak.stock_zh_a_spot()
    print(f"    ✓ 成功 - 获取 {len(df3)} 条数据（实时行情）")
    if symbol in df3['代码'].values:
        row = df3[df3['代码'] == symbol].iloc[0]
        print(f"       最新价: {row['最新价']}")
except Exception as e:
    print(f"    ✗ 失败 - {str(e)[:50]}")

# 4. 腾讯财经
print("\n【4】stock_zh_a_spot - 腾讯财经（部分）")
try:
    df4 = ak.stock_zh_a_spot()
    # 注意：这个函数的实际数据源取决于 akshare 版本
    print(f"    ✓ 可用 - 获取 {len(df4)} 条数据")
except Exception as e:
    print(f"    ✗ 失败 - {str(e)[:50]}")

# 5. 历史数据-其他接口
print("\n【5】其他历史数据接口")

# 5a. stock_zh_a_hist 参数变体
print("  5a. stock_zh_a_hist (调整复权类型)")
try:
    df5a = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    print(f"    ✓ 成功 - 前复权数据 - {len(df5a)} 条")
except Exception as e:
    print(f"    ✗ 失败 - {str(e)[:50]}")

# 5b. stock_zh_a_hist 参数变体
print("  5b. stock_zh_a_hist (后复权)")
try:
    df5b = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="hfq")
    print(f"    ✓ 成功 - 后复权数据 - {len(df5b)} 条")
except Exception as e:
    print(f"    ✗ 失败 - {str(e)[:50]}")

print("\n" + "=" * 70)
print("数据源总结")
print("=" * 70)
print("1. 主要数据源: 东方财富网 (eastmoney.com)")
print("2. 备用数据源: 新浪财经、腾讯财经")
print("3. 接口差异: 不同的函数可能使用不同的数据源")
print("\n建议:")
print("- 当前使用: stock_zh_a_hist (最稳定)")
print("- 备用方案: stock_zh_a_daily (同数据源，不同接口)")
print("- 实时行情: stock_zh_a_spot (多源聚合)")
print("=" * 70)
