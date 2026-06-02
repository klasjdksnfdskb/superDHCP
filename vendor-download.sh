#!/bin/bash
# =============================================================================
# vendor-download.sh — Download ALL dependencies for offline deployment
#
# ⚠️  Run this on an internet-connected openEuler (or Linux) machine.
#    Then copy the entire superDHCP/ folder to the target offline machine.
#
#    This script will:
#    1. Download Python wheels into vendor/pypi/
#    2. Install & build frontend with npm
#    3. Package npm cache for offline reuse
#    4. Build frontend static files into frontend/dist/
# =============================================================================

set -eu
(set -o pipefail) 2>/dev/null && set -o pipefail
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

VENDOR_PYPI="$PROJECT_DIR/vendor/pypi"
VENDOR_NPM_CACHE="$PROJECT_DIR/vendor/npm-cache"

mkdir -p "$VENDOR_PYPI"

# ── Step 1: Python packages ───────────────────────────────────────
log_info "=== Step 1: Python Offline Packages ==="
if command -v pip3 &>/dev/null; then
    pip3 download -d "$VENDOR_PYPI" -r "$PROJECT_DIR/backend/requirements.txt"
    log_info "Downloaded $(ls "$VENDOR_PYPI"/*.whl 2>/dev/null | wc -l) Python wheels to vendor/pypi/"
else
    log_warn "pip3 not found. Skip Python package download."
    log_warn "Run on a machine with Python 3 to generate vendor/pypi/"
fi

# ── Step 2: Frontend packages ─────────────────────────────────────
log_info "=== Step 2: Frontend Offline Packages ==="
if ! command -v node &>/dev/null; then
    log_error "Node.js not found. Install: dnf install nodejs npm"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/frontend/package.json" ]; then
    log_warn "frontend/package.json not found. Skip frontend."
    exit 0
fi

cd "$PROJECT_DIR/frontend"

# Clean previous install
rm -rf node_modules package-lock.json 2>/dev/null || true

log_info "Installing npm dependencies..."
npm install --no-audit --no-fund 2>&1 | tail -3

# Copy npm cache for offline reuse
log_info "Copying npm cache to vendor/npm-cache/..."
NPM_CACHE=$(npm config get cache)
if [ -d "$NPM_CACHE/_cacache" ]; then
    rm -rf "$VENDOR_NPM_CACHE" 2>/dev/null || true
    mkdir -p "$VENDOR_NPM_CACHE"
    cp -r "$NPM_CACHE/_cacache" "$VENDOR_NPM_CACHE/"
    log_info "npm cache copied ($(find "$VENDOR_NPM_CACHE" -type f | wc -l) files)"
else
    log_warn "Could not find npm cache at: $NPM_CACHE"
fi

# Build frontend
log_info "Building frontend static files..."
npm run build 2>&1 | tail -5
log_info "Frontend built → frontend/dist/"

# Clean up node_modules (target machine will re-install from cache)
rm -rf node_modules
log_info "Removed node_modules/ (will be reinstalled on target)"

echo ""
echo "============================================"
echo "  ${GREEN}Vendor download complete!${NC}"
echo "============================================"
echo ""
echo "  Python wheels:   vendor/pypi/"
echo "  NPM cache:       vendor/npm-cache/"
echo "  Frontend dist:   frontend/dist/"
echo ""
echo "  Next: Copy the entire superDHCP/ folder"
echo "        to the offline openEuler machine,"
echo "        then run: sudo bash install.sh"
echo "============================================"
