"""测试akshare数据源是否有最新数据"""
import akshare as ak
from datetime import datetime

print("=== 测试 akshare 数据源 ===")
print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 测试获取平安银行数据
symbol = "000001"
end_date = datetime.now().strftime("%Y%m%d")

print(f"测试股票: {symbol}")
print(f"请求结束日期: {end_date}\n")

try:
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20260201", end_date=end_date)
    if not df.empty:
        latest_date = df['日期'].iloc[-1]
        latest_date_str = latest_date.strftime('%Y-%m-%d') if hasattr(latest_date, 'strftime') else str(latest_date)
        print(f"最新数据日期: {latest_date_str}")
        print(f"总数据行数: {len(df)}")
        print(f"\n最近5个交易日:")
        print(df[['日期', '收盘', '成交量']].tail())
    else:
        print("未获取到数据")
except Exception as e:
    print(f"获取数据失败: {e}")

print("\n=== 提示 ===")
print("如果数据不是最新的，可能是：")
print("1. 周末/节假日休市")
print("2. akshare 数据源更新延迟")
print("3. 网络连接问题")
