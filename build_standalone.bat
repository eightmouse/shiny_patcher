@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "logo.ico" (
  echo [ERROR] Missing logo.ico
  pause
  exit /b 1
)

if not exist "kira_patch_gui.py" (
  echo [ERROR] Missing kira_patch_gui.py
  pause
  exit /b 1
)

for /f %%V in ('python -c "import sys; print(f''{sys.version_info.major}{sys.version_info.minor}'')"') do set "PYVER=%%V"
set "PYI_EXE=%APPDATA%\Python\Python%PYVER%\Scripts\pyinstaller.exe"

if exist "%PYI_EXE%" (
  call "%PYI_EXE%" --noconfirm --clean --onefile --windowed --name KiraPatch --icon logo.ico --add-data "logo.ico;." kira_patch_gui.py
) else (
  python -m PyInstaller --noconfirm --clean --onefile --windowed --name KiraPatch --icon logo.ico --add-data "logo.ico;." kira_patch_gui.py
)

if errorlevel 1 (
  echo.
  echo [ERROR] Build failed.
  pause
  exit /b 1
)

echo.
echo [OK] Standalone built: dist\KiraPatch.exe
pause
exit /b 0
