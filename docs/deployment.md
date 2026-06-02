# superDHCP 部署运维手册

## 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 操作系统 | openEuler 22.03 LTS | openEuler 24.03 LTS |
| CPU | 4 核 | 8 核 + |
| 内存 | 8 GB | 16 GB + |
| 磁盘 | 50 GB SSD | 200 GB SSD (视租约量) |
| Python | 3.10 | 3.11 |
| Node.js | 18 LTS | 20 LTS |
| PostgreSQL | 14 | 15 |
| Redis | 6 | 7 |
| Nginx | 1.20+ | 1.22+ |

## 一键离线部署 (推荐)

整个部署过程**无需互联网连接**，所有依赖预置在 `vendor/` 目录中。

### 前置准备（在联网机器上执行一次）

```bash
# 1. 下载 Python 依赖到 vendor/pypi/
pip download -d vendor/pypi -r backend/requirements.txt

# 2. 安装前端依赖并打包到 vendor/npm-packages/ (前端需要 node_modules)
cd frontend
npm install
# 打包所有依赖为 .tgz（可选，用于离线重建）
for pkg in node_modules/*/package.json; do
  dir=$(dirname "$pkg")
  (cd "$dir" && npm pack --pack-destination ../../vendor/npm-packages/) 2>/dev/null || true
done

# 3. 构建前端
npm run build

# 4. 打包整个项目
cd ../..
tar -czf superDHCP-v1.0.0.tar.gz superDHCP/
```

### 在 openEuler 上部署

```bash
# 1. 解压
tar -xzf superDHCP-v1.0.0.tar.gz
cd superDHCP

# 2. 执行安装（root 权限）
sudo bash install.sh
```

安装脚本自动完成：
- 系统依赖安装（Python3, PostgreSQL, Redis, Nginx）
- 创建应用用户和目录结构
- Python 虚拟环境（离线）
- PostgreSQL 数据库初始化
- Redis 配置
- Nginx 反向代理
- Systemd 服务注册
- 内核参数调优
- 防火墙规则

### 部署后验证

```bash
# 检查服务状态
systemctl status superdhcp
systemctl status postgresql
systemctl status redis
systemctl status nginx

# 健康检查
curl http://localhost/api/health

# 查看日志
journalctl -u superdhcp -f
```

## 初始登录

- URL: `http://<server-ip>`
- 用户名: `admin`
- 密码: `admin@superDHCP2024`
- ⚠️ **首次登录后请立即修改密码**

## 服务管理

```bash
# 启停服务
systemctl start superdhcp
systemctl stop superdhcp
systemctl restart superdhcp
systemctl enable superdhcp   # 开机自启
systemctl disable superdhcp  # 取消自启

# 查看状态
systemctl status superdhcp

# 实时日志
journalctl -u superdhcp -f

# 最近日志
journalctl -u superdhcp -n 100
```

## 目录结构

```
/opt/superDHCP/          # 应用目录
├── backend/             # FastAPI 后端
│   └── .venv/           # Python 虚拟环境
└── frontend/            # 前端静态文件 (dist/)

/etc/superdhcp/          # 配置文件
└── .env                 # 环境变量

/var/lib/superdhcp/      # 运行时数据
/var/log/superdhcp/      # 日志目录

/etc/nginx/conf.d/       # Nginx 配置
└── superdhcp.conf
```

## 配置说明

编辑 `/etc/superdhcp/.env`：

```
DATABASE_URL=postgresql+asyncpg://superdhcp:PASSWORD@localhost:5432/superdhcp
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<random-48-bytes>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
LOG_LEVEL=INFO
DHCPv4_INTERFACE=eth0
DHCPv6_INTERFACE=eth0
```

## 备份 & 恢复

```bash
# 备份数据库
pg_dump -U superdhcp superdhcp > backup_$(date +%Y%m%d).sql

# 恢复
psql -U superdhcp superdhcp < backup_20240601.sql

# 定时备份 (crontab)
0 3 * * * pg_dump -U superdhcp superdhcp | gzip > /backup/superdhcp_$(date +\%Y\%m\%d).sql.gz
```

## 监控

```bash
# 健康检查
curl http://localhost/api/health

# 租约统计
curl -H "Authorization: Bearer <token>" http://localhost/api/dashboard/stats

# 查看日志
journalctl -u superdhcp -f

# 系统资源
htop
free -h
df -h
```

## 升级流程

```bash
# 1. 停止服务
systemctl stop superdhcp

# 2. 备份
pg_dump -U superdhcp superdhcp > /backup/pre_upgrade_$(date +%Y%m%d).sql

# 3. 更新应用文件
rsync -a /path/to/new/superDHCP/backend/ /opt/superDHCP/backend/
rsync -a /path/to/new/superDHCP/frontend/dist/ /opt/superDHCP/frontend/

# 4. 更新 Python 依赖
source /opt/superDHCP/backend/.venv/bin/activate
pip install --no-index --find-links=/path/to/new/vendor/pypi -r /opt/superDHCP/backend/requirements.txt

# 5. 启动服务
systemctl start superdhcp
```

## 故障排查

### 服务无法启动

```bash
# 检查详细错误
journalctl -u superdhcp -n 50 --no-pager

# 常见原因:
# - PostgreSQL 未运行: systemctl restart postgresql
# - Redis 未运行: systemctl restart redis
# - 端口占用: ss -tlnp | grep 8000
# - 权限问题: 检查 /opt/superDHCP/ 所有权
```

### 前端 502 错误

```bash
# 检查后端是否运行
systemctl status superdhcp

# 检查 Nginx 配置
nginx -t
systemctl restart nginx
```
