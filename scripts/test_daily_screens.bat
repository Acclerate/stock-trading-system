@echo off
REM ==============================================================================
REM 测试脚本 - 手动执行每日策略
REM ==============================================================================

setlocal

set "PROJECT_ROOT=%~dp0.."
set "PYTHON_EXE=python"

echo ===============================================================================
echo 测试每日策略执行
echo ===============================================================================
echo.
echo 项目根目录: %PROJECT_ROOT%
echo.

REM 检测Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
        set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
        echo 使用虚拟环境Python
    ) else (
        echo 错误: 找不到Python解释器
        pause
        exit /b 1
    )
)

echo Python 解释器: %PYTHON_EXE%
echo.

REM 执行脚本
echo 开始执行...
echo.
"%PYTHON_EXE%" "%PROJECT_ROOT%\scripts\run_daily_screens.py"

echo.
echo ===============================================================================
echo 执行完成
echo ===============================================================================
pause
