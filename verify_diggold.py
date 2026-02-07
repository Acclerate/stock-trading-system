"""验证掘金SDK初始化状态"""
import sys
import io

# 修复 Windows 中文乱码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from data_resilient import DIGGOLD_AVAILABLE, DIGGOLD_TOKEN
from config_data_source import get_enabled_sources, DATA_SOURCE_CONFIG

print("=" * 60)
print("数据源配置验证")
print("=" * 60)

print(f"\n[1] 掘金SDK状态:")
print(f"    可用: {DIGGOLD_AVAILABLE}")
if DIGGOLD_AVAILABLE:
    print(f"    Token: {DIGGOLD_TOKEN[:16]}...")

print(f"\n[2] 默认数据源:")
default = DATA_SOURCE_CONFIG['default']
print(f"    {default}: {DATA_SOURCE_CONFIG['sources'][default]['name']}")

print(f"\n[3] 启用的数据源（按优先级）:")
enabled = get_enabled_sources()
for source_id, config in enabled:
    status = "✓" if config['enabled'] else "✗"
    print(f"    {status} {config['name']} (优先级: {config['priority']})")

print(f"\n[4] 配置参数:")
print(f"    自动降级: {DATA_SOURCE_CONFIG['auto_fallback']}")
print(f"    最大重试: {DATA_SOURCE_CONFIG['max_retries']} 次")
print(f"    重试延迟: {DATA_SOURCE_CONFIG['retry_delay']} 秒")

print("\n" + "=" * 60)
print("配置验证完成")
print("=" * 60)
