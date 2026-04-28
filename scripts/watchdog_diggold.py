#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
掘金数据服务守护脚本
定期检查 gmterm-serv 是否存活，挂了自动重启
可配置为 Windows 计划任务每5分钟运行一次
"""
import subprocess
import sys
import time
from pathlib import Path

# 配置
GM_EXE = r"D:\Program Files\dfcf\EastMoneyGoldminer\goldminer3\emgm3.exe"
GM_PATH = r"D:\Program Files\dfcf\EastMoneyGoldminer"
TOKEN = "b0535281367c9d208540e282c79bdb9b4df8f9a8"
LOG_FILE = Path("logs/watchdog_diggold.log")

def is_service_running():
    """检查 gmterm-serv 是否在运行且端口就绪"""
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True, text=True, timeout=5
        )
        return ':7001' in result.stdout and 'LISTENING' in result.stdout
    except Exception:
        return False

def start_service():
    """隐藏窗口启动服务"""
    ps_cmd = (
        f"Start-Process -FilePath '{GM_EXE}' "
        f"-ArgumentList '--token={TOKEN}','--path={GM_PATH}' "
        f"-WindowStyle Hidden"
    )
    try:
        subprocess.run(
            ['powershell', '-Command', ps_cmd],
            timeout=10
        )
        return True
    except Exception as e:
        log(f"启动失败: {e}")
        return False

def log(msg):
    """写入日志"""
    LOG_FILE.parent.mkdir(exist_ok=True)
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def main():
    if is_service_running():
        log("服务正常运行")
        return

    log("服务未运行，尝试启动...")

    # 先清理残留进程
    subprocess.run(['taskkill', '/F', '/IM', 'gmterm-serv.exe'],
                   capture_output=True, timeout=5)
    subprocess.run(['taskkill', '/F', '/IM', 'emgm3.exe'],
                   capture_output=True, timeout=5)
    time.sleep(3)

    if start_service():
        log("启动命令已发送，等待初始化...")
        time.sleep(20)

        if is_service_running():
            log("服务重启成功")
        else:
            log("服务启动失败，请手动检查")
    else:
        log("启动命令执行失败")

if __name__ == "__main__":
    main()
