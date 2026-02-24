"""清除数据缓存"""
import os
import shutil

cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')

if os.path.exists(cache_dir):
    # 删除整个缓存目录
    shutil.rmtree(cache_dir)
    print(f"✅ 缓存已清除: {cache_dir}")
else:
    print(f"⚠️ 缓存目录不存在: {cache_dir}")

# 重新创建空的缓存结构
os.makedirs(os.path.join(cache_dir, 'stock'), exist_ok=True)
os.makedirs(os.path.join(cache_dir, 'macro'), exist_ok=True)
print(f"✅ 缓存目录已重新创建")
