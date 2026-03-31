@echo off
REM ==========================================================================
REM  KYC Platform - Windows Build Script
REM  Produces: desktop\pyinstaller\dist\KYCPlatform\KYCPlatform.exe
REM ==========================================================================

setlocal EnableDelayedExpansion

SET SCRIPT_DIR=%~dp0
SET PROJECT_ROOT=%SCRIPT_DIR%..\..
SET FRONTEND_DIR=%PROJECT_ROOT%\frontend
SET BACKEND_DIR=%PROJECT_ROOT%\backend
SET DIST_DIR=%SCRIPT_DIR%dist

echo ==================================================
echo   KYC Platform - Windows Build
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

where python >NUL 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python not found. Install from https://python.org/
    exit /b 1
)

where pyinstaller >NUL 2>&1
IF ERRORLEVEL 1 (
    echo [INFO] PyInstaller not found. Installing...
    pip install pyinstaller
    IF ERRORLEVEL 1 (
        echo [ERROR] Failed to install PyInstaller.
        exit /b 1
    )
)

REM --------------------------------------------------------------------------
REM  1. Build React frontend
REM --------------------------------------------------------------------------

echo [STEP 1/3] Building React frontend...
cd /d "%FRONTEND_DIR%"

IF NOT EXIST node_modules (
    echo [INFO] Installing frontend dependencies...
    call npm install
    IF ERRORLEVEL 1 (
        echo [ERROR] npm install failed.
        exit /b 1
    )
)

call npm run build
IF ERRORLEVEL 1 (
    echo [ERROR] Frontend build failed.
    exit /b 1
)
echo [OK] Frontend built: %FRONTEND_DIR%\dist

REM --------------------------------------------------------------------------
REM  2. Install backend Python dependencies
REM --------------------------------------------------------------------------

echo.
echo [STEP 2/3] Installing backend Python dependencies...
cd /d "%BACKEND_DIR%"

IF EXIST requirements.txt (
    pip install -r requirements.txt
    IF ERRORLEVEL 1 (
        echo [ERROR] pip install failed.
        exit /b 1
    )
)
echo [OK] Python dependencies installed.

REM --------------------------------------------------------------------------
REM  3. Run PyInstaller
REM --------------------------------------------------------------------------

echo.
echo [STEP 3/3] Running PyInstaller...
cd /d "%SCRIPT_DIR%"

REM Clean previous build
IF EXIST build rmdir /s /q build
IF EXIST "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

pyinstaller kyc.spec --clean --noconfirm
IF ERRORLEVEL 1 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

REM --------------------------------------------------------------------------
REM  Output summary
REM --------------------------------------------------------------------------

echo.
echo ==================================================
echo   Build complete!
echo ==================================================
echo.
echo   Executable: %DIST_DIR%\KYCPlatform\KYCPlatform.exe
echo.
echo   To distribute, zip the entire KYCPlatform folder:
echo     %DIST_DIR%\KYCPlatform\
echo.

endlocal
exit /b 0
