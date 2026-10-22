# PowerShell build script for Windows standalone binary
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Building Standalone Windows Executable (.exe)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$PipExe = Join-Path $ScriptDir ".venv\Scripts\pip.exe"
$PyInstallerExe = Join-Path $ScriptDir ".venv\Scripts\pyinstaller.exe"

Write-Host "Installing dependencies..."
& $PipExe install --upgrade pip
& $PipExe install -r requirements.txt

Write-Host "Compiling executable with PyInstaller..."
& $PyInstallerExe --clean -y android_automator.spec

$DistExe = Join-Path $ScriptDir "dist\android-automator.exe"
if (Test-Path $DistExe) {
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " Build SUCCESSFUL!" -ForegroundColor Green
    Write-Host " Executable: $DistExe" -ForegroundColor Green
    Write-Host " To run:" -ForegroundColor Green
    Write-Host "   .\dist\android-automator.exe --port 28491" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} else {
    Write-Error "Build failed: binary not found in dist/"
}
