@echo off
title Gynae Oncology Database Server
cd /d "%~dp0"
echo ========================================================
echo Starting Gynae Oncology Database from D: Drive...
echo Application folder: %CD%
echo ========================================================
echo.

rem Check if venv_new exists, if not create and install dependencies
if not exist ".\venv_new\Scripts\python.exe" (
    echo [1/3] Setting up fresh Python environment with updated Python...
    echo Please wait while the virtual environment is created...
    py -m venv venv_new
    if errorlevel 1 (
        echo Trying direct Python path...
        "C:\Users\charu\AppData\Local\Python\pythoncore-3.15-64\python.exe" -m venv venv_new
    )
    
    echo [2/3] Installing Django and database dependencies...
    ".\venv_new\Scripts\python.exe" -m pip install --upgrade pip
    ".\venv_new\Scripts\pip.exe" install "Django>=4.2,<5.0" python-dotenv pillow reportlab svglib pypdf openpyxl
    echo Environment setup complete!
    echo.
)

echo [3/3] Starting local Gynae Oncology Database server...
echo Server URL: http://127.0.0.1:8000/
echo.
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000/"
".\venv_new\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
pause
