"""检查掘金Token是否可用"""
import os
from dotenv import load_dotenv
from datetime import datetime

print("=" * 70)
print("掘金Token状态检查")
print("=" * 70)
print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 1. 检查 .env 文件
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    print(f"✅ .env 文件存在: {env_path}")
    load_dotenv()
else:
    print(f"❌ .env 文件不存在: {env_path}")
    print("💡 提示: 请创建 .env 文件并添加 DIGGOLD_TOKEN")

# 2. 检查环境变量
token = os.getenv('DIGGOLD_TOKEN', '')
print(f"\n{'='*70}")
print("环境变量检查")
print(f"{'='*70}")

if token:
    print(f"✅ DIGGOLD_TOKEN 已设置")
    print(f"   Token前缀: {token[:16]}...")
    print(f"   Token长度: {len(token)} 字符")
else:
    print(f"❌ DIGGOLD_TOKEN 未设置")
    print(f"\n💡 如何获取掘金Token:")
    print(f"   1. 访问: https://www.myquant.cn/")
    print(f"   2. 注册/登录掘金量化平台")
    print(f"   3. 创建策略获取Token")
    print(f"   4. 在 .env 文件中添加: DIGGOLD_TOKEN=你的Token")

# 3. 尝试初始化掘金SDK
print(f"\n{'='*70}")
print("掘金SDK测试")
print(f"{'='*70}")

if not token:
    print("❌ 无法测试: Token未设置")
    exit(1)

try:
    from gm.api import set_token, history, get_instruments

    # 尝试初始化
    set_token(token)
    print("✅ 掘金SDK初始化成功")

    # 测试获取数据
    print(f"\n{'='*70}")
    print("数据获取测试")
    print(f"{'='*70}")

    # 测试获取平安银行最近数据
    test_symbol = "SZSE.000001"  # 平安银行
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now()).replace(day=1).strftime('%Y-%m-%d')  # 本月1号

    print(f"测试股票: 平安银行 (000001)")
    print(f"查询区间: {start_date} ~ {end_date}")

    df = history(
        symbol=test_symbol,
        frequency='1d',
        start_time=start_date,
        end_time=end_date,
        adjust=1,  # 前复权
        df=True
    )

    if not df.empty:
        print(f"✅ 数据获取成功")
        print(f"  获取到 {len(df)} 条数据")
        print(f"  数据列: {list(df.columns)}")

        # 检查是否有日期列
        date_col = None
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower() or 'eob' in col.lower() or 'bob' in col.lower():
                date_col = col
                break

        print(f"\n最近5个交易日:")
        print(df.tail())

        # 获取最新日期
        if date_col:
            latest_date_raw = df[date_col].iloc[-1]
            print(f"\n最新数据:")
            print(f"  日期列: {date_col} = {latest_date_raw}")
            print(f"  收盘: {df['close'].iloc[-1]:.2f}")
            print(f"  成交量: {df['volume'].iloc[-1]:,.0f}")

            # 尝试解析日期
            try:
                if hasattr(latest_date_raw, 'date'):
                    latest_date = latest_date_raw.date()
                elif isinstance(latest_date_raw, str):
                    from datetime import datetime as dt
                    latest_date = dt.strptime(latest_date_raw.split()[0], '%Y-%m-%d').date()
                else:
                    latest_date = latest_date_raw

                today = datetime.now().date()
                delay_days = (today - latest_date).days

                print(f"\n数据延迟检查:")
                print(f"  最新数据日期: {latest_date}")
                print(f"  今天日期: {today}")
                if delay_days == 0:
                    print(f"  ✅ 数据最新 (无延迟)")
                elif delay_days == 1:
                    print(f"  ⚠️ 延迟1天 (正常，今天数据可能未更新)")
                else:
                    print(f"  ⚠️ 延迟{delay_days}天")
            except Exception as e:
                print(f"\n⚠️ 无法解析日期延迟: {e}")
        else:
            print(f"\n最新数据:")
            print(f"  收盘: {df['close'].iloc[-1]:.2f}")
            print(f"  成交量: {df['volume'].iloc[-1]:,.0f}")
            print(f"\n⚠️ 未找到日期列，无法判断数据延迟")

        print(f"\n数据延迟检查:")
        print(f"  最新数据日期: {latest_date}")
        print(f"  今天日期: {today}")
        if delay_days == 0:
            print(f"  ✅ 数据最新 (无延迟)")
        elif delay_days == 1:
            print(f"  ⚠️ 延迟1天 (正常，今天数据可能未更新)")
        else:
            print(f"  ⚠️ 延迟{delay_days}天")
    else:
        print("❌ 数据获取失败 (返回空数据)")

except ImportError:
    print("❌ 掘金SDK未安装")
    print("\n💡 安装方法:")
    print("   pip install gm-python")
except Exception as e:
    print(f"❌ 掘金SDK测试失败: {e}")
    print(f"\n可能原因:")
    print(f"  1. Token无效或已过期")
    print(f"  2. 网络连接问题")
    print(f"  3. 掘金服务暂时不可用")

print(f"\n{'='*70}")
print("检查完成")
print(f"{'='*70}")
