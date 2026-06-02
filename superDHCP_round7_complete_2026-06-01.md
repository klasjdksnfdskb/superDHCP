# superDHCP Round 7: Offline Vendor + Bugfixes

## Objective
完善离线部署依赖打包机制，修复前端构建错误，完成 i18n 收尾。

## Key Actions

### 1. TagTree 组件 i18n
- 添加 `useTranslation` hook
- 硬编码中文 "暂无组织架构标签" / "创建根标签" → `t('tags.noTags')` / `t('tags.createRoot')`

### 2. 离线依赖打包
- `vendor-download.sh` 重写：完整流程 script，包含 Python wheels 下载、npm install、npm cache 复制到 vendor/npm-cache/
- `vendor/npm-cache/_cacache` — 从本机 npm cache 复制 (2,148 文件)
- `frontend/setup.sh` — 新建：离线前端构建脚本，优先使用 vendor/npm-cache 或 vendor/npm-packages/*.tgz
- `install.sh` 升级：新增 `setup_frontend()` 函数（在 install 流程中调用），优先用预构建 dist，其次运行 frontend/setup.sh；Python venv 部分改进 pip upgrade 逻辑
- `docker-compose.yml` 添加 DEPRECATED 水印注释

### 3. 前端构建错误修复
- **useAuth.ts → useAuth.tsx**：JSX 语法在 `.ts` 文件中不被 TypeScript 识别，`<AuthContext.Provider>` 被解析为泛型类型断言
- **LeaseManagement.tsx**：`LeaseItem` 从 LeaseTable 导入并使用为 `useState<LeaseItem[]>` 类型
- **LeaseTable.tsx**：`LeaseItem` 接口添加 `export`

### 4. README.md 全面重写
- 新增：中/英文双语能力、离线部署能力
- 项目结构简化：移除 Docker 优先，改为裸机部署
- 快速开始：离线部署三步流程 (vendor-download.sh → scp → install.sh)

## Build Result
```
✓ built in 7.84s
dist/index.html         0.47 kB
dist/assets/index.css   7.62 kB
dist/assets/index.js  311.10 kB (gzip: 98.59 kB)
```

## Key Technical Notes
- `.ts` vs `.tsx`: Vite 能自动处理，但 tsc 不能 — JSX 必须用 `.tsx` 扩展名
- npm offline cache: 需要 `_cacache` 目录 + `--cache <path> --prefer-offline` 参数
- 跨平台 npm: `.tgz` 包含平台无关源码，但原生模块（esbuild, rollup 等）需在目标平台重新编译
- 最佳离线流程：联网 Linux 机器执行 vendor-download.sh → 打包整个目录 → 拷贝到 openEuler → install.sh
