@echo off
REM ============================================================
REM 掘金数据服务无UI启动脚本 (隐藏窗口模式)
REM 通过 PowerShell WindowStyle Hidden 启动 emgm3.exe
REM 完整初始化 gmterm-serv 数据服务，窗口不可见
REM ============================================================

setlocal

set "GM_EXE=D:\Program Files\dfcf\EastMoneyGoldminer\goldminer3\emgm3.exe"
set "GM_PATH=D:\Program Files\dfcf\EastMoneyGoldminer"
set "TOKEN=b0535281367c9d208540e282c79bdb9b4df8f9a8"

REM ====== 检查是否已在运行 ======
tasklist /FI "IMAGENAME eq gmterm-serv.exe" 2>NUL | find /I "gmterm-serv.exe" >NUL
if %ERRORLEVEL%==0 (
    echo [OK] gmterm-serv already running
    netstat -ano | find ":7001" | find "LISTENING" >NUL 2>&1
    if %ERRORLEVEL%==0 (
        echo [OK] Port 7001 is listening
        echo [INFO] Service is ready. No action needed.
        exit /b 0
    ) else (
        echo [WARN] gmterm-serv running but port 7001 not ready, restarting...
        taskkill /F /IM gmterm-serv.exe >NUL 2>&1
        taskkill /F /IM emgm3.exe >NUL 2>&1
        timeout /t 3 /nobreak >NUL
    )
)

REM ====== 检查可执行文件 ======
if not exist "%GM_EXE%" (
    echo [ERROR] emgm3.exe not found: %GM_EXE%
    exit /b 1
)

REM ====== 隐藏窗口启动 emgm3.exe ======
echo [INFO] Starting GoldMiner (hidden window)...
powershell -Command "Start-Process -FilePath '%GM_EXE%' -ArgumentList '--token=%TOKEN%','--path=%GM_PATH%' -WindowStyle Hidden"

REM ====== 等待服务初始化 ======
echo [INFO] Waiting for service to initialize (20s)...
timeout /t 20 /nobreak >NUL

REM ====== 验证服务状态 ======
echo [INFO] Checking service status...

set MAX_RETRY=5
set RETRY=0

:check
netstat -ano | find ":7001" | find "LISTENING" >NUL 2>&1
if %ERRORLEVEL%==0 (
    echo [OK] gmterm-serv is running on port 7001
    echo [OK] GoldMiner data service started successfully (hidden mode)
    goto :done
)

set /a RETRY+=1
if %RETRY% GEQ %MAX_RETRY% (
    echo [ERROR] Failed to start gmterm-serv after %MAX_RETRY% retries
    echo [ERROR] Try opening GoldMiner GUI manually
    exit /b 1
)

echo [INFO] Port 7001 not ready, retrying (%RETRY%/%MAX_RETRY%)...
timeout /t 5 /nobreak >NUL
goto :check

:done
endlocal
