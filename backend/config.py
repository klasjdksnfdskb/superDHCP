"""
superDHCP — 后端配置管理中心
支持环境变量、配置文件、命令行参数三级优先级
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """全局配置，自动从环境变量 / .env 文件加载"""

    # ─── 应用基础 ───
    APP_NAME: str = "superDHCP"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ─── 数据库 ───
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://superdhcp:superdhcp_secure_pwd@localhost:5432/superdhcp",
        description="异步 PostgreSQL 连接串 (asyncpg 驱动)"
    )
    DB_POOL_SIZE: int = 40        # 连接池大小（支撑高并发）
    DB_MAX_OVERFLOW: int = 20     # 溢出连接数
    DB_POOL_RECYCLE: int = 3600   # 连接回收时间(秒)

    # ─── Redis ───
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── JWT 认证 ───
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_RANDOM_64_CHARS"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── DHCP 服务 ───
    DHCPV4_ENABLED: bool = True
    DHCPV6_ENABLED: bool = True
    DHCPV4_INTERFACE: str = "eth0"
    DHCPV6_INTERFACE: str = "eth0"
    DHCPV4_SERVER_PORT: int = 67   # DHCPv4 标准端口
    DHCPV6_SERVER_PORT: int = 547  # DHCPv6 标准端口
    DHCP_WORKERS: int = 4          # DHCP 协议处理进程数

    # ─── 租约管理 ───
    LEASE_DEFAULT_TIME: int = 86400          # 默认租期 24h
    LEASE_MAX_TIME: int = 604800             # 最大租期 7d
    LEASE_CLEANUP_INTERVAL: int = 300        # 过期清理间隔(秒)
    LEASE_BATCH_FLUSH_SIZE: int = 1000       # 批量写入数据库的阈值

    # ─── 性能调优 ───
    API_RATE_LIMIT: str = "100/minute"       # API 限流
    MAX_EXPORT_ROWS: int = 1000000           # CSV 导出最大行数
    QUERY_PAGE_SIZE_MAX: int = 500           # 分页最大条数

    # ─── CORS ───
    CORS_ORIGINS: List[str] = ["http://localhost:8080", "http://localhost:3000"]

    # ─── Web 管理 ───
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin@superDHCP2024"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
