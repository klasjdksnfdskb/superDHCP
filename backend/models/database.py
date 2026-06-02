"""
数据库引擎 & 会话管理
异步 PostgreSQL + SQLAlchemy 2.0 async style
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from sqlalchemy.orm import DeclarativeBase
from config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.DEBUG,
    # PostgreSQL 优化
    connect_args={
        "server_settings": {
            "application_name": "superDHCP",
            "jit": "off",  # OLTP 场景关闭 JIT
        }
    }
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入 — 自动获取/释放会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """应用启动时: 创建所有表 + 初始化种子数据"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)