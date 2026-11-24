@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher "py" was not found. Install Python 3.10 or later.
    exit /b 1
)

py -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo Failed to install Bibi build dependencies.
    exit /b 1
)

py -m PyInstaller --noconfirm --clean --windowed --onedir --name Bibi bibi.py
if errorlevel 1 (
    echo Failed to package Bibi.
    exit /b 1
)

set "ISCC="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC=ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo Inno Setup 6 was not found. Install it, then run this script again.
    echo The packaged app is available in dist\Bibi.
    exit /b 1
)

"%ISCC%" installer.iss
if errorlevel 1 (
    echo Failed to build the installer.
    exit /b 1
)

echo.
echo Installer created: dist\Bibi-Setup.exe
exit /b 0
