"""测试.env文件中的Token是否可用"""
import sys
import os
from dotenv import load_dotenv

# 设置UTF-8编码输出（Windows兼容）
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 加载.env文件
load_dotenv()

# 读取token
token = os.getenv('DIGGOLD_TOKEN')

print("=" * 60)
print("Token验证测试")
print("=" * 60)

if not token:
    print("[错误] 未找到DIGGOLD_TOKEN环境变量")
    print("   请检查.env文件是否存在且配置正确")
    sys.exit(1)

print(f"[成功] Token已读取: {token[:16]}...")
print(f"   Token长度: {len(token)} 字符")

# 验证token格式（掘金SDK token应该是40字符的十六进制）
if len(token) == 40:
    try:
        int(token, 16)  # 验证是否为有效的十六进制
        print("[成功] Token格式正确（40位十六进制）")
    except ValueError:
        print("[警告] Token格式可能不正确（非十六进制）")
else:
    print(f"[警告] Token长度异常（应为40字符，实际{len(token)}字符）")

# 测试掘金SDK初始化
print("\n测试掘金SDK初始化...")
try:
    from gm.api import set_token
    set_token(token)
    print("[成功] 掘金SDK初始化成功！")

    # 尝试获取股票列表验证token是否真的可用
    print("\n测试获取股票列表...")
    from gm.api import get_instruments
    instruments = get_instruments(exchanges='SHSE', sec_types=1, df=True)
    if instruments is not None and not instruments.empty:
        print(f"[成功] Token可用！成功获取到 {len(instruments)} 只上海股票信息")
        print(f"\n示例股票：")
        print(instruments.head(3))
    else:
        print("[警告] Token可能无效或已过期（返回空数据）")

except ImportError:
    print("[警告] 未安装掘金SDK（gm.api），无法验证Token")
    print("   请运行: pip install gm-python-sdk")
except Exception as e:
    print(f"[错误] Token验证失败: {e}")
    print("   可能的原因：")
    print("   1. Token无效或已过期")
    print("   2. 网络连接问题")
    print("   3. 掘金SDK服务异常")

print("\n" + "=" * 60)
