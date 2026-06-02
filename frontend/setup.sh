#!/bin/bash
# =============================================================================
# frontend/setup.sh — Offline frontend build for openEuler
#
# Usage: bash frontend/setup.sh
# =============================================================================
set -eu
(set -o pipefail) 2>/dev/null && set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Check Node.js ─────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    log_error "Node.js is not installed. Install Node.js 18+ first."
    echo "  openEuler: dnf install -y nodejs npm"
    exit 1
fi

NODE_VER=$(node -v | sed 's/v//')
log_info "Node.js version: v$NODE_VER"

# ── Offline npm install ───────────────────────────────────────────
VENDOR_CACHE="$PROJECT_DIR/vendor/npm-cache"
VENDOR_PKGS="$PROJECT_DIR/vendor/npm-packages"

if [ -d "$VENDOR_CACHE" ]; then
    log_info "Using offline npm cache from vendor/npm-cache/"
    NPM_CACHE_ARG="--cache $VENDOR_CACHE --prefer-offline"
elif [ "$(ls "$VENDOR_PKGS"/*.tgz 2>/dev/null | wc -l)" -gt 0 ]; then
    log_info "Found $(ls "$VENDOR_PKGS"/*.tgz | wc -l) local .tgz packages"
    log_info "Creating local npm registry overlay..."
    # Build a package registry from .tgz files
    mkdir -p /tmp/superdhcp-npm-local
    for tgz in "$VENDOR_PKGS"/*.tgz; do
        tar -xzf "$tgz" -C /tmp/superdhcp-npm-local/
    done
    # Use npm overlay
    NPM_CACHE_ARG="--cache /tmp/superdhcp-npm-local --prefer-offline"
else
    log_info "No offline packages found. Will download from registry."
    log_info "(Run vendor-download.sh on an internet-connected machine first.)"
    NPM_CACHE_ARG=""
fi

# ── Install dependencies ──────────────────────────────────────────
log_info "Installing npm dependencies..."
cd "$SCRIPT_DIR"
npm install $NPM_CACHE_ARG --no-audit --no-fund 2>&1 | tail -5 || {
    log_error "npm install failed. Falling back to online install..."
    npm install --no-audit --no-fund
}

# ── Build ─────────────────────────────────────────────────────────
log_info "Building frontend..."
npm run build

log_info "Frontend built successfully → $(ls -d "$SCRIPT_DIR/dist" 2>/dev/null && echo "$SCRIPT_DIR/dist/" || echo "check dist/")"
echo ""
echo "=== Done ==="
echo "Point Nginx root to: $SCRIPT_DIR/dist/"
