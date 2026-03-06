# StockScience Daily Screen Scheduler Setup for Windows 11
# Run as Administrator

$ErrorActionPreference = "Stop"

$ProjectRoot = "D:\privategit\github\stockScience"
$TaskName = "StockScience_DailyScreens"
$PythonExe = "$ProjectRoot\.venv\Scripts\python.exe"
$ScriptPath = "$ProjectRoot\scripts\run_daily_screens.py"

# Function to write colored header
function Write-Header {
    param($Text, $Color = "Cyan")
    $line = "=" * 60
    Write-Host $line -ForegroundColor $Color
    Write-Host $Text -ForegroundColor $Color
    Write-Host $line -ForegroundColor $Color
    Write-Host ""
}

Write-Header "StockScience Task Scheduler Setup"

# Check admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Please run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell -> Run as Administrator" -ForegroundColor Yellow
    pause
    exit 1
}

# Check files
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Script not found: $ScriptPath" -ForegroundColor Red
    pause
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "WARNING: Python not found at: $PythonExe" -ForegroundColor Yellow
    Write-Host "Please update PythonExe path in the script" -ForegroundColor Yellow
}

# Delete existing task
try {
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
} catch {
    # No existing task, continue
}

# Create trigger (Mon-Fri 9 PM)
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 21:00

# Create action
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument $ScriptPath -WorkingDirectory $ProjectRoot

# Settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Principal
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Register task
try {
    Register-ScheduledTask -TaskName $TaskName -Trigger $trigger -Action $action -Settings $settings -Principal $Principal -ErrorAction Stop

    Write-Host ""
    Write-Header "Task Created Successfully!" "Green"

    Write-Host "Task Name: $TaskName"
    Write-Host "Schedule: Monday - Friday at 21:00"
    Write-Host "Run as: SYSTEM"
    Write-Host ""
    Write-Host "Useful Commands:" -ForegroundColor Cyan
    Write-Host "  View task: Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "  Run now:  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "  Delete:   Unregister-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Or open Task Scheduler: taskschd.msc" -ForegroundColor Gray

} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to create task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
pause
