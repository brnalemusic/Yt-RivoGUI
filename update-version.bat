@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Usage: update-version.bat W.X.Y.Z
    echo Example: update-version.bat 0.0.1.0
    exit /b 1
)

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] python is not found in your PATH.
    exit /b 1
)

python devscripts\update-version.py %*
exit /b %ERRORLEVEL%
