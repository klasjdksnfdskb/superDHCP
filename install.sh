#!/bin/bash
set -eu
(set -o pipefail) 2>/dev/null && set -o pipefail

# =============================================================================
# superDHCP - openEuler Offline Installation Script
# -----------------------------------------------------------
# Runs on openEuler 22.03+ / 24.03. No Docker required.
# All dependencies included in vendor/ directory.
# =============================================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

APP_USER="superdhcp"
APP_DIR="/opt/superDHCP"
VENV_DIR="$APP_DIR/backend/.venv"
DATA_DIR="/var/lib/superdhcp"
CONFIG_DIR="/etc/superdhcp"
LOG_DIR="/var/log/superdhcp"

PHP_VER=""  # not used, just for consistency

# ── Pre-flight check ───────────────────────────────────────────────
preflight() {
    log_info "=== superDHCP v1.0.0 Offline Installer ==="
    echo ""

    if [ "$(id -u)" -ne 0 ]; then
        log_error "This script must be run as root (sudo)."
        exit 1
    fi

    if ! grep -qEi 'openEuler|EulerOS' /etc/os-release 2>/dev/null; then
        log_warn "This system does not appear to be openEuler."
        log_warn "superDHCP is tested on openEuler 22.03+ / 24.03."
        read -p "Continue anyway? (y/N): " cont
        if [ "$cont" != "y" ] && [ "$cont" != "Y" ]; then
            exit 0
        fi
    fi
}

# ── System Dependencies ────────────────────────────────────────────
install_system_deps() {
    log_info "Installing system dependencies..."

    # Detect package manager (dnf on openEuler)
    if command -v dnf &>/dev/null; then
        PKG_MGR="dnf"
    elif command -v yum &>/dev/null; then
        PKG_MGR="yum"
    else
        log_error "No supported package manager found (dnf/yum)."
        exit 1
    fi

    log_info "Using package manager: $PKG_MGR"

    $PKG_MGR install -y \
        python3 python3-devel python3-pip \
        postgresql postgresql-server postgresql-devel \
        redis nginx rsync \
        policycoreutils-python-utils \
        gcc gcc-c++ make \
        libffi-devel openssl-devel bzip2-devel \
        &>/dev/null && log_info "System packages installed." || {
        log_warn "Some packages may already be installed, continuing..."
    }
}

# ── Create System User ─────────────────────────────────────────────
create_user() {
    if ! id "$APP_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$APP_DIR" "$APP_USER"
        log_info "Created user: $APP_USER"
    else
        log_info "User $APP_USER already exists"
    fi
}

# ── Directory Structure ────────────────────────────────────────────
setup_dirs() {
    log_info "Setting up directories..."

    mkdir -p "$APP_DIR" "$DATA_DIR" "$CONFIG_DIR" "$LOG_DIR"

    # Copy backend application files (frontend is handled by setup_frontend)
    rsync -a --delete "$PROJECT_DIR/backend/" "$APP_DIR/backend/"

    chown -R "$APP_USER:$APP_USER" "$APP_DIR" "$DATA_DIR" "$CONFIG_DIR" "$LOG_DIR"
    chmod 755 "$APP_DIR"       # nginx needs +x to traverse
    chmod 750 "$CONFIG_DIR"    # keep config restricted
    chmod 770 "$DATA_DIR" "$LOG_DIR"
}

# ── Python Virtual Environment (Offline) ───────────────────────────
setup_python_venv() {
    log_info "Setting up Python virtual environment..."

    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    # Upgrade pip from local wheel or online
    pip install --upgrade pip 2>/dev/null || true

    if [ -d "$PROJECT_DIR/vendor/pypi" ] && ls "$PROJECT_DIR/vendor/pypi/"*.whl &>/dev/null 2>&1; then
        log_info "Installing Python packages from vendor/pypi/ (offline mode)..."
        pip install --no-index --find-links="$PROJECT_DIR/vendor/pypi" -r "$APP_DIR/backend/requirements.txt"
    else
        log_warn "vendor/pypi/ not found or empty, trying online install..."
        log_warn "If offline, first run: bash vendor-download.sh on an internet-connected machine"
        pip install -r "$APP_DIR/backend/requirements.txt"
    fi

    deactivate
    log_info "Python environment ready."
}

# ── Frontend Setup (Offline) ──────────────────────────────────────
setup_frontend() {
    log_info "Setting up frontend..."

    mkdir -p "$APP_DIR/frontend"

    # If pre-built dist exists, use it directly
    if [ -d "$PROJECT_DIR/frontend/dist" ] && [ -f "$PROJECT_DIR/frontend/dist/index.html" ]; then
        log_info "Using pre-built frontend from frontend/dist/"
        rsync -a --delete "$PROJECT_DIR/frontend/dist/" "$APP_DIR/frontend/"
        return 0
    fi

    # Fallback: dist might be in deploy-package (e.g. WinSCP skipped dist/ folder)
    if [ -d "$PROJECT_DIR/deploy-package/frontend/dist" ] && [ -f "$PROJECT_DIR/deploy-package/frontend/dist/index.html" ]; then
        log_info "Using pre-built frontend from deploy-package/frontend/dist/"
        rsync -a --delete "$PROJECT_DIR/deploy-package/frontend/dist/" "$APP_DIR/frontend/"
        return 0
    fi

    # Otherwise, try to build from offline packages
    if [ -f "$PROJECT_DIR/frontend/setup.sh" ]; then
        log_info "Running frontend offline setup..."
        cd "$PROJECT_DIR"
        if bash frontend/setup.sh 2>&1; then
            if [ -d "$PROJECT_DIR/frontend/dist" ] && [ -f "$PROJECT_DIR/frontend/dist/index.html" ]; then
                rsync -a --delete "$PROJECT_DIR/frontend/dist/" "$APP_DIR/frontend/"
                log_info "Frontend built and deployed successfully."
                return 0
            fi
        fi
        log_warn "Frontend build failed. Serving setup guide page instead."
    else
        log_warn "No frontend setup available. Serving setup guide page."
        log_warn "Run vendor-download.sh on an internet-connected machine first."
    fi

    # Fallback: create a placeholder so nginx doesn't return 500
    cat > "$APP_DIR/frontend/index.html" <<'FALLBACK_HTML'
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>superDHCP - Setup Guide</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0e17; color: #e0e6ed; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
.card { background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 48px; max-width: 600px; width: 90%; text-align: center; }
h1 { font-size: 28px; margin-bottom: 8px; color: #3b82f6; }
.badge { display: inline-block; background: #1e3a5f; color: #3b82f6; padding: 4px 16px; border-radius: 20px; font-size: 14px; margin-bottom: 24px; }
.step { text-align: left; background: #0f172a; border-radius: 8px; padding: 16px 20px; margin: 12px 0; }
.step .num { display: inline-block; background: #3b82f6; color: #fff; width: 24px; height: 24px; line-height: 24px; text-align: center; border-radius: 50%; font-size: 13px; margin-right: 10px; }
code { background: #1e293b; padding: 2px 8px; border-radius: 4px; font-size: 13px; color: #60a5fa; }
.api-link { margin-top: 24px; }
.api-link a { color: #3b82f6; text-decoration: none; font-weight: 500; }
.api-link a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="card">
  <h1>superDHCP</h1>
  <div class="badge">v1.0.0 &middot; Carrier-Grade DHCP Server</div>
  <p style="margin-bottom:8px; color:#9ca3af;">The Web UI frontend is not yet built.</p>
  <p style="margin-bottom:24px; color:#9ca3af;">Follow the steps below to enable it:</p>

  <div class="step">
    <span class="num">1</span> On an <strong>internet-connected</strong> Linux machine:
    <br><code>bash vendor-download.sh</code>
  </div>
  <div class="step">
    <span class="num">2</span> Copy the project to this server:
    <br><code>scp -r superDHCP/ root@&lt;this-server&gt;:/tmp/</code>
  </div>
  <div class="step">
    <span class="num">3</span> Re-run the installer:
    <br><code>cd /tmp/superDHCP &amp;&amp; sudo bash install.sh</code>
  </div>

  <div class="api-link">
    <p style="color:#6b7280; font-size:14px;">Backend API is available at:</p>
    <a href="/api/docs">/api/docs &rarr; Swagger UI</a>
  </div>
</div>
</body>
</html>
FALLBACK_HTML

    log_info "Created fallback index.html (setup guide)."
}

# ── PostgreSQL Setup ───────────────────────────────────────────────
setup_postgres() {
    log_info "Configuring PostgreSQL..."

    # Initialize database cluster if not already done
    PG_DATA="/var/lib/pgsql/data"
    if [ ! -f "$PG_DATA/PG_VERSION" ]; then
        log_info "Initializing PostgreSQL database cluster..."
        su - postgres -c "/usr/bin/initdb -D $PG_DATA"
    fi

    # Start PostgreSQL
    systemctl enable postgresql
    systemctl start postgresql

    # Create database and user (idempotent)
    su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='$APP_USER'\"" | grep -q 1 || {
        su - postgres -c "psql -c \"CREATE USER $APP_USER WITH PASSWORD 'superdhcp_pg_2024';\""
    }
    su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='superdhcp'\"" | grep -q 1 || {
        su - postgres -c "psql -c \"CREATE DATABASE superdhcp OWNER $APP_USER;\""
        su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE superdhcp TO $APP_USER;\""
    }

    # ── Schema Migrations ───────────────────────────────────────────
    log_info "Applying database schema migrations..."
    su - postgres -c "psql -d superdhcp -c \"
        ALTER TABLE address_pools ADD COLUMN IF NOT EXISTS tag_id uuid REFERENCES custom_tags(id) ON DELETE SET NULL;
        ALTER TABLE subnets ADD COLUMN IF NOT EXISTS v6_mode varchar(16);
        ALTER TABLE subnets ADD COLUMN IF NOT EXISTS delegation_prefix varchar(64);
        ALTER TABLE subnets ADD COLUMN IF NOT EXISTS enable_reservation boolean DEFAULT false;
        ALTER TABLE subnets ADD COLUMN IF NOT EXISTS last_assigned_ip inet;
        ALTER TABLE subnets ADD COLUMN IF NOT EXISTS reservation_start inet;
        ALTER TABLE subnets ADD COLUMN IF NOT EXISTS reservation_end inet;
    \"" 2>/dev/null || log_warn "Migration may have already been applied, continuing..."

    log_info "PostgreSQL configured."
}

# ── Redis Setup ────────────────────────────────────────────────────
setup_redis() {
    log_info "Configuring Redis..."

    systemctl enable redis
    systemctl start redis
    log_info "Redis running."
}

# ── Application Config ─────────────────────────────────────────────
setup_config() {
    log_info "Generating application config..."

    cat > "$CONFIG_DIR/.env" <<EOF
# superDHCP Configuration
DATABASE_URL=postgresql+asyncpg://$APP_USER:superdhcp_pg_2024@localhost:5432/superdhcp
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
LOG_LEVEL=INFO
DHCPv4_INTERFACE=eth0
DHCPv6_INTERFACE=eth0
EOF

    chown "$APP_USER:$APP_USER" "$CONFIG_DIR/.env"
    chmod 600 "$CONFIG_DIR/.env"
    log_info "Config written to $CONFIG_DIR/.env"
}

# ── SELinux Configuration ───────────────────────────────────────
configure_selinux() {
    # Check if SELinux is enforcing
    if command -v getenforce &>/dev/null && [ "$(getenforce 2>/dev/null)" = "Enforcing" ]; then
        log_info "SELinux is Enforcing. Applying context for Nginx..."

        # Allow nginx to make outbound connections (proxy_pass to backend)
        setsebool -P httpd_can_network_connect 1 2>/dev/null || true

        # Apply httpd context to frontend files so nginx can read them
        if [ -d "$APP_DIR/frontend" ]; then
            semanage fcontext -a -t httpd_sys_content_t "$APP_DIR/frontend(/.*)?" 2>/dev/null || \
                chcon -R -t httpd_sys_content_t "$APP_DIR/frontend/" 2>/dev/null || true
            restorecon -Rv "$APP_DIR/frontend/" 2>/dev/null || true
            log_info "SELinux context applied to $APP_DIR/frontend/."
        fi

        # Apply httpd context only to the parent directory itself
        # (not recursive) so nginx can traverse to frontend/
        semanage fcontext -a -t httpd_sys_content_t "$APP_DIR" 2>/dev/null || \
            chcon -t httpd_sys_content_t "$APP_DIR/" 2>/dev/null || true
        restorecon -v "$APP_DIR/" 2>/dev/null || true
        log_info "SELinux context applied to $APP_DIR/ (parent traversal)."

        # NOTE: Do NOT apply httpd_sys_content_t to backend/ — nginx
        # accesses backend via proxy_pass, and httpd_sys_content_t
        # on .venv/bin/python will cause systemd status=203/EXEC.
    elif command -v getenforce &>/dev/null; then
        log_info "SELinux is $(getenforce). No context fix needed."
    else
        log_info "SELinux not detected."
    fi
}


# ── Nginx Setup ────────────────────────────────────────────────────
setup_nginx() {
    log_info "Configuring Nginx..."

    # Copy nginx config
    if [ -f "$PROJECT_DIR/deploy/nginx-superdhcp.conf" ]; then
        cp "$PROJECT_DIR/deploy/nginx-superdhcp.conf" /etc/nginx/conf.d/superdhcp.conf
    else
        cat > /etc/nginx/conf.d/superdhcp.conf <<'NGINX_EOF'
server {
    listen 80;
    server_name _;

    # Frontend static files
    root /opt/superDHCP/frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;

        # Security headers
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
NGINX_EOF
    fi

    systemctl enable nginx
    systemctl restart nginx
    log_info "Nginx configured."
}

# ── Systemd Service ────────────────────────────────────────────────
setup_service() {
    log_info "Setting up systemd service..."

    cat > /etc/systemd/system/superdhcp.service <<EOF
[Unit]
Description=superDHCP - Enterprise DHCP Server
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR/backend
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=$CONFIG_DIR/.env
AmbientCapabilities=CAP_NET_BIND_SERVICE
ExecStart=$VENV_DIR/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5
TimeoutStopSec=30
LimitNOFILE=65536
LimitNPROC=32768

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable superdhcp
    log_info "systemd service created."
}

# ── Kernel Tuning for High Concurrency ─────────────────────────────
setup_kernel() {
    log_info "Applying kernel tuning for DHCP high concurrency..."

    if [ -f "$PROJECT_DIR/deploy/openEuler/sysctl-dhcp.conf" ]; then
        cp "$PROJECT_DIR/deploy/openEuler/sysctl-dhcp.conf" /etc/sysctl.d/99-superdhcp.conf
    else
        cat > /etc/sysctl.d/99-superdhcp.conf <<'SYSCTL_EOF'
# superDHCP Kernel Tuning (500K+ concurrent DHCP sessions)
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 500000
net.ipv4.tcp_max_syn_backlog = 300000
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 10
net.ipv4.ip_local_port_range = 1024 65000
fs.file-max = 2097152
fs.nr_open = 2097152
vm.swappiness = 10
SYSCTL_EOF
    fi

    sysctl --system
    log_info "Kernel tuning applied."
}

# ── Start Services ─────────────────────────────────────────────────
start_services() {
    log_info "Starting superDHCP..."

    systemctl restart redis
    systemctl restart postgresql
    sleep 2   # wait for DB to come up
    systemctl start superdhcp
    systemctl restart nginx

    # Verify
    sleep 2
    if systemctl is-active --quiet superdhcp; then
        log_info "superDHCP is running!"
    else
        log_warn "superDHCP may not have started. Check: journalctl -u superdhcp -f"
    fi
}

# ── Firewall ───────────────────────────────────────────────────────
setup_firewall() {
    log_info "Configuring firewall..."

    if command -v firewall-cmd &>/dev/null; then
        firewall-cmd --zone=public --add-port=80/tcp --permanent
        firewall-cmd --zone=public --add-port=67/udp --permanent  # DHCPv4
        firewall-cmd --zone=public --add-port=547/udp --permanent # DHCPv6
        firewall-cmd --reload
    elif command -v iptables &>/dev/null; then
        iptables -I INPUT -p tcp --dport 80 -j ACCEPT
        iptables -I INPUT -p udp --dport 67 -j ACCEPT
        iptables -I INPUT -p udp --dport 547 -j ACCEPT
        service iptables save
    fi

    log_info "Firewall rules added."
}

# ── Print Summary ──────────────────────────────────────────────────
print_summary() {
    echo ""
    echo "============================================="
    echo "  ${BOLD}superDHCP Installation Complete${NC}"
    echo "============================================="
    echo ""
    echo "  Web UI:      http://$(hostname -I | awk '{print $1}'):80"
    echo "  API:         http://localhost:8000/api/"
    echo "  Default:     admin / admin@superDHCP2024"
    echo ""
    echo "  Commands:"
    echo "    systemctl start|stop|restart superdhcp"
    echo "    journalctl -u superdhcp -f       # live logs"
    echo "    journalctl -u superdhcp -n 100   # recent logs"
    echo ""
    echo "  Config:     $CONFIG_DIR/.env"
    echo "  Logs:       $LOG_DIR/"
    echo "  Data:       $DATA_DIR/"
    echo "============================================="
}

# ── Main ───────────────────────────────────────────────────────────
main() {
    preflight
    install_system_deps
    create_user
    setup_dirs
    setup_config
    setup_python_venv
    setup_frontend
    setup_postgres
    setup_redis
    setup_nginx
    configure_selinux
    setup_service
    setup_kernel
    setup_firewall
    start_services
    print_summary
}

main "$@"
