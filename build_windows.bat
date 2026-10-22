@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo  Building Standalone Windows Executable (.exe)
echo ==========================================================

cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Ensure Python is installed and in PATH.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo Running PyInstaller...
pyinstaller --clean -y android_automator.spec

if exist "dist\android-automator.exe" (
    echo ==========================================================
    echo  Build SUCCESSFUL!
    echo  Executable: dist\android-automator.exe
    echo  To run:
    echo    dist\android-automator.exe --port 28491
    echo ==========================================================
) else (
    echo Build failed: executable not found in dist\
    pause
    exit /b 1
)

pause
