@echo off
setlocal

set "APP_ROOT=%~dp0"
cd /d "%APP_ROOT%"

set "PYTHONPATH=%APP_ROOT%src;%PYTHONPATH%"

if exist "%APP_ROOT%.venv\Scripts\python.exe" (
    call :launch "%APP_ROOT%.venv\Scripts\python.exe"
    exit /b
)

where py >nul 2>nul
if not errorlevel 1 (
    call :launch py
    exit /b
)

where python >nul 2>nul
if not errorlevel 1 (
    call :launch python
    exit /b
)

echo Python was not found. Install Python 3.11+ or create the project virtual environment.
pause
exit /b 1

:launch
%* -m simpost.app
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
    echo.
    echo Simulation Post Processor exited with error code %APP_EXIT%.
    pause
)
exit /b %APP_EXIT%
