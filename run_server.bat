@echo off
title Gynae Oncology Database Server
cd /d "%~dp0"
echo ========================================================
echo   Starting Gynae Oncology Clinical Database Server
echo ========================================================
echo.
echo Opening http://127.0.0.1:8000 in your browser...
start http://127.0.0.1:8000/
echo.
echo Server is running. Keep this window open while using the application.
echo Press Ctrl+C to stop the server.
echo.
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
pause
