@echo off
title Run Analytical Export System Tests
cd /d "%~dp0"
echo ========================================================
echo Running Analytical Export System Tests on D: Drive...
echo ========================================================
echo.
".\venv\Scripts\python.exe" test_export_system.py
echo.
pause
