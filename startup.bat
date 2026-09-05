@echo off
setlocal EnableExtensions

rem Always run relative to this script, even when launched from another folder.
cd /d "%~dp0"
set "PROJECT_DIR=%CD%"
set "VENV_PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"
set "CLI_COMMAND=%PROJECT_DIR%\.venv\Scripts\dtri-office-lunch.exe"
rem Avoid a broken or access-restricted user-level uv cache.
set "UV_CACHE_DIR=%TEMP%\dtri-office-lunch-uv-cache"

echo.
echo ============================================================
echo  DTRI Office Lunch - startup
echo  Project: %PROJECT_DIR%
echo ============================================================
echo.

echo [1/5] Checking for uv...
where uv >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('uv --version 2^>^&1') do echo       Found: %%I
    goto :check_venv
)

echo       Result: uv was not found. Installing uv...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression"
if errorlevel 1 goto :uv_install_failed

rem uv's Windows installer normally adds this directory to PATH for new shells.
set "PATH=%USERPROFILE%\.local\bin;%APPDATA%\uv\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 goto :uv_not_available
for /f "delims=" %%I in ('uv --version 2^>^&1') do echo       Result: installed %%I

:check_venv
echo.
echo [2/5] Checking the virtual environment...
if exist "%VENV_PYTHON%" (
    echo       Result: found .venv
) else (
    if exist "%PROJECT_DIR%\.venv" (
        echo       Result: .venv exists but is incomplete; expected Scripts\python.exe.
        echo       Please remove or repair .venv, then run this script again.
        exit /b 1
    )
    echo       Result: .venv was not found. Creating it...
    uv venv "%PROJECT_DIR%\.venv"
    if errorlevel 1 goto :venv_failed
    echo       Result: virtual environment created.
)

echo.
echo [3/5] Installing the editable Python package and its dependencies...
echo       Using temporary uv cache: %UV_CACHE_DIR%
uv pip install --python "%VENV_PYTHON%" -e "%PROJECT_DIR%"
if errorlevel 1 goto :dependencies_failed
echo       Result: editable package and Python dependencies are ready.

echo.
echo [4/5] Checking the Playwright Chromium browser...
"%VENV_PYTHON%" -m playwright install chromium
if errorlevel 1 goto :browser_failed
echo       Result: Chromium is ready.

echo.
echo [5/5] Starting the dtri-office-lunch CLI...
echo       Command: "%CLI_COMMAND%" %*
echo.
"%CLI_COMMAND%" %*
set "APP_EXIT_CODE=%ERRORLEVEL%"
echo.
if "%APP_EXIT_CODE%"=="0" (
    echo Result: dtri-office-lunch finished successfully.
) else (
    echo Result: dtri-office-lunch stopped with exit code %APP_EXIT_CODE%.
)
exit /b %APP_EXIT_CODE%

:uv_install_failed
echo.
echo Result: uv installation failed. Check your Internet connection and PowerShell policy, then try again.
exit /b 1

:uv_not_available
echo.
echo Result: uv was installed but is not available in this window.
echo Close this Command Prompt, open a new one, and run startup.bat again.
exit /b 1

:venv_failed
echo.
echo Result: unable to create .venv.
exit /b 1

:dependencies_failed
echo.
echo Result: dependency installation failed.
exit /b 1

:browser_failed
echo.
echo Result: Playwright Chromium installation failed.
exit /b 1
