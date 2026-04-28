@echo off
REM 停止掘金数据服务
echo [INFO] Stopping GoldMiner service...
taskkill /F /IM emgm3.exe >NUL 2>&1
taskkill /F /IM gmterm-serv.exe >NUL 2>&1
timeout /t 2 /nobreak >NUL
echo [OK] All GoldMiner processes stopped
