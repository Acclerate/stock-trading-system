@echo off
echo ============================================================
echo 修复 strategy_tracker 数据库 - 清理无效记录
echo ============================================================
echo.

REM 停止Python进程（如果有）
taskkill /F /IM python.exe 2>nul

REM 等待2秒
timeout /t 2 /nobreak >nul

REM 备份并删除旧数据库
if exist "data\stock_tracker.db" (
    echo 备份旧数据库...
    move "data\stock_tracker.db" "data\stock_tracker.db.backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%.bak"
    echo 旧数据库已备份
)

echo.
echo 重新初始化数据库...
python -m strategy_tracker.main --init-db

echo.
echo 重新解析输出文件...
python -m strategy_tracker.main --parse-all

echo.
echo 计算持仓收益...
python -m strategy_tracker.main --calculate

echo.
echo ============================================================
echo 修复完成！
echo ============================================================
pause
