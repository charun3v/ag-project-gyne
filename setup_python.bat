@echo off
title Python Setup and Diagnostic
cd /d "D:\n3v\My projects\Databases\Gynae\Gynae database\AG project - Gyne"
echo ========================================================
echo Configuring Python for Gynae Database...
echo ========================================================
echo.

echo Testing Python executable: > python_diagnostic.log
"C:\Users\charu\AppData\Local\Python\pythoncore-3.15-64\python.exe" -V >> python_diagnostic.log 2>&1
echo Testing py launcher: >> python_diagnostic.log
py -V >> python_diagnostic.log 2>&1

echo Checking pip: >> python_diagnostic.log
py -m pip --version >> python_diagnostic.log 2>&1

echo Creating clean virtual environment in venv_new... >> python_diagnostic.log
py -m venv venv_new >> python_diagnostic.log 2>&1

echo Installing project requirements in venv_new... >> python_diagnostic.log
".\venv_new\Scripts\python.exe" -m pip install --upgrade pip >> python_diagnostic.log 2>&1
".\venv_new\Scripts\pip.exe" install Django>=4.2,<5.0 python-dotenv pillow reportlab svglib pypdf openpyxl >> python_diagnostic.log 2>&1

echo Testing Django check with new venv: >> python_diagnostic.log
".\venv_new\Scripts\python.exe" manage.py check >> python_diagnostic.log 2>&1

echo Done! >> python_diagnostic.log
echo Finished! Check python_diagnostic.log.
pause
