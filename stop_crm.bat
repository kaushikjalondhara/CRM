@echo off
title Stop Apex CRM
echo ===================================================
echo               Stopping Apex CRM
echo ===================================================
echo.
echo Stopping Backend (Port 5000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1

echo Stopping Frontend (Port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1

echo.
echo Apex CRM servers have been stopped.
echo ===================================================
pause
