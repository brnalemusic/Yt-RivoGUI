@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] python is not found in your PATH.
    exit /b 1
)

python devscripts\test_build.py %*
exit /b %ERRORLEVEL%
