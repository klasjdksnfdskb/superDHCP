"""
superDHCP — FastAPI 应用入口
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app_settings import settings
from models.database import init_db, engine
from services.dhcp_server import DHCPServer
from services.redis_client import close_redis, rate_limit_check
from routers import (
    auth_router,
    dashboard_router,
    pools_router,
    leases_router,
    tags_router,
    users_router,
)

# ─── 日志 ───
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# ─── 应用生命周期 ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动 & 关闭钩子"""
    logger.info(f"🚀 superDHCP v{settings.APP_VERSION} 启动中...")

    # 初始化数据库
    await init_db()

    # 创建默认管理员 (如果不存在)
    await _seed_default_admin()

    # 启动 DHCP 协议服务 (后台任务)
    dhcp_server = DHCPServer()
    dhcp_task = asyncio.create_task(dhcp_server.start())
    app.state.dhcp_server = dhcp_server
    app.state.dhcp_task = dhcp_task
    logger.info("✅ superDHCP 就绪 — API:8000 DHCPv4:67 DHCPv6:547")

    yield

    # 关闭 DHCP 服务
    logger.info("🛑 superDHCP 关闭中...")
    if dhcp_server:
        dhcp_server.running = False
    if dhcp_task and not dhcp_task.done():
        dhcp_task.cancel()
        try:
            await dhcp_task
        except asyncio.CancelledError:
            pass
    await dhcp_server.stop()
    await close_redis()
    await engine.dispose()
    logger.info("✅ 数据库连接池已释放")


async def _seed_default_admin():
    """创建默认管理员账户 (如果不存在)"""
    from models.user import User, UserRole
    from models.database import AsyncSessionLocal
    from routers.auth import hash_password
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
        )
        if not result.scalars().first():
            admin = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                display_name="超级管理员",
                role=UserRole.SUPERADMIN,
            )
            session.add(admin)
            await session.commit()
            logger.info(f"✅ 默认管理员已创建: {settings.DEFAULT_ADMIN_USERNAME}")


# ─── 创建 FastAPI 应用 ───

app = FastAPI(
    title="superDHCP API",
    version=settings.APP_VERSION,
    description="企业级高并发 DHCPv4/DHCPv6 服务管理平台",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ─── 中间件 ───

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip 压缩
app.add_middleware(GZipMiddleware, minimum_size=1000)

# API 限流 (令牌桶, 60次/分钟/IP)
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 跳过健康检查 & 文档
        if request.url.path.startswith(("/api/health", "/api/docs", "/api/redoc")):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}:{request.url.path}"
        allowed = await rate_limit_check(key, max_requests=60, window_seconds=60)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试 (60次/分钟)"}
            )
        return await call_next(request)

app.add_middleware(RateLimitMiddleware)

# 安全头
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ─── 注册路由 ───

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(pools_router)
app.include_router(leases_router)
app.include_router(tags_router)
app.include_router(users_router)


# ─── 健康检查 ───

@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "dhcp_server_running": getattr(app.state, 'dhcp_server', None) is not None and app.state.dhcp_server.running,
        "services": {
            "dhcpv4": settings.DHCPV4_ENABLED,
            "dhcpv6": settings.DHCPV6_ENABLED,
        }
    }


@app.get("/")
async def root():
    return {
        "name": "superDHCP",
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
    }


# ─── 启动入口 ───

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
