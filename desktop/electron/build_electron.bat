@echo off
REM ==========================================================================
REM  KYC Platform - Electron Desktop Build Script (Windows)
REM  Produces: desktop\electron\dist\KYC Platform Setup x.x.x.exe
REM ==========================================================================

setlocal EnableDelayedExpansion

SET SCRIPT_DIR=%~dp0
SET PROJECT_ROOT=%SCRIPT_DIR%..\..
SET FRONTEND_DIR=%PROJECT_ROOT%\frontend
SET ELECTRON_DIR=%SCRIPT_DIR%

echo ==================================================
echo   KYC Platform - Electron Build (Windows)
echo ==================================================
echo.

REM --------------------------------------------------------------------------
REM  0. Check prerequisites
REM --------------------------------------------------------------------------

where node >NUL 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org/
    exit /b 1
)

where npm >NUL 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] npm not found. Reinstall Node.js.
    exit /b 1
)

echo [OK] Prerequisites satisfied.
echo.

REM --------------------------------------------------------------------------
REM  1. Build React frontend
REM --------------------------------------------------------------------------

echo [STEP 1/3] Building React frontend...
cd /d "%FRONTEND_DIR%"

IF NOT EXIST node_modules (
    echo [INFO] Installing frontend npm dependencies...
    call npm install
    IF ERRORLEVEL 1 (
        echo [ERROR] npm install failed in frontend.
        exit /b 1
    )
)

call npm run build
IF ERRORLEVEL 1 (
    echo [ERROR] React build failed.
    exit /b 1
)
echo [OK] React build output: %FRONTEND_DIR%\dist

REM --------------------------------------------------------------------------
REM  2. Install Electron dependencies
REM --------------------------------------------------------------------------

echo.
echo [STEP 2/3] Installing Electron dependencies...
cd /d "%ELECTRON_DIR%"

IF NOT EXIST node_modules (
    call npm install
    IF ERRORLEVEL 1 (
        echo [ERROR] npm install failed in electron dir.
        exit /b 1
    )
)
echo [OK] Electron dependencies installed.

REM --------------------------------------------------------------------------
REM  3. Package with electron-builder
REM --------------------------------------------------------------------------

echo.
echo [STEP 3/3] Packaging with electron-builder...

call npm run build
IF ERRORLEVEL 1 (
    echo [ERROR] electron-builder failed.
    exit /b 1
)

REM --------------------------------------------------------------------------
REM  Summary
REM --------------------------------------------------------------------------

echo.
echo ==================================================
echo   Build complete!
echo ==================================================
echo.
echo   Installer: %ELECTRON_DIR%dist\
echo.
echo   Look for a file named: KYC Platform Setup *.exe
echo.

endlocal
exit /b 0
