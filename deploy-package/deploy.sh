#!/bin/bash
set -eu

# superDHCP 前端热更新脚本
# 用法: ./deploy.sh

FRONTEND_DIR="/opt/superDHCP/frontend"
BACKEND_DIR="/opt/superDHCP/backend-source"

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Error: $FRONTEND_DIR not found"
    exit 1
fi

echo "=== superDHCP 前端更新 ==="

# 1. 替换前端文件
if [ -d "$(dirname "$0")/frontend/dist" ]; then
    rsync -a --delete "$(dirname "$0")/frontend/dist/" "$FRONTEND_DIR/"
    echo "✅ Frontend files updated"
else
    echo "⚠️  frontend/dist not found in deploy-package, skipping"
fi

# 2. 重载nginx
if systemctl is-active --quiet nginx 2>/dev/null; then
    systemctl reload nginx && echo "✅ nginx reloaded" || echo "⚠️  nginx reload failed"
fi

# 3. 重启后端
if systemctl is-active --quiet superdhcp 2>/dev/null; then
    systemctl restart superdhcp && echo "✅ superdhcp restarted" || echo "⚠️  superdhcp restart failed"
else
    echo "⚠️  superdhcp service not running"
fi

# 4. 状态摘要
echo ""
echo "=== 服务状态 ==="
systemctl status superdhcp --no-pager -l 2>/dev/null | head -5
echo ""
echo "=== 前端文件 ==="
ls -lh "$FRONTEND_DIR/assets/" 2>/dev/null
echo ""
echo "部署完成！浏览器 Ctrl+F5 强制刷新验证"