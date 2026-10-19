@echo off
setlocal EnableDelayedExpansion

REM Always run from the folder that contains this script
cd /d "%~dp0"

echo ============================================
echo  My Attendance - Startup Script
echo ============================================
echo.
echo Working directory: %CD%
echo.

set PYTHON_EXE=

if exist "%USERPROFILE%\Desktop\Python312\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\Desktop\Python312\python.exe
    goto :found
)
if exist "%USERPROFILE%\Desktop\Python311\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\Desktop\Python311\python.exe
    goto :found
)
if exist "%USERPROFILE%\Desktop\Python310\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\Desktop\Python310\python.exe
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    goto :found
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set PYTHON_EXE=py
    goto :found
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set PYTHON_EXE=python
    goto :found
)

echo ERROR: Python was not found.
echo.
echo Install Python 3.10+ or use the full path, for example:
echo   "%USERPROFILE%\Desktop\Python312\python.exe" -m pip install -r requirements.txt
echo   "%USERPROFILE%\Desktop\Python312\python.exe" wsgi.py
pause
exit /b 1

:found
echo Using Python: %PYTHON_EXE%
echo.

if not exist ".env" (
    echo WARNING: .env file not found.
    if exist ".env.example" (
        echo Creating .env from .env.example ...
        copy ".env.example" ".env" >nul
        echo.
        echo Please edit .env and set:
        echo   ADMIN_USERNAME=yourname
        echo   ADMIN_PASSWORD=your-strong-password
        echo   SECRET_KEY=any-long-random-string
        echo.
        echo Then run this script again.
        notepad ".env"
        pause
        exit /b 0
    )
)

echo Installing / updating dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo Starting My Attendance...
echo Open http://127.0.0.1:5000 in your browser.
echo Press Ctrl+C to stop.
echo.

"%PYTHON_EXE%" wsgi.py
pause
