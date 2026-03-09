@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "logo.png" (
  echo [ERROR] Missing logo.png
  pause
  exit /b 1
)

if not exist "build_logo_icon.py" (
  echo [ERROR] Missing build_logo_icon.py
  pause
  exit /b 1
)

if not exist "kira_patch_gui.py" (
  echo [ERROR] Missing kira_patch_gui.py
  pause
  exit /b 1
)

python build_logo_icon.py
if errorlevel 1 (
  echo.
  echo [ERROR] Could not regenerate logo.ico
  pause
  exit /b 1
)

for /f %%V in ('python -c "import sys; print(f''{sys.version_info.major}{sys.version_info.minor}'')"') do set "PYVER=%%V"
set "PYI_EXE=%APPDATA%\Python\Python%PYVER%\Scripts\pyinstaller.exe"

if exist "%PYI_EXE%" (
  call "%PYI_EXE%" --noconfirm --clean --onefile --windowed --name KiraPatch --icon logo.ico --add-data "logo.ico;." --add-data "logo.png;." kira_patch_gui.py
) else (
  python -m PyInstaller --noconfirm --clean --onefile --windowed --name KiraPatch --icon logo.ico --add-data "logo.ico;." --add-data "logo.png;." kira_patch_gui.py
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
