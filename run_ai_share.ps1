# Daily AI-share report to the ROP Telegram group.
# Started by Windows Task Scheduler. The scheduler's own console process
# was getting killed with CTRL_C (exit 0xC000013A), so here we only LAUNCH
# python as an independent process and exit at once: nothing to interrupt.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$env:AI_LOOKBACK_DAYS = "21"
$env:AI_WORKERS = "6"

$py = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $py) { Add-Content "$here\ai_share.log" "$(Get-Date -f 'dd.MM.yyyy HH:mm:ss') no python found"; exit 1 }

Add-Content "$here\ai_share.log" "---------- $(Get-Date -f 'dd.MM.yyyy HH:mm:ss') launch"
$p = Start-Process -FilePath $py -ArgumentList "-I", "ai_share_daily.py" `
     -WorkingDirectory $here `
     -RedirectStandardOutput "$here\ai_share.out" `
     -RedirectStandardError  "$here\ai_share.err" `
     -WindowStyle Hidden -PassThru
Add-Content "$here\ai_share.log" "           started pid $($p.Id)"
