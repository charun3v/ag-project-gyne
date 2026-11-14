@echo off
title Run Recent Patients Tests
cd /d "%~dp0"
echo ========================================================
echo Running Recent Patients Tests on D: Drive...
echo ========================================================
echo.
".\venv\Scripts\python.exe" test_recent_patients.py
echo.
pause
