# superDHCP — 企业级高性能 DHCP 服务平台

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-openEuler%2022.03%2B-brightgreen)](https://www.openeuler.org/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-18.x-61DAFB)](https://react.dev/)

> 面向运营商/大型企业的高并发 DHCPv4/DHCPv6 一体化服务解决方案，支持 50 万+ 终端同时在线。

---

## 🚀 核心能力

| 能力 | 说明 |
|------|------|
| **双栈 DHCP** | 同时提供 DHCPv4 和 DHCPv6（有状态/无状态）地址分配 |
| **超高并发** | 基于异步 IO + 共享内存，轻松支持 50 万+ 并发租约 |
| **MAC 索引数据库** | 以 MAC 为基准条目，一条记录关联 v4/v6 地址、租期、获取方式等全量信息 |
| **多地址池** | 按 VLAN ID 路由到不同地址池，支持预留地址与排除范围 |
| **多层组织架构标签** | 服务端自定义多层级标签（如 `省/市/机房/机架`），对客户端透明 |
| **科技感 Web 管理** | React 18 + 深色科技风 Dashboard，管理员账户体系、CSV 导出 |
| **中/英文双语** | 一键切换中文/English，浏览器语言自动检测，localStorage 持久化 |
| **离线部署** | 预置 Python wheels + NPM 缓存，无需联网即可完成 openEuler 部署 |
| **前后端分离** | FastAPI RESTful API + React SPA，独立部署，Nginx 反向代理 |

---

## 📊 数据库核心模型

```
┌──────────────────────────────────────────────────────────────────┐
│                        dhcp_leases (主表)                         │
├──────────────────────────────────────────────────────────────────┤
│ mac_address          VARCHAR(17) PRIMARY KEY   — MAC 基准条目     │
│ dhcpv4_address       INET                       — 分配的 IPv4 地址 │
│ dhcpv4_netmask       INET                       — 子网掩码         │
│ dhcpv4_gateway       INET                       — 默认网关         │
│ dhcpv4_dns           INET[]                     — DNS 服务器列表    │
│ dhcpv4_lease_start   TIMESTAMPTZ                — v4 租约开始时间   │
│ dhcpv4_lease_end     TIMESTAMPTZ                — v4 租约到期时间   │
│ dhcpv4_lease_time    INTEGER                    — v4 租期(秒)      │
│ dhcpv6_address       INET                       — 分配的 IPv6 地址 │
│ dhcpv6_prefix_len    INTEGER                    — IPv6 前缀长度     │
│ dhcpv6_duid          VARCHAR(128)               — DHCPv6 DUID      │
│ dhcpv6_iaid          INTEGER                    — IAID             │
│ dhcpv6_mode          VARCHAR(32)                — stateful/stateless│
│ dhcpv6_lease_start   TIMESTAMPTZ                — v6 租约开始时间   │
│ dhcpv6_lease_end     TIMESTAMPTZ                — v6 租约到期时间   │
│ dhcpv6_lease_time    INTEGER                    — v6 租期(秒)      │
│ vlan_id              INTEGER                    — VLAN ID          │
│ hostname             VARCHAR(255)               — 客户端主机名      │
│ option43             JSONB                      — Option 43 数据   │
│ option82             JSONB                      — Option 82 数据   │
│ custom_tag_id        UUID FK → custom_tags      — 组织架构标签     │
│ pool_id              UUID FK → address_pools    — 所属地址池       │
│ state                VARCHAR(16)                — active/expired/...│
│ first_seen           TIMESTAMPTZ                — 首次发现时间      │
│ last_updated         TIMESTAMPTZ                — 最后更新时间      │
└──────────────────────────────────────────────────────────────────┘
```

### 自定义组织架构标签

```
custom_tags 表支持无限层级：
  示例：中国 → 广东省 → 深圳市 → 南山区 → 数据中心A → 机房3 → 机架12
         ^      ^        ^       ^         ^         ^       ^
       level1 level2  level3  level4   level5   level6  level7
```

---

## 🏗️ 项目结构

```
superDHCP/
├── README.md                     # 项目总览
├── LICENSE                       # Apache 2.0
├── install.sh                    # 🔧 openEuler 一键部署脚本
├── vendor-download.sh            # 📦 离线依赖下载脚本
├── docker-compose.yml            # 本地开发用（生产推荐裸机部署）
├── docs/
│   ├── architecture.md           # 架构设计文档
│   └── deployment.md             # 部署运维手册
├── vendor/
│   ├── pypi/                     # Python 离线 Wheel 包
│   ├── npm-cache/                # NPM 离线缓存
│   └── npm-packages/             # NPM .tgz 包
├── backend/                      # FastAPI 后端
│   ├── main.py, config.py
│   ├── models/   (database, lease, pool, user, tags)
│   ├── routers/  (auth, pools, leases, tags, users, dashboard)
│   └── services/ (dhcp_server, dhcpv4, dhcpv6, pool_manager, lease_manager)
├── frontend/                     # React 18 SPA
│   ├── setup.sh                  # 🔧 离线前端构建脚本
│   ├── src/
│   │   ├── i18n.ts               # 🌐 国际化配置
│   │   ├── locales/ (zh.json, en.json)
│   │   ├── components/ (Layout, StatCard, PoolGauge, LeaseTable, TagTree)
│   │   ├── pages/ (Login, Dashboard, LeaseManagement, PoolManagement,
│   │   │          TagManagement, UserManagement, Settings)
│   │   ├── services/api.ts, hooks/useAuth.ts
│   │   └── styles/global.css     # 深色科技风
│   └── vite.config.ts, tsconfig.json
└── deploy/
    ├── nginx-superdhcp.conf      # Nginx 反向代理
    └── openEuler/sysctl-dhcp.conf  # 内核调优
```

---

## 🔧 快速开始

### 环境要求

- **OS**: openEuler 22.03 LTS 或更高
- **Python**: 3.10+
- **PostgreSQL**: 14+
- **Redis**: 6+
- **Nginx**: 1.20+

### 离线一键部署（推荐）

```bash
# 1. 在联网机器上下载所有依赖到 vendor/
bash vendor-download.sh

# 2. 将整个目录拷贝到 openEuler 目标机器
scp -r superDHCP/ root@<server-ip>:/opt/

# 3. 在 openEuler 上执行安装
sudo bash /opt/superDHCP/install.sh

# 4. 访问 Web 管理后台
# http://<server-ip>
# 默认账户: admin / admin@superDHCP2024
```

> 详细部署说明见 [docs/deployment.md](docs/deployment.md)

---

## 📡 API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 管理员登录 |
| `/api/auth/refresh` | POST | 刷新 JWT Token |
| `/api/dashboard/stats` | GET | 实时统计（租约数/池用量/活跃用户） |
| `/api/pools` | GET/POST | 地址池列表/创建 |
| `/api/pools/{id}` | GET/PUT/DELETE | 地址池详情/修改/删除 |
| `/api/pools/{id}/subnets` | GET/POST | 子网管理 |
| `/api/leases` | GET | 租约列表（支持过滤/分页/排序） |
| `/api/leases/export` | GET | 导出租约 CSV |
| `/api/leases/{mac}` | GET | 单条租约详情 |
| `/api/leases/{mac}/release` | POST | 手动释放租约 |
| `/api/tags` | GET/POST | 标签树查询/创建 |
| `/api/tags/{id}` | PUT/DELETE | 标签修改/删除 |
| `/api/tags/tree` | GET | 完整标签树（组织架构视图） |
| `/api/users` | GET/POST | 用户列表/创建 |
| `/api/users/{id}` | PUT/DELETE | 用户修改/删除 |
| `/api/users/{id}/password` | PUT | 修改密码 |

---

## 🎨 Web 界面

- **深色科技风** Dashboard，实时刷新地址池利用率、活跃租约
- **中/英文一键切换**：侧边栏底部按钮，`localStorage` 持久化语言偏好
- **租约管理**：按 MAC/IP/VLAN/标签 多维度筛选，CSV 批量导出
- **地址池配置**：可视化创建/编辑，配置 VLAN 绑定，设置预留地址
- **组织架构标签**：无限层级树形结构管理，租约关联标签
- **多用户管理**：超级管理员/管理员/观察者三级角色

---

## 📈 性能指标

| 指标 | 目标值 | 实现方式 |
|------|--------|----------|
| 并发租约数 | ≥ 500,000 | PostgreSQL 分区表 + 连接池 |
| DHCP 请求处理 | ≥ 50,000 QPS | Python asyncio + UDP 多进程 |
| Web API 响应 | < 100ms (P95) | FastAPI 异步 ORM + Redis 缓存 |
| CSV 导出 | 50 万行 < 30s | 流式查询 + 分块写入 |

---

## 🛡️ 安全

- JWT Token 认证 + 刷新机制
- 密码 bcrypt 哈希存储
- API 限流（令牌桶算法）
- 操作审计日志
- CORS 白名单
- 输入参数严格校验

---

## 📄 License

Apache License 2.0 — 详见 [LICENSE](LICENSE)