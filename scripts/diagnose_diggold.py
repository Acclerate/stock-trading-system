#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
掘金终端连接详细诊断
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Windows encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

def diagnose():
    print("=" * 70)
    print("掘金终端连接详细诊断")
    print("=" * 70)

    # 1. Token检查
    print("\n[1] Token配置检查")
    print("-" * 70)
    token = os.getenv('DIGGOLD_TOKEN', '')
    if not token:
        print("X DIGGOLD_TOKEN 未设置")
        return False
    print(f"OK Token已配置: {token[:16]}...")
    print(f"   Token长度: {len(token)} 字符")

    # 2. SDK导入检查
    print("\n[2] SDK导入检查")
    print("-" * 70)
    try:
        from gm.api import set_token
        print("OK gm.api 导入成功")
    except ImportError as e:
        print(f"X gm.api 导入失败: {e}")
        print("   请运行: pip install gm")
        return False

    # 3. Token设置
    print("\n[3] Token初始化")
    print("-" * 70)
    try:
        set_token(token)
        print("OK set_token() 调用成功")
    except Exception as e:
        print(f"X set_token() 失败: {e}")
        return False

    # 4. 连接测试 - 使用 history() 测试 (更可靠)
    print("\n[4] 连接测试")
    print("-" * 70)

    # 导入 history
    try:
        from gm.api import history
    except ImportError:
        print("X 无法导入 history 函数")
        return False

    # 测试1: history() - 获取股票历史数据 (推荐方法)
    print("\n测试1: history() - 获取浦发银行历史数据")
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        result = history(
            symbol='SHSE.600000',
            frequency='1d',
            start_time=start_date,
            end_time=end_date,
            df=True
        )

        if result is not None and not result.empty:
            print(f"OK 成功! 获取到 {len(result)} 条数据")
            print(f"  测试股票: 浦发银行 (600000)")
            print(f"  日期范围: {start_date} ~ {end_date}")
            print("\n" + "=" * 70)
            print("诊断结果: 掘金终端连接正常!")
            print("=" * 70)
            return True
        else:
            print("X 返回空数据")
    except Exception as e:
        error_msg = str(e)
        print(f"X 失败: {error_msg}")

        # 详细分析错误
        print("\n[5] 错误详细分析")
        print("-" * 70)

        if "1024" in error_msg or "orgcode" in error_msg.lower():
            print("错误代码 1024 - 无法获取组织代码")
            print("\n可能原因:")
            print("1. 掘金终端未登录账号")
            print("   -> 请在掘金终端内登录您的账号")
            print("2. Token与登录账号不匹配")
            print("   -> Token必须来自当前登录的账号")
            print("3. 掘金终端正在初始化")
            print("   -> 请等待终端完全加载后再试")
            print("\n解决步骤:")
            print("a. 在掘金终端右上角确认已登录用户名")
            print("b. 如果未登录，请先登录")
            print("c. 登录后在终端内获取新的Token")
            print("d. 更新.env文件中的DIGGOLD_TOKEN")

        elif "连接" in error_msg or "网络" in error_msg or "timeout" in error_msg.lower():
            print("网络连接错误")
            print("请检查:")
            print("- 掘金终端是否正常运行")
            print("- 网络连接是否正常")
            print("- 防火墙是否阻止了连接")

    print("\n" + "=" * 70)
    print("诊断结果: 掘金终端连接失败")
    print("=" * 70)
    return False

if __name__ == "__main__":
    success = diagnose()
    sys.exit(0 if success else 1)
