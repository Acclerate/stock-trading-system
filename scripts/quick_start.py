#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
东方财富量化 - 半自动化启动脚本

流程:
  1. 自动启动东方财富主终端
  2. 自动启动掘金量化启动器 (gmstarter.exe)
  3. 提示用户点击"量化"按钮
  4. 自动检测掘金连接
  5. 执行策略脚本
"""
import sys
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime

# Windows控制台编码处理
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# 设置项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# 配置
EASTMONEY_DIR = Path(r"D:\eastmoney\swc8")
MAINFREE_EXE = EASTMONEY_DIR / "mainfree.exe"
GM_STARTER_EXE = EASTMONEY_DIR / "EastMoneyGoldminer" / "gmstarter.exe"
GM_PROCESS = "gmstarter.exe"
EMGM_PROCESS = "emgm3.exe"

RUN_SCRIPT = PROJECT_ROOT / "scripts" / "run_daily_screens.py"
CONDA_PYTHON = Path(r"D:\ProgramData\anaconda3\python.exe")
PYTHON_EXE = str(CONDA_PYTHON) if CONDA_PYTHON.exists() else sys.executable


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def is_process_running(process_name: str) -> bool:
    """检查进程是否运行"""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {process_name}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return process_name.lower() in result.stdout.lower()
    except Exception:
        return False


def start_main_terminal() -> bool:
    """启动东方财富主终端"""
    if not MAINFREE_EXE.exists():
        print(f"  [FAIL] 未找到: {MAINFREE_EXE}")
        return False

    if is_process_running("mainfree.exe"):
        print("  [INFO] 东方财富终端已在运行")
        return True

    print(f"  正在启动: {MAINFREE_EXE}")
    try:
        subprocess.Popen([str(MAINFREE_EXE)], shell=True)
        print("  [OK] 东方财富终端已启动")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def start_gm_starter() -> bool:
    """启动掘金量化启动器"""
    if not GM_STARTER_EXE.exists():
        print(f"  [WARN] 未找到: {GM_STARTER_EXE}")
        print("         将跳过自动启动")
        return False

    print(f"  正在启动: {GM_STARTER_EXE}")
    try:
        # 在正确的目录下启动
        subprocess.Popen(
            [str(GM_STARTER_EXE)],
            cwd=str(GM_STARTER_EXE.parent),
            shell=True
        )
        print("  [OK] 掘金启动器已启动")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def check_diggold_connection() -> tuple[bool, str]:
    """检查掘金连接"""
    try:
        from gm.api import set_token, get_instruments
        token = os.getenv('DIGGOLD_TOKEN', '')
        if not token:
            return False, "DIGGOLD_TOKEN 未配置"
        set_token(token)
        result = get_instruments(exchanges='SHSE', sec_types=1, df=True)
        if result is not None and len(result) > 0:
            return True, f"成功 (获取到 {len(result)} 只股票)"
        else:
            return False, "返回空数据"
    except Exception as e:
        error_msg = str(e)
        if "1001" in error_msg:
            return False, "无法连接到掘金终端"
        return False, f"连接失败: {error_msg}"


def wait_for_connection(max_wait: int = 180) -> bool:
    """等待连接"""
    print(f"\n等待掘金连接... (最多{max_wait}秒)")

    start_time = time.time()
    check_interval = 3

    while time.time() - start_time < max_wait:
        elapsed = int(time.time() - start_time)
        print(f"  检测中... ({elapsed}/{max_wait}秒)", end='  \r', flush=True)

        success, message = check_diggold_connection()
        if success:
            print(f"\n  [OK] {message}")
            return True

        time.sleep(check_interval)

    print("\n  [FAIL] 等待超时")
    return False


def run_strategy() -> bool:
    """执行策略"""
    print("\n执行策略脚本...")
    if not RUN_SCRIPT.exists():
        print(f"  [FAIL] 脚本不存在: {RUN_SCRIPT}")
        return False

    try:
        result = subprocess.run(
            [PYTHON_EXE, str(RUN_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy()
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def main():
    """主函数"""
    print_header("东方财富量化 - 半自动化启动")

    print(f"\n当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ========== 步骤1: 启动东方财富主终端 ==========
    print("\n【步骤1】启动东方财富主终端")

    if not start_main_terminal():
        return 1

    print("\n  等待主终端加载...")
    time.sleep(5)

    # ========== 步骤2: 启动掘金量化启动器 ==========
    print("\n【步骤2】启动掘金量化启动器")

    gm_started = start_gm_starter()

    if gm_started:
        print("\n  等待掘金终端初始化...")
        time.sleep(5)

    # ========== 步骤3: 检查连接状态 ==========
    print("\n【步骤3】检测掘金连接")

    # 先快速检测一次
    success, message = check_diggold_connection()

    if success:
        print(f"  [OK] {message}")
        print("\n  掘金终端已就绪，直接执行策略！")
    else:
        print(f"  [INFO] {message}")
        print("\n  请在东方财富终端中点击 '量化' 按钮")
        print("  完成后按回车键继续...", end='')

        try:
            input()
        except KeyboardInterrupt:
            print("\n\n操作已取消")
            return 130

        # 再次等待连接
        print("\n【步骤4】等待掘金连接")

        if not wait_for_connection():
            print("\n  连接超时，请检查:")
            print("    1. 是否已点击'量化'按钮")
            print("    2. 掘金量化客户端是否正常运行")
            print("    3. 是否已登录东方财富账号")

            user_input = input("\n  是否仍要继续执行策略? (y/n): ").strip().lower()
            if user_input != 'y':
                return 1

    # ========== 步骤5: 执行策略 ==========
    print_header("执行策略")

    success = run_strategy()

    print_header("完成")
    if success:
        print("  [OK] 执行成功")
    else:
        print("  [WARN] 请查看日志")

    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        input("\n按回车键退出...")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(130)
    except Exception as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
