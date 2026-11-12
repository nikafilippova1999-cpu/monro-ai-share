@echo off
rem Daily AI-share report to the ROP Telegram group. Run by Windows Task Scheduler.
rem No Cyrillic here on purpose: cmd.exe reads this file in the OEM codepage.
cd /d "%~dp0"
set AI_LOOKBACK_DAYS=21
set AI_WORKERS=6
set PY="%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist %PY% set PY=py
echo ---------- %DATE% %TIME% start >> ai_share.log
%PY% -I ai_share_daily.py >> ai_share.log 2>&1
echo ---------- %DATE% %TIME% exit=%ERRORLEVEL% >> ai_share.log
