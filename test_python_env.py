"""测试Anaconda Python环境"""
import sys

print("=" * 60)
print("Anaconda Python环境验证")
print("=" * 60)
print(f"\nPython版本: {sys.version}")
print(f"Python路径: {sys.executable}")
print(f"\nAnaconda环境: {'Yes' if 'anaconda3' in sys.executable.lower() else 'No'}")

# 测试关键依赖
print("\n关键依赖检查:")
dependencies = {
    'pandas': 'pandas',
    'numpy': 'numpy',
    'gm': 'gm (掘金SDK)',
    'talib': 'talib',
    'akshare': 'akshare',
    'dotenv': 'python-dotenv'
}

for module, display_name in dependencies.items():
    try:
        if module == 'dotenv':
            from dotenv import load_dotenv
            print(f"  [OK] {display_name}")
        else:
            __import__(module)
            print(f"  [OK] {display_name}")
    except ImportError:
        print(f"  [--] {display_name} (未安装)")

print("\n" + "=" * 60)
