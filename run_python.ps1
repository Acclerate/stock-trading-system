# Stock Science Python运行脚本（PowerShell版本）
# 使用Anaconda base环境运行Python脚本

# 设置路径
$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PYTHON_EXE = "D:\ProgramData\anaconda3\python.exe"

# 检查参数
if ($args.Count -eq 0) {
    Write-Host "用法: .\run_python.ps1 <脚本路径> [参数...]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "示例:" -ForegroundColor Cyan
    Write-Host "  .\run_python.ps1 strategies\stockPre.py"
    Write-Host "  .\run_python.ps1 strategies\stockRanking.py"
    Write-Host "  .\run_python.ps1 tests\verify_diggold.py"
    Write-Host ""
    exit 1
}

# 切换到项目目录
Set-Location $PROJECT_DIR

# 运行Python脚本
Write-Host "正在使用 Anaconda Python 运行脚本..." -ForegroundColor Green
Write-Host ""

& $PYTHON_EXE $args

# 检查退出代码
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "脚本运行出错，错误代码: $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
