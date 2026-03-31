#!/usr/bin/env bash
# ==========================================================================
#  KYC Platform - Linux / macOS Build Script
#  Produces: desktop/pyinstaller/dist/KYCPlatform/KYCPlatform
# ==========================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
BACKEND_DIR="${PROJECT_ROOT}/backend"
DIST_DIR="${SCRIPT_DIR}/dist"

echo "=================================================="
echo "  KYC Platform - Linux/macOS Build"
echo "=================================================="
echo ""

# --------------------------------------------------------------------------
#  0. Check prerequisites
# --------------------------------------------------------------------------

check_command() {
    if ! command -v "$1" &>/dev/null; then
        echo "[ERROR] '$1' not found. Please install it and re-run."
        exit 1
    fi
}

check_command node
check_command npm
check_command python3

# Ensure pyinstaller is available
if ! python3 -m PyInstaller --version &>/dev/null; then
    echo "[INFO] PyInstaller not found. Installing..."
    pip3 install pyinstaller
fi

# --------------------------------------------------------------------------
#  1. Build React frontend
# --------------------------------------------------------------------------

echo "[STEP 1/3] Building React frontend..."
cd "${FRONTEND_DIR}"

if [ ! -d "node_modules" ]; then
    echo "[INFO] Installing frontend dependencies..."
    npm install
fi

npm run build
echo "[OK] Frontend built: ${FRONTEND_DIR}/dist"

# --------------------------------------------------------------------------
#  2. Install backend Python dependencies
# --------------------------------------------------------------------------

echo ""
echo "[STEP 2/3] Installing backend Python dependencies..."
cd "${BACKEND_DIR}"

if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
fi
echo "[OK] Python dependencies installed."

# --------------------------------------------------------------------------
#  3. Run PyInstaller
# --------------------------------------------------------------------------

echo ""
echo "[STEP 3/3] Running PyInstaller..."
cd "${SCRIPT_DIR}"

# Clean previous build artifacts
rm -rf build "${DIST_DIR}"

python3 -m PyInstaller kyc.spec --clean --noconfirm

# --------------------------------------------------------------------------
#  Make the binary executable
# --------------------------------------------------------------------------

BINARY="${DIST_DIR}/KYCPlatform/KYCPlatform"
if [ -f "${BINARY}" ]; then
    chmod +x "${BINARY}"
fi

# --------------------------------------------------------------------------
#  Output summary
# --------------------------------------------------------------------------

echo ""
echo "=================================================="
echo "  Build complete!"
echo "=================================================="
echo ""
echo "  Executable: ${DIST_DIR}/KYCPlatform/KYCPlatform"
echo ""
echo "  To create a distributable archive:"
echo "    cd ${DIST_DIR} && tar -czf KYCPlatform.tar.gz KYCPlatform/"
echo ""
