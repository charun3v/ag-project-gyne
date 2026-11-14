@echo off
title Clinical Fixes Verification Runner
color 1F
cd /d "D:\n3v\My projects\Databases\Gynae\Gynae database\AG project - Gyne"

echo ======================================================================
echo    RUNNING CLINICAL ENHANCEMENTS AND FIXES VERIFICATION
echo ======================================================================
echo.

if exist ".\venv\Scripts\python.exe" (
    ".\venv\Scripts\python.exe" test_clinical_fixes.py
) else (
    python test_clinical_fixes.py
)

echo.
echo ======================================================================
pause
