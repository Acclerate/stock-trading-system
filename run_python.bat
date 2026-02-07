@echo off
REM Stock Science Python运行脚本
REM 使用Anaconda base环境运行Python脚本

REM 设置路径
set PROJECT_DIR=%~dp0
set PYTHON_EXE=D:\ProgramData\anaconda3\python.exe

REM 检查是否提供了脚本参数
if "%1"=="" (
    echo 用法: run_python.bat ^<脚本路径^> [参数...]
    echo.
    echo 示例:
    echo   run_python.bat strategies\stockPre.py
    echo   run_python.bat strategies\stockRanking.py
    echo   run_python.bat tests\verify_diggold.py
    echo.
    pause
    exit /b 1
)

REM 运行Python脚本
echo 正在使用 Anaconda Python 运行脚本...
echo.
cd /d "%PROJECT_DIR%"
"%PYTHON_EXE%" %*

REM 如果出错则暂停
if errorlevel 1 (
    echo.
    echo 脚本运行出错，错误代码: %errorlevel%
    pause
)
