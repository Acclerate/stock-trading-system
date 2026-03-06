@echo off
chcp 65001 >nul
REM ==============================================================================
REM Daily Task Setup Script (Windows)
REM Creates scheduled task for daily stock screening
REM
REM Schedule: Every trading day starting at 21:00
REM 1. 21:00 - HS300 Screening (cache generation)
REM 2. 21:10 - ZZ500 Screening (cache generation)
REM 3. 21:20 - Trend Stocks Screening (full market scan)
REM 4. 21:30 - Low Volume Breakout (institutional strategy)
REM 5. 21:45 - Quick Select (cache-based)
REM 6. 22:00 - Multi-dimensional Ranking (deep analysis)
REM ==============================================================================

setlocal

REM Project root directory (auto-detect)
set "PROJECT_ROOT=%~dp0.."
set "PROJECT_ROOT=%PROJECT_ROOT:\=/%"

REM Python executable path (modify as needed)
set "PYTHON_EXE=C:\Python311\python.exe"

REM Try virtual environment if Python not found
if not exist "%PYTHON_EXE%" (
    if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
        set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
    )
)

REM Script path
set "SCRIPT_PATH=%PROJECT_ROOT%/scripts/run_daily_screens.py"

echo ===============================================================================
echo Daily Task Setup Script
echo ===============================================================================
echo.
echo Project Root: %PROJECT_ROOT%
echo Python: %PYTHON_EXE%
echo Script: %SCRIPT_PATH%
echo.

REM Check Python exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python not found
    echo Please modify PYTHON_EXE in this script
    pause
    exit /b 1
)

REM Check script exists
if not exist "%SCRIPT_PATH%" (
    echo ERROR: Script not found
    echo Path: %SCRIPT_PATH%
    pause
    exit /b 1
)

REM Task name
set "TASK_NAME=StockScience_DailyScreens"

REM Delete old task if exists
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo Deleting old task...
    schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
)

echo Creating scheduled task...
echo.

REM Create new task - Mon-Fri at 21:00 (script handles 6 strategies internally)
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\"" /sc weekly /d MON,TUE,WED,THU,FRI /st 21:00 /ru SYSTEM /rl HIGHEST /f

if %errorlevel% equ 0 (
    echo ===============================================================================
    echo Task created successfully!
    echo ===============================================================================
    echo.
    echo Task Name: %TASK_NAME%
    echo Schedule: Mon-Fri at 21:00
    echo Run As: SYSTEM
    echo.
    echo Execution Flow (controlled by script):
    echo   21:00 - HS300 Screening (cache generation)
    echo   21:10 - ZZ500 Screening (cache generation)
    echo   21:20 - Trend Stocks Screening (full market scan)
    echo   21:30 - Low Volume Breakout (institutional strategy)
    echo   21:45 - Quick Select (cache-based)
    echo   22:00 - Multi-dimensional Ranking (deep analysis)
    echo.
    echo To modify schedule, use Task Scheduler or:
    echo   schtasks /delete /tn "%TASK_NAME%" /f
    echo.
    echo View task details:
    echo   schtasks /query /tn "%TASK_NAME%" /fo list /v
    echo.
    echo ===============================================================================
) else (
    echo ===============================================================================
    echo Failed to create task!
    echo ===============================================================================
    echo.
    echo Please run as Administrator
    echo.
)

pause
