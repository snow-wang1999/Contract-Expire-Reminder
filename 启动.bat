@echo off
cd /d "%~dp0"
title Contract Expire Reminder
set "PY=%~dp0runtime\python\python.exe"
if not exist "%PY%" (
  echo [ERROR] runtime\python\python.exe not found.
  echo Please extract the WHOLE zip to a folder first, then run this file from that folder.
  pause
  exit /b 1
)
echo Starting... keep this window open while using the web page.
"%PY%" app.py
echo.
echo The service has stopped. If you see an error above, please send a screenshot.
pause
