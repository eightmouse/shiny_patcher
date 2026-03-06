@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PYTHON_CMD=python"
set "PATCHER_SCRIPT=shiny_patcher.py"
set "CONFIG_FILE=patcher_config.ini"
set "PASS_COUNT=0"
set "FAIL_COUNT=0"
set "SKIP_COUNT=0"
set "PATCH_ALL=0"

if not exist "%PATCHER_SCRIPT%" (
  echo [ERROR] Could not find "%PATCHER_SCRIPT%" in this folder.
  echo Put this .bat next to shiny_patcher.py.
  pause
  exit /b 1
)

if not exist "%CONFIG_FILE%" (
  >"%CONFIG_FILE%" (
    echo ; Gen 3 Shiny Odds Patcher config
    echo ; Set shiny odds as 1 in N ^(integer ^> 0^)
    echo ; Set mode as one of: auto, canonical, reroll, native, legacy
    echo odds=256
    echo mode=auto
  )
  echo [INFO] Created default config: "%CONFIG_FILE%"
)

call :load_config
if errorlevel 1 (
  pause
  exit /b 1
)

set "RUN_ODDS=!ODDS!"
set "RUN_MODE=!MODE!"

:parse_opts
if "%~1"=="" goto opts_done
set "ARG=%~1"
if /I "!ARG!"=="--all" (
  set "PATCH_ALL=1"
  shift
  goto parse_opts
)
if /I "!ARG!"=="--odds" (
  if "%~2"=="" (
    echo [ERROR] --odds requires a value.
    pause
    exit /b 1
  )
  set "RUN_ODDS=%~2"
  shift
  shift
  goto parse_opts
)
if /I "!ARG!"=="--mode" (
  if "%~2"=="" (
    echo [ERROR] --mode requires a value.
    pause
    exit /b 1
  )
  set "RUN_MODE=%~2"
  shift
  shift
  goto parse_opts
)
if "!ARG:~0,2!"=="--" (
  echo [ERROR] Unknown option: !ARG!
  echo Supported options: --odds N --mode MODE --all
  pause
  exit /b 1
)
goto opts_done

:opts_done
set "RUN_ODDS=!RUN_ODDS: =!"
set "RUN_MODE=!RUN_MODE: =!"

echo(!RUN_ODDS!| findstr /R "^[1-9][0-9]*$" >nul
if errorlevel 1 (
  echo [ERROR] Invalid odds: !RUN_ODDS!
  pause
  exit /b 1
)

set "MODE_OK="
if /I "!RUN_MODE!"=="auto" set "MODE_OK=1"
if /I "!RUN_MODE!"=="canonical" set "MODE_OK=1"
if /I "!RUN_MODE!"=="reroll" set "MODE_OK=1"
if /I "!RUN_MODE!"=="native" set "MODE_OK=1"
if /I "!RUN_MODE!"=="legacy" set "MODE_OK=1"
if not defined MODE_OK (
  echo [ERROR] Invalid mode: !RUN_MODE!
  echo Use auto, canonical, reroll, native, or legacy.
  pause
  exit /b 1
)

for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_TS=%%T"
if not defined RUN_TS set "RUN_TS=manual"

echo.
echo === KiraPatch Test Launcher ===
echo [INFO] Odds: 1/!RUN_ODDS!
echo [INFO] Mode: !RUN_MODE!
echo [INFO] Run tag: !RUN_TS!
echo.

if "%~1"=="" if "%PATCH_ALL%"=="0" if exist ".roms\*.gba" set "PATCH_ALL=1"

if "%PATCH_ALL%"=="1" (
  if not exist ".roms\*.gba" (
    echo [ERROR] --all requested but no .gba files found in .roms
    pause
    exit /b 1
  )
  for %%F in (".roms\*.gba") do (
    call :patch_one "%%~fF"
  )
  goto done
)

if "%~1"=="" (
  echo Drag and drop one or more .gba files onto this launcher,
  echo or run it with --all to patch all ROMs in .roms.
  echo Example: KiraPatch.bat --odds 16 --mode auto --all
  echo.
  pause
  exit /b 1
)

:process_next
if "%~1"=="" goto done
call :patch_one "%~1"
shift
goto process_next

:patch_one
set "ROM_PATH=%~1"

if /I not "%~x1"==".gba" (
  echo [SKIP] "%ROM_PATH%" ^(not a .gba file^)
  set /a SKIP_COUNT+=1
  goto :eof
)

if not exist "%ROM_PATH%" (
  echo [SKIP] "%ROM_PATH%" ^(file not found^)
  set /a SKIP_COUNT+=1
  goto :eof
)

call :build_output_path "%ROM_PATH%"

echo [PATCH] "%ROM_PATH%"
echo [OUT]   "!OUTPUT_PATH!"
%PYTHON_CMD% "%PATCHER_SCRIPT%" "%ROM_PATH%" --odds !RUN_ODDS! --mode !RUN_MODE! --output "!OUTPUT_PATH!"
if errorlevel 1 (
  echo [FAIL] "%ROM_PATH%"
  set /a FAIL_COUNT+=1
) else (
  echo [OK]   "%ROM_PATH%"
  set /a PASS_COUNT+=1
)
echo.
goto :eof

:build_output_path
set "BASE_DIR=%~dp1"
set "BASE_NAME=%~n1"
set "OUTPUT_PATH=%BASE_DIR%%BASE_NAME%.patched_1in!RUN_ODDS!_!RUN_MODE!_!RUN_TS!.gba"
if not exist "!OUTPUT_PATH!" goto :eof

set /a IDX=2
:output_loop
set "OUTPUT_PATH=%BASE_DIR%%BASE_NAME%.patched_1in!RUN_ODDS!_!RUN_MODE!_!RUN_TS!_v!IDX!.gba"
if exist "!OUTPUT_PATH!" (
  set /a IDX+=1
  goto output_loop
)
goto :eof

:load_config
set "ODDS="
set "MODE="

for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /I /B /C:"odds=" /C:"mode=" "%CONFIG_FILE%"`) do (
  if /I "%%~A"=="odds" set "ODDS=%%~B"
  if /I "%%~A"=="mode" set "MODE=%%~B"
)

if not defined ODDS (
  echo [ERROR] Could not find odds=... in "%CONFIG_FILE%".
  exit /b 1
)
if not defined MODE (
  echo [ERROR] Could not find mode=... in "%CONFIG_FILE%".
  exit /b 1
)

set "ODDS=!ODDS: =!"
set "MODE=!MODE: =!"

echo(!ODDS!| findstr /R "^[1-9][0-9]*$" >nul
if errorlevel 1 (
  echo [ERROR] Invalid odds in "%CONFIG_FILE%": !ODDS!
  exit /b 1
)

if /I "!MODE!"=="auto" set "MODE=auto"
if /I "!MODE!"=="canonical" set "MODE=canonical"
if /I "!MODE!"=="reroll" set "MODE=reroll"
if /I "!MODE!"=="native" set "MODE=native"
if /I "!MODE!"=="legacy" set "MODE=legacy"

if /I not "!MODE!"=="auto" if /I not "!MODE!"=="canonical" if /I not "!MODE!"=="reroll" if /I not "!MODE!"=="native" if /I not "!MODE!"=="legacy" (
  echo [ERROR] Invalid mode in "%CONFIG_FILE%": !MODE!
  exit /b 1
)
exit /b 0

:done
echo === Run Summary ===
echo [OK]   !PASS_COUNT!
echo [FAIL] !FAIL_COUNT!
echo [SKIP] !SKIP_COUNT!
echo.
echo Finished.
pause
exit /b 0
