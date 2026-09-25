@echo off
title Apex CRM Launcher
echo ===================================================
echo               Starting Apex CRM
echo ===================================================
echo.

:: 1. Check / Start MySQL
echo [1/3] Checking MySQL database on port 3306...
netstat -ano | findstr ":3306" >nul
if %ERRORLEVEL% neq 0 (
    echo Starting MySQL from XAMPP...
    if exist "C:\xampp\mysql\bin\mysqld.exe" (
        start "" /b "C:\xampp\mysql\bin\mysqld.exe" --defaults-file="C:\xampp\mysql\bin\my.ini" --standalone
        timeout /t 3 /nobreak >nul
    ) else (
        echo [WARNING] Please ensure MySQL is started from XAMPP Control Panel!
    )
) else (
    echo [OK] MySQL is running on port 3306.
)

:: 2. Start Backend Flask Server
echo [2/3] Starting Backend API Server on http://127.0.0.1:5000...
start "Apex CRM Backend (Port 5000)" cmd /k "cd /d %~dp0 && python backend/app.py"

:: 3. Start Frontend Web Server
echo [3/3] Starting Frontend Web Server on http://127.0.0.1:8000...
start "Apex CRM Frontend (Port 8000)" cmd /k "cd /d %~dp0 && python -m http.server 8000 --directory frontend"

:: Wait 2 seconds and open browser
timeout /t 2 /nobreak >nul
echo Opening Apex CRM in your default browser...
start http://127.0.0.1:8000/login.html

echo.
echo ===================================================
echo Apex CRM is now running!
echo Frontend: http://127.0.0.1:8000
echo Backend:  http://127.0.0.1:5000
echo.
echo Demo Accounts:
echo - Admin:    admin@crm.local   / Admin@123456
echo - Manager:  manager@crm.local / Manager@123456
echo - Sales:    sales@crm.local   / Sales@123456
echo - Staff:    staff@crm.local   / Staff@123456
echo ===================================================
echo Keep the backend and frontend command windows open.
pause
