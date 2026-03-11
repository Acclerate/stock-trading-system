@echo off
chcp 65001 >nul
REM ==============================================================================
REM Windows 定时任务设置脚本
REM
REM 使用说明:
REM   1. 每天早上运行 quick_start.py 启动终端并点击"量化"
REM   2. 本脚本设置定时任务，在交易日晚上执行策略
REM ==============================================================================

setlocal

REM 项目根目录
set "PROJECT_ROOT=%~dp0.."
set "PROJECT_ROOT=%PROJECT_ROOT:\=/%"

REM Python路径 (conda base)
set "PYTHON_EXE=D:\ProgramData\anaconda3\python.exe"

REM 脚本路径
set "SCRIPT_PATH=%PROJECT_ROOT%/scripts/run_daily_screens.py"

echo ===============================================================================
echo Stock Science 定时任务设置
echo ===============================================================================
echo.
echo 项目根目录: %PROJECT_ROOT%
echo Python: %PYTHON_EXE%
echo 脚本: %SCRIPT_PATH%
echo.

REM 检查文件
if not exist "%PYTHON_EXE%" (
    echo 错误: Python未找到
    echo 请修改脚本中的 PYTHON_EXE 路径
    pause
    exit /b 1
)

if not exist "%SCRIPT_PATH%" (
    echo 错误: 脚本未找到
    pause
    exit /b 1
)

REM 任务名称
set "TASK_NAME=StockScience_DailyScreens"

REM 删除旧任务
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo 删除旧任务...
    schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
)

echo 创建定时任务...
echo.

REM 创建任务: 周一到周五 21:00 执行
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\"" /sc weekly /d MON,TUE,WED,THU,FRI /st 21:00 /ru SYSTEM /rl HIGHEST /f

if %errorlevel% equ 0 (
    echo ===============================================================================
    echo 任务创建成功!
    echo ===============================================================================
    echo.
    echo 任务名称: %TASK_NAME%
    echo 执行时间: 周一到周五 21:00
    echo 运行身份: SYSTEM
    echo.
    echo 重要提示:
    echo   1. 每天早上需要先运行 quick_start.py 启动终端
    echo   2. 点击"量化"按钮后，终端会保持运行
    echo   3. 定时任务将在晚上自动执行策略
    echo.
    echo 修改/删除任务:
    echo   删除: schtasks /delete /tn "%TASK_NAME%" /f
    echo   查看: schtasks /query /tn "%TASK_NAME%" /fo list /v
    echo.
    echo ===============================================================================
) else (
    echo ===============================================================================
    echo 任务创建失败!
    echo ===============================================================================
    echo.
    echo 请以管理员身份运行此脚本
    echo.
)

pause
