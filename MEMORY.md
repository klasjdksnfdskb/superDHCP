# superDHCP — 项目持久记忆

## 身份

- 项目名: superDHCP
- 定位: 运营商级 DHCPv4/v6 服务器
- 目标平台: openEuler 22.03+
- 并发目标: ≥ 500,000 终端

## 核心设计决策（不可改变）

### 1. MAC 基准条目
`dhcp_leases` 以 MAC 为主键，一条记录含 v4 + v6 全量双栈信息。
Option43 (JSONB)、Option82 (JSONB)、DUID、IAID、有状态/无状态模式。

### 2. VLAN → 地址池路由
Option82 解析 VLAN ID → `address_pools.vlan_ids` 数组绑定 → fallback 池兜底。

### 3. 自定义标签（无限层级）
`CustomTag.parent_id` 自引用，`get_full_path()` 返回完整路径。
服务端专用，客户端无感知。租约查询和 CSV 导出处可见完整路径。

### 4. IPv6 双模式
`DHCPv6Mode` 枚举: stateful / stateless / slaac。DUID 必选，IAID 可选。

### 5. 前端风格（不可改为浅色）
深色科技风: `#0a0e17` 主背景，`#3b82f6` 强调色。

### 6. 认证体系
JWT 双 Token (access + refresh) + bcrypt 哈希。
三级角色: superadmin / admin / viewer。
默认账户: admin / admin@superDHCP2024

### 7. 部署方式
禁止 Docker 生产部署。仅支持裸机 openEuler 直接部署。
`install.sh` 一键安装脚本。`vendor/` 目录预置所有离线依赖。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI (Python 3.10+) |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库 | PostgreSQL 15+ |
| 缓存 | Redis 7+ |
| DHCP 引擎 | asyncio + 原生 UDP |
| 前端框架 | React 18 + TypeScript |
| 构建工具 | Vite 5 |
| 图表 | Recharts 2.x |
| 图标 | Lucide React |
| 国际化 | i18next + react-i18next |
| 反向代理 | Nginx 1.20+ |

## 文件结构要点

- `install.sh` — openEuler 裸机一键安装
- `vendor-download.sh` — 离线依赖打包（在联网机器运行）
- `vendor/pypi/` — Python wheel 离线包
- `vendor/npm-cache/` — npm 缓存（平台特定）
- `vendor/npm-packages/` — npm .tgz 离线包
- `frontend/setup.sh` — 前端离线构建脚本
- `frontend/src/locales/{zh,en}.json` — 双语字典
- `frontend/src/i18n.ts` — i18next 配置 + 浏览器语言检测
- `deploy/nginx-superdhcp.conf` — Nginx 配置

## 目录文件清单

```
superDHCP/
├── README.md, LICENSE
├── install.sh, vendor-download.sh
├── docker-compose.yml (仅本地开发)
├── docs/architecture.md, docs/deployment.md
├── vendor/ (pypi/, npm-cache/, npm-packages/)
├── backend/ (main.py, config.py, requirements.txt, Dockerfile,
│            models/, routers/, services/)
├── frontend/ (setup.sh, package.json, tsconfig.json, vite.config.ts,
│              index.html, src/ (i18n.ts, locales/, components/,
│              pages/, services/, hooks/, styles/))
├── deploy/ (nginx-superdhcp.conf, openEuler/sysctl-dhcp.conf)
└── MEMORY.md
```

## 操作日志

- 2026-06-01: 项目创建，完成数据模型、后端路由、前端、部署结构
- 2026-06-01: 新增中英文双语切换 (i18next)
- 2026-06-01: 移除 Docker 生产部署，改为裸机 openEuler 直接安装
- 2026-06-01: 新增 vendor/ 离线依赖打包机制
- 2026-06-01: 新增 install.sh 全自动部署脚本
